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


class VoiceReceiver:
    """ Consumes incoming RTP voice packets and dispatches audio to an :class:`AudioSink`. """

    def __init__(self, voice_client: "VoiceClient") -> None:
        """
        Create a receiver bound to a voice client.

        Parameters
        ----------
        voice_client:
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

    def start(self, sink: "AudioSink") -> None:
        """
        Begin listening, dispatching received audio to ``sink``.

        Parameters
        ----------
        sink:
            The sink to receive decoded PCM or raw Opus audio.
        """
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

    def is_listening(self) -> bool:
        """
        Whether a sink is currently attached.

        Returns
        -------
            ``True`` if listening, ``False`` otherwise.
        """
        return self.sink is not None

    def add_ssrc(self, ssrc: int, user_id: int) -> None:
        """
        Associate an RTP SSRC with a user ID.

        Parameters
        ----------
        ssrc:
            The RTP synchronisation source identifier.
        user_id:
            The user ID that owns the SSRC.
        """
        self._ssrc_map[ssrc] = user_id

    def remove_user(self, user_id: int) -> None:
        """
        Remove every SSRC mapping and decoder belonging to a user.

        Parameters
        ----------
        user_id:
            The user ID to forget.
        """
        stale = [ssrc for ssrc, uid in self._ssrc_map.items() if uid == user_id]

        for ssrc in stale:
            del self._ssrc_map[ssrc]
            self._last_seq.pop(ssrc, None)

            decoder = self._decoders.pop(ssrc, None)
            if decoder is not None:
                decoder.cleanup()

    def _get_decoder(self, ssrc: int) -> Decoder:
        """
        Return the per-SSRC decoder, creating it on first use.

        Parameters
        ----------
        ssrc:
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
        packet:
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
        except Exception:
            _log.exception("Failed to transport-decrypt incoming voice packet")
            return

        # DAVE end-to-end decryption, applied only when a session is active and
        # we know who the sender is. Tolerant: skip silently when inactive.
        if user_id is not None and connection.can_encrypt():
            try:
                payload = connection.dave_decrypt_opus(user_id, payload)
            except Exception:
                _log.exception("Failed to DAVE-decrypt incoming voice packet")
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
        ssrc:
            The RTP synchronisation source identifier of the sender.
        sequence:
            The RTP sequence number of the packet, used to detect gaps.
        payload:
            The Opus payload to decode.

        Returns
        -------
            The decoded signed 16-bit little-endian stereo PCM, or ``None`` when
            libopus is unavailable and the packet must be dropped.
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

            # Detect a sequence gap and conceal a single lost frame before
            # decoding the packet we actually received. RTP sequence numbers are
            # 16-bit and wrap, so compare modulo 2**16.
            last = self._last_seq.get(ssrc)
            if last is not None and (sequence - last) & 0xFFFF > 1:
                decoder.decode(None)

            self._last_seq[ssrc] = sequence

            return decoder.decode(payload)
        except Exception:
            _log.exception("Failed to Opus-decode received voice packet")
            return None
