import asyncio
import logging
import struct

from collections.abc import Callable
from typing import TYPE_CHECKING

from .connection import VoiceConnection

if TYPE_CHECKING:
    from ..channel import PartialChannel
    from ..client import Client
    from .opus import Encoder
    from .player import AudioPlayer, AudioSourceInput
    from .receiver import VoiceReceiver
    from .sinks import AudioSink

__all__ = ("VoiceClient",)

_log = logging.getLogger(__name__)


class VoiceClient:
    """
    The public handle for an active voice connection in a guild.

    Wraps the lower-level :class:`VoiceConnection` and exposes playback,
    receiving, and RTP transmission helpers.
    """

    def __init__(self, client: "Client", channel: "PartialChannel"):
        self.client: "Client" = client
        """ The bot client that owns this voice client. """

        self.bot: "Client" = client
        """ Alias of :attr:`client`. """

        self.channel: "PartialChannel" = channel
        """ The voice channel this client is connected to. """

        if channel.guild_id is None:
            raise ValueError("Cannot create a voice client for a channel without a guild")

        self.guild_id: int = channel.guild_id
        """ The ID of the guild this voice client is in. """

        self.connection: VoiceConnection = VoiceConnection(self)
        """ The underlying voice connection state machine. """

        self._player: "AudioPlayer | None" = None
        self._receiver: "VoiceReceiver | None" = None
        self._encoder: "Encoder | None" = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """ The event loop the client runs on. """
        return self.client.loop

    @property
    def user_id(self) -> int:
        """ The ID of the bot user. """
        return self.client.user.id

    @property
    def ssrc(self) -> int | None:
        """ The SSRC assigned to this connection. """
        return self.connection.ssrc

    @property
    def secret_key(self) -> bytes | None:
        """ The transport secret key, once known. """
        return self.connection.secret_key

    @property
    def latency(self) -> float:
        """ The latency of the most recent voice heartbeat, in seconds. """
        return self.connection.latency

    @property
    def average_latency(self) -> float:
        """ The average latency of recent voice heartbeats, in seconds. """
        return self.connection.average_latency

    @property
    def voice_privacy_code(self) -> str | None:
        """ The DAVE voice privacy code, if available. """
        return self.connection.voice_privacy_code

    @property
    def endpoint(self) -> str | None:
        """ The voice server endpoint host. """
        return self.connection.endpoint

    @property
    def session_id(self) -> str | None:
        """ The voice session ID. """
        return self.connection.session_id

    def is_connected(self) -> bool:
        """ Whether the voice connection is established. """
        return self.connection.is_connected()

    async def connect(
        self,
        *,
        timeout: float = 30.0,
        reconnect: bool = True,
        self_deaf: bool = False,
        self_mute: bool = False
    ) -> None:
        """
        Connect to the voice channel.

        Parameters
        ----------
        timeout:
            The maximum time to wait for the handshake, in seconds.
        reconnect:
            Whether to attempt reconnection on failure.
        self_deaf:
            Whether to join self-deafened.
        self_mute:
            Whether to join self-muted.
        """
        await self.connection.connect(
            timeout=timeout,
            reconnect=reconnect,
            self_deaf=self_deaf,
            self_mute=self_mute,
        )

    async def disconnect(self, *, force: bool = True) -> None:
        """
        Disconnect from the voice channel and clean up.

        Parameters
        ----------
        force:
            Whether to force the disconnect even on error.
        """
        if self._player is not None:
            self._player.stop()
            self._player = None

        if self._receiver is not None:
            self._receiver.stop()
            self._receiver = None

        if self._encoder is not None:
            self._encoder.cleanup()
            self._encoder = None

        await self.connection.disconnect(force=force)
        self.client._remove_voice_client(self.guild_id)

    async def _cleanup(self) -> None:
        """
        Tear down the voice client locally without relying on the gateway.

        Stops the player and receiver, closes the websocket and UDP transport,
        and removes the client from the registry. Safe to call when the owning
        shard has been reset or killed and op4 can no longer be sent.
        """
        if self._player is not None:
            self._player.stop()
            self._player = None

        if self._receiver is not None:
            self._receiver.stop()
            self._receiver = None

        if self._encoder is not None:
            self._encoder.cleanup()
            self._encoder = None

        await self.connection.close_transport()
        self.client._remove_voice_client(self.guild_id)

    async def move_to(self, channel: "PartialChannel | int") -> None:
        """
        Move to a different voice channel.

        Parameters
        ----------
        channel:
            The channel to move to, either a channel object or its ID.
        """
        if isinstance(channel, int):
            channel = self.client.get_partial_channel(channel, guild_id=self.guild_id)
        await self.connection.move_to(channel)
        self.channel = channel

    def on_voice_state_update(self, data: dict) -> None:
        """
        Forward a VOICE_STATE_UPDATE to the connection.

        Parameters
        ----------
        data:
            The raw voice state update payload.
        """
        self.connection.on_voice_state_update(data)

    def on_voice_server_update(self, data: dict) -> None:
        """
        Forward a VOICE_SERVER_UPDATE to the connection.

        Parameters
        ----------
        data:
            The raw voice server update payload.
        """
        self.connection.on_voice_server_update(data)

    async def speak(self, speaking: bool = True) -> None:
        """
        Send the SPEAKING frame to the voice gateway.

        Parameters
        ----------
        speaking:
            Whether the bot is speaking.
        """
        if self.connection.socket is None or self.connection.ssrc is None:
            return
        await self.connection.socket.send_speaking(1 if speaking else 0, ssrc=self.connection.ssrc)

    def _get_encoder(self) -> "Encoder":
        """
        Return the cached Opus encoder, creating it on first use.

        Returns
        -------
            The Opus encoder for this client.
        """
        if self._encoder is None:
            from .opus import Encoder

            self._encoder = Encoder()
        return self._encoder

    def send_audio_packet(self, data: bytes, *, encode: bool = True) -> None:
        """
        Frame, encrypt, and transmit a single audio packet over UDP.

        Parameters
        ----------
        data:
            The audio payload: PCM when ``encode`` is ``True`` else a raw Opus packet.
        encode:
            Whether ``data`` is PCM that must be Opus-encoded first.
        """
        connection = self.connection
        if connection.encryptor is None or connection.transport is None or connection.ssrc is None:
            return

        opus = self._get_encoder().encode(data) if encode else data

        # DAVE end-to-end encryption applies to the Opus payload before RTP framing.
        if connection.can_encrypt():
            opus = connection.dave_encrypt_opus(opus)

        connection.sequence = (connection.sequence + 1) % (2 ** 16)

        header = bytearray(12)
        struct.pack_into(">BBHII", header, 0, 0x80, 0x78, connection.sequence, connection.timestamp, connection.ssrc)

        connection.timestamp = (connection.timestamp + 960) % (2 ** 32)

        packet = connection.encryptor.encrypt(bytes(header), opus)

        try:
            connection.transport.sendto(packet)
        except OSError:
            _log.debug(f"Failed to send audio packet for guild {self.guild_id}")

    def play(
        self,
        audio: "AudioSourceInput",
        *,
        after: Callable[[Exception | None], object] | None = None
    ) -> None:
        """
        Play an audio source over the connection.

        Parameters
        ----------
        audio:
            The audio source, path, bytes, or stream to play.
        after:
            A callback invoked with any error once playback finishes.
        """
        from .player import AudioPlayer, _resolve_source

        if self._player is not None:
            self._player.stop()

        source = _resolve_source(audio)
        player = AudioPlayer(source, self, after=after)
        self._player = player
        player.start()

    def pause(self) -> None:
        """ Pause the current playback. """
        if self._player is not None:
            self._player.pause()

    def resume(self) -> None:
        """ Resume paused playback. """
        if self._player is not None:
            self._player.resume()

    def stop(self) -> None:
        """ Stop the current playback. """
        if self._player is not None:
            self._player.stop()
            self._player = None

    def is_playing(self) -> bool:
        """ Whether audio is currently playing. """
        return self._player is not None and self._player.is_playing()

    def is_paused(self) -> bool:
        """ Whether playback is currently paused. """
        return self._player is not None and self._player.is_paused()

    def listen(self, sink: "AudioSink") -> None:
        """
        Start receiving voice into the given sink.

        Parameters
        ----------
        sink:
            The audio sink to write received audio into.
        """
        from .receiver import VoiceReceiver

        if self._receiver is None:
            self._receiver = VoiceReceiver(self)
        self._receiver.start(sink)

    def stop_listening(self) -> None:
        """ Stop receiving voice. """
        if self._receiver is not None:
            self._receiver.stop()

    def is_listening(self) -> bool:
        """ Whether the client is currently receiving voice. """
        return self._receiver is not None and self._receiver.is_listening()
