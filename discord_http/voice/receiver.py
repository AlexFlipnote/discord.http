import logging
import struct

from typing import TYPE_CHECKING

from . import opus
from .opus import Decoder
from .sinks import VoiceData

if TYPE_CHECKING:
    from .client import VoiceClient
    from .sinks import AudioSink

__all__ = (
    "VoiceReceiver",
)

_log = logging.getLogger(__name__)


# The fixed-length portion of an RTP header is 12 bytes; the SSRC is the final
# 32-bit big-endian field, occupying bytes 8..12.
_RTP_HEADER_LENGTH = 12
_SSRC_OFFSET = 8

# The RTP timestamp is a 32-bit big-endian field occupying bytes 4..8.
_TIMESTAMP_OFFSET = 4

# The RTP sequence number is a 16-bit big-endian field occupying bytes 2..4.
_SEQUENCE_OFFSET = 2

# Per-packet failures are logged on the first occurrence and then once every
# this many, a broken stream would otherwise log ~50 lines a second per speaker
_LOG_EVERY = 500


class VoiceReceiver:
    """ Consumes incoming RTP voice packets and dispatches audio to an :class:`AudioSink`. """

    def __init__(self, voice_client: "VoiceClient") -> None:
        """
        Create a receiver bound to a voice client.

        Parameters
        ----------
        voice_client
            The voice client this receiver belongs to, used to reach the
            connection (encryptor, DAVE hooks) and event loop.
        """
        self.voice_client = voice_client
        """ The voice client this receiver belongs to. """

        self.sink: "AudioSink | None" = None
        """ The sink currently receiving audio, or ``None`` when not listening. """

        self._ssrc_map: dict[int, int] = {}
        """ Maps an RTP SSRC to the user ID it belongs to. """

        # Lazily-created per-SSRC Opus decoders. Only populated when the active
        # sink wants PCM, since Opus passthrough never needs to decode.
        self._decoders: dict[int, Decoder] = {}

        # Per-SSRC last seen RTP sequence number, used for lightweight
        # packet-loss concealment when decoding to PCM.
        self._last_seq: dict[int, int] = {}

        # Whether the missing-libopus warning has already been emitted, so the
        # synchronous UDP callback does not spam the log on every packet.
        self._warned_no_opus = False

        # Count of packets dropped because DAVE was active but the SSRC was
        # not yet mapped to a user, used to rate-limit the debug log.
        self._dave_unmapped_drops = 0

        # Failure kind -> how many times it happened, used to rate-limit logs
        self._failures: dict[str, int] = {}

    def start(self, sink: "AudioSink") -> None:
        """
        Begin listening, dispatching received audio to ``sink``.

        Parameters
        ----------
        sink
            The sink to receive decoded PCM or raw Opus audio.
        """
        # Tear down any in-progress session so its sink is cleaned up and stale
        # per-SSRC decoder/sequence state does not leak into the new sink.
        if self.sink is not None:
            self.stop()

        self.sink = sink

    def stop(self) -> None:
        """ Stop listening and release any per-SSRC decoders and the sink. """
        sink = self.sink
        self.sink = None

        for decoder in self._decoders.values():
            decoder.cleanup()

        self._decoders.clear()
        self._last_seq.clear()

        if sink is not None:
            try:
                sink.cleanup()
            except Exception:
                _log.exception("Error while cleaning up audio sink")

    def reset(self) -> None:
        """
        Drop all SSRC-keyed state for a fresh voice session.

        Called on voice READY, where a fresh session has just allocated new
        SSRCs. Separate from :meth:`stop` because ``stop()`` also detaches and
        finalizes the sink. A reconnect must keep listening with the existing
        sink while forgetting mappings, decoders and sequence state tied to
        SSRCs from the previous session.
        """
        for decoder in self._decoders.values():
            decoder.cleanup()

        self._ssrc_map.clear()
        self._decoders.clear()
        self._last_seq.clear()
        self._dave_unmapped_drops = 0
        self._failures.clear()

    def is_listening(self) -> bool:
        """ Whether a sink is currently attached. """
        return self.sink is not None

    def add_ssrc(self, ssrc: int, user_id: int) -> None:
        """
        Associate an RTP SSRC with a user ID.

        Parameters
        ----------
        ssrc
            The RTP synchronisation source identifier.
        user_id
            The user ID that owns the SSRC.
        """
        self._ssrc_map[ssrc] = user_id

    def remove_user(self, user_id: int) -> None:
        """
        Remove every SSRC mapping and decoder belonging to a user.

        Parameters
        ----------
        user_id
            The user ID to forget.
        """
        stale = [ssrc for ssrc, uid in self._ssrc_map.items() if uid == user_id]

        for ssrc in stale:
            del self._ssrc_map[ssrc]
            self._last_seq.pop(ssrc, None)

            decoder = self._decoders.pop(ssrc, None)
            if decoder is not None:
                decoder.cleanup()

    def _log_failure(self, kind: str, message: str, *, level: int = logging.WARNING) -> None:
        """
        Log a per-packet failure, rate-limited per kind.

        Parameters
        ----------
        kind
            What failed, failures of the same kind share a counter.
        message
            The message to log.
        level
            The logging level to use.
        """
        count = self._failures.get(kind, 0) + 1
        self._failures[kind] = count
        if count == 1 or count % _LOG_EVERY == 0:
            _log.log(level, f"{message} (seen {count} time(s))")

    def _get_decoder(self, ssrc: int) -> Decoder:
        """
        Return the per-SSRC decoder, creating it on first use.

        Parameters
        ----------
        ssrc
            The RTP synchronisation source identifier to decode for.

        Returns
        -------
            The decoder dedicated to ``ssrc``.
        """
        decoder = self._decoders.get(ssrc)
        if decoder is None:
            decoder = Decoder()
            self._decoders[ssrc] = decoder

        return decoder

    def unpack(self, packet: bytes) -> None:
        """
        Decrypt, decode and dispatch a single received RTP packet.

        This is called synchronously from the UDP datagram callback, so it must
        never raise: every failure is logged and swallowed.

        Parameters
        ----------
        packet
            The raw RTP packet as received from the voice UDP socket.
        """
        sink = self.sink
        if sink is None:
            return

        if len(packet) < _RTP_HEADER_LENGTH:
            return

        ssrc = struct.unpack_from(">I", packet, _SSRC_OFFSET)[0]
        timestamp = struct.unpack_from(">I", packet, _TIMESTAMP_OFFSET)[0]
        sequence = struct.unpack_from(">H", packet, _SEQUENCE_OFFSET)[0]
        user_id = self._ssrc_map.get(ssrc)

        connection = self.voice_client.connection

        encryptor = connection.encryptor
        if encryptor is None:
            # No session key yet (or already torn down); nothing decryptable.
            return

        try:
            payload = encryptor.decrypt(packet)
        except Exception as exc:
            # Expected briefly after a reconnect, packets still carry the old key
            self._log_failure("transport", f"Failed to transport-decrypt incoming voice packet: {exc!r}", level=logging.DEBUG)
            return

        if not payload:
            return

        # RTP padding (RFC 3550 5.1): the last payload byte is the padding length.
        # Clients send padding-only packets as bandwidth probes, they carry no audio.
        if packet[0] & 0x20 and payload:
            payload = payload[:-payload[-1]] if payload[-1] <= len(payload) else b""
            if not payload:
                return

        # DAVE end-to-end decryption, applied whenever a session is active.
        # Decrypting requires knowing who the sender is, and RTP (UDP) has no
        # ordering guarantee against the SPEAKING event (voice websocket) that
        # maps the SSRC to a user. If the mapping has not arrived yet, drop the
        # packet rather than passing the still-encrypted payload along as if it
        # were plain Opus; losing a few leading frames is acceptable.
        if not connection.can_decrypt():
            # End-to-end encryption is negotiated but our session isn't ready
            # (joining, or a group change), these frames are still ciphertext
            if connection.is_undecryptable_dave_frame(payload):
                self._log_failure(
                    "dave_pending",
                    "Dropped DAVE-encrypted voice while the DAVE session is not ready",
                    level=logging.DEBUG,
                )
                return

        else:
            if user_id is None:
                self._dave_unmapped_drops += 1
                if self._dave_unmapped_drops == 1 or self._dave_unmapped_drops % 100 == 0:
                    _log.debug(
                        f"Dropped {self._dave_unmapped_drops} DAVE-encrypted packet(s) "
                        f"from not-yet-mapped SSRC(s), latest ssrc={ssrc}"
                    )
                return

            try:
                payload = connection.dave_decrypt_opus(user_id, payload)
            except Exception as exc:
                # A member joining sends plaintext until their DAVE transition
                # completes, the protocol expects those frames to be dropped
                if "UnencryptedWhenPassthroughDisabled" in str(exc):
                    _log.debug(f"Dropped unencrypted frame from user {user_id} during a DAVE transition")
                else:
                    self._log_failure("dave", f"Failed to DAVE-decrypt incoming voice from user {user_id}: {exc!r}")
                return

        if sink.wants_opus():
            data = VoiceData(user=user_id, pcm=None, opus=payload, timestamp=timestamp, ssrc=ssrc)
        else:
            pcm = self._decode_pcm(ssrc, sequence, payload)
            if pcm is None:
                return
            data = VoiceData(user=user_id, pcm=pcm, opus=None, timestamp=timestamp, ssrc=ssrc)

        try:
            sink.write(user_id, data)
        except Exception:
            _log.exception("Error in audio sink while writing received voice data")

    def _decode_pcm(self, ssrc: int, sequence: int, payload: bytes) -> bytes | None:
        """
        Decode an Opus payload to PCM, applying lightweight packet-loss concealment.

        Parameters
        ----------
        ssrc
            The RTP synchronisation source identifier of the sender.
        sequence
            The RTP sequence number of the packet, used to detect gaps.
        payload
            The Opus payload to decode.

        Returns
        -------
            The decoded signed 16-bit little-endian stereo PCM, prefixed with one
            concealment frame when a gap was detected. ``None`` when libopus is
            unavailable or the packet arrived late and must be dropped.
        """
        if not opus.is_loaded():
            # PCM was requested but libopus is missing. Log once and drop rather
            # than raising, so the synchronous UDP callback never crashes.
            if not self._warned_no_opus:
                self._warned_no_opus = True
                _log.warning("libopus is not loaded; dropping received voice (PCM decoding unavailable)")
            return None

        try:
            decoder = self._get_decoder(ssrc)

            # RTP sequence numbers are 16-bit and wrap, so compare modulo 2**16.
            # A delta in the upper half means the packet is late/duplicate.
            concealed = b""
            last = self._last_seq.get(ssrc)
            if last is not None:
                delta = (sequence - last) & 0xFFFF
                if delta == 0 or delta >= 0x8000:
                    # No jitter buffer, late packets are dropped as the decoder
                    # has already moved past them
                    return None
                if delta > 1:
                    # Conceal a single lost frame and keep it, so recordings
                    # don't drift shorter than wall clock on loss
                    concealed = decoder.decode(None)

            self._last_seq[ssrc] = sequence

            return concealed + decoder.decode(payload)
        except Exception as exc:
            self._log_failure("opus", f"Failed to Opus-decode received voice packet: {exc!r}")
            return None
