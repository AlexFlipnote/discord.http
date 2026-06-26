import asyncio
import logging

from typing import TYPE_CHECKING

from ..utils import URL, ExponentialBackoff
from .dave import DaveManager, has_dave
from .encryptor import Encryptor
from .enums import SUPPORTED_MODES
from .gateway_udp import VoiceUDPProtocol, create_udp
from .socket import VoiceCloseCode, VoiceSocket

if TYPE_CHECKING:
    from ..channel import PartialChannel
    from ..client import Client
    from .client import VoiceClient

__all__ = ("VoiceConnection",)

_log = logging.getLogger(__name__)


class VoiceConnection:
    """ The transport and control-plane state machine for a voice connection. """

    def __init__(self, voice_client: "VoiceClient"):
        self.voice_client: "VoiceClient" = voice_client
        """ The voice client that owns this connection. """

        self.guild_id: int = voice_client.guild_id
        """ The ID of the guild this connection is for. """

        self.channel_id: int | None = voice_client.channel.id
        """ The ID of the voice channel currently targeted. """

        self.user_id: int = voice_client.user_id
        """ The ID of the bot user. """

        self.socket: VoiceSocket | None = None
        """ The voice websocket, if open. """

        self.udp: VoiceUDPProtocol | None = None
        """ The UDP protocol, if connected. """

        self.transport: asyncio.DatagramTransport | None = None
        """ The UDP datagram transport, if connected. """

        self.encryptor: Encryptor | None = None
        """ The transport encryptor, once the secret key is known. """

        self.token: str | None = None
        """ The voice connection token from the voice server update. """

        self.endpoint: str | None = None
        """ The voice server endpoint host, without scheme or port. """

        self.session_id: str | None = None
        """ The voice session ID from the voice state update. """

        self.server_id: int | None = None
        """ The server (guild) ID from the voice server update. """

        self.ssrc: int | None = None
        """ The synchronisation source identifier assigned by the gateway. """

        self.secret_key: bytes | None = None
        """ The secret key used for transport encryption. """

        self.endpoint_ip: str | None = None
        """ The discovered external IP address. """

        self.endpoint_port: int | None = None
        """ The discovered external UDP port. """

        self.mode: str | None = None
        """ The negotiated encryption mode. """

        self.sequence: int = 0
        """ The RTP sequence counter. """

        self.timestamp: int = 0
        """ The RTP timestamp counter. """

        self.dave_session: "DaveManager | None" = None
        """ The DAVE/MLS session manager, if a protocol version was negotiated. """

        self.dave_protocol_version: int = 0
        """ The negotiated DAVE protocol version (0 if not in use). """

        self._state_event: asyncio.Event = asyncio.Event()
        self._server_event: asyncio.Event = asyncio.Event()
        self._ready_event: asyncio.Event = asyncio.Event()
        self._connected_event: asyncio.Event = asyncio.Event()
        # Set when the gateway acknowledges the bot leaving the channel
        # (VOICE_STATE_UPDATE with channel_id=None); used by the reconnect
        # bounce to confirm the leave before rejoining.
        self._left_event: asyncio.Event = asyncio.Event()

        self._reconnect: bool = True
        self._reconnect_on_session_invalid: bool = False
        self._self_mute: bool = False
        self._self_deaf: bool = False
        self._closing: bool = False
        self._reconnect_task: asyncio.Task | None = None
        # Built lazily on first use so the backoff base/max_delay can be read
        # from the client (mirroring how voice_reconnect_attempts is read).
        self._backoff: ExponentialBackoff | None = None

    @property
    def backoff(self) -> ExponentialBackoff:
        """ The exponential backoff for reconnects, built lazily from client settings. """
        if self._backoff is None:
            self._backoff = ExponentialBackoff(
                base=self.client.voice_reconnect_base,
                max_delay=self.client.voice_reconnect_max_delay,
            )
        return self._backoff

    @property
    def client(self) -> "Client":
        """ The bot client that owns this voice connection. """
        return self.voice_client.bot

    @property
    def latency(self) -> float:
        """ The latency of the most recent voice heartbeat, in seconds. """
        if self.socket is None:
            return float("inf")
        return self.socket.latency

    @property
    def average_latency(self) -> float:
        """ The average latency of recent voice heartbeats, in seconds. """
        if self.socket is None:
            return float("inf")
        return self.socket.average_latency

    @property
    def voice_privacy_code(self) -> str | None:
        """ The DAVE voice privacy code, if a DAVE session is active. """
        if self.dave_session is None:
            return None
        return self.dave_session.voice_privacy_code

    def is_connected(self) -> bool:
        """ Whether the connection has completed its handshake. """
        return self._connected_event.is_set()

    async def connect(
        self,
        *,
        timeout: float = 30.0,
        reconnect: bool = True,
        reconnect_on_session_invalid: bool = False,
        self_deaf: bool = False,
        self_mute: bool = False
    ) -> None:
        """ Establish the full voice connection, resetting the reconnect backoff. """
        await self._connect(
            timeout=timeout,
            reconnect=reconnect,
            reconnect_on_session_invalid=reconnect_on_session_invalid,
            self_deaf=self_deaf,
            self_mute=self_mute,
        )

    async def _connect(
        self,
        *,
        timeout: float = 30.0,
        reconnect: bool = True,
        reconnect_on_session_invalid: bool = False,
        self_deaf: bool = False,
        self_mute: bool = False,
        preserve_backoff: bool = False
    ) -> None:
        """ Drive the full handshake, optionally preserving the reconnect backoff. """
        client = self.client

        shard_id = client.get_shard_by_guild_id(self.guild_id)
        if shard_id is None:
            raise RuntimeError(f"Could not resolve a shard for guild {self.guild_id}")

        shard = client.gateway.get_shard(shard_id) if client.gateway else None
        if shard is None:
            raise RuntimeError(f"Could not resolve shard {shard_id} for guild {self.guild_id}")

        self._reconnect = reconnect
        self._reconnect_on_session_invalid = reconnect_on_session_invalid
        self._self_mute = self_mute
        self._self_deaf = self_deaf
        self._closing = False

        # Only reset the exponential backoff on a genuinely fresh/initial
        # connect. The reconnect loop in _full_reconnect() drives its own
        # backoff and passes preserve_backoff=True so that each retry's
        # _connect() call does NOT reset it -- otherwise the delay would never
        # grow and every attempt would sleep the base delay.
        if not preserve_backoff:
            self.backoff.reset()

        self._state_event.clear()
        self._server_event.clear()
        self._ready_event.clear()
        self._connected_event.clear()

        # Join the voice client's channel, which is the authoritative target.
        # Do NOT use self.channel_id here: the reconnect bounce sends op4 with
        # channel_id=None and the gateway echoes a VOICE_STATE_UPDATE that
        # clears self.channel_id, so reading it could rejoin the wrong channel.
        await shard.change_voice_state(
            guild_id=self.guild_id,
            channel_id=self.voice_client.channel.id,
            self_mute=self_mute,
            self_deaf=self_deaf,
        )

        await asyncio.wait_for(self._wait_for_handshake(), timeout)

    async def _wait_for_handshake(self) -> None:
        """ Wait for the gateway handshake then drive the voice socket to connected. """
        await self._state_event.wait()
        await self._server_event.wait()

        self.socket = VoiceSocket(self)
        await self.socket.connect()

        await self._connected_event.wait()

    def _on_socket_closed(self, close_code: int | None) -> None:
        """ React to the voice websocket closing by deciding whether to reconnect. """
        if self._closing:
            return

        if self._reconnect_task is not None and not self._reconnect_task.done():
            return

        self._reconnect_task = asyncio.create_task(
            self._handle_close(close_code),
            name=f"discord.http/voice/connection-{self.guild_id}/reconnect"
        )

    async def _handle_close(self, close_code: int | None) -> None:
        """ Drive reconnect/resume logic based on the voice gateway close code. """
        if close_code in (VoiceCloseCode.disconnected, VoiceCloseCode.call_terminated):
            _log.debug(f"Voice connection for guild {self.guild_id} disconnected (code {close_code}); tearing down")
            await self._teardown_and_remove()
            return

        if close_code == VoiceCloseCode.rate_limited:
            _log.warning(f"Voice connection for guild {self.guild_id} was rate limited (code {close_code}); not reconnecting")
            await self._teardown_and_remove()
            return

        if close_code == VoiceCloseCode.voice_server_crashed:
            _log.debug(f"Voice server for guild {self.guild_id} crashed (code {close_code}); resuming")
            await self._resume()
            return

        if close_code == VoiceCloseCode.session_invalid:
            # Discord invalidates the session (4006) most commonly when another
            # member leaves/rejoins and the DAVE/MLS group is rebuilt. The bot is
            # still in the channel, so reconnecting only helps if the caller opted
            # in; otherwise we disconnect rather than retry-and-time-out.
            if not (self._reconnect and self._reconnect_on_session_invalid):
                _log.debug(f"Voice session for guild {self.guild_id} invalidated (code {close_code}); disconnecting")
                await self._teardown_and_remove()
                return

            # Try a soft reconnect first: re-open the voice websocket and
            # re-IDENTIFY with the existing token/session, WITHOUT leaving the
            # channel. This avoids a visible disconnect/rejoin blip when the
            # credentials are still usable.
            _log.debug(f"Voice session for guild {self.guild_id} invalidated (code {close_code}); attempting soft reconnect")
            if await self._soft_reconnect():
                _log.debug(f"Voice connection for guild {self.guild_id} recovered without rejoining")
                return

            # The existing credentials are no longer usable; fall back to a full
            # reconnect that drops and re-acquires the gateway voice state.
            _log.debug(f"Soft reconnect for guild {self.guild_id} failed; falling back to rejoin")
            await self._full_reconnect(close_code, force_refresh=True)
            return

        if close_code in (VoiceCloseCode.normal, VoiceCloseCode.going_away):
            _log.debug(f"Voice connection for guild {self.guild_id} closed cleanly (code {close_code})")
            await self._teardown_and_remove()
            return

        if not self._reconnect:
            _log.debug(f"Voice connection for guild {self.guild_id} closed (code {close_code}); reconnect disabled")
            await self._teardown_and_remove()
            return

        await self._full_reconnect(close_code)

    async def _resume(self) -> None:
        """ Re-open the voice websocket and RESUME (op 7) the existing session. """
        if self.socket is not None:
            self.socket._request_close()
            await self.socket.close()

        try:
            self._connected_event.clear()
            self.socket = VoiceSocket(self)
            await self.socket.connect(resume=True)
        except Exception as exc:
            _log.debug(f"Voice resume for guild {self.guild_id} failed; falling back to full reconnect", exc_info=exc)
            await self._full_reconnect(int(VoiceCloseCode.voice_server_crashed))

    async def _soft_reconnect(self, timeout: float = 10.0) -> bool:
        """ Re-open the voice websocket and re-IDENTIFY without leaving the channel. """
        if not (self.session_id and self.token and self.endpoint):
            return False

        # Tear down the old socket/UDP locally WITHOUT sending op4, so the gateway
        # keeps our voice state and we can reuse the session id and token.
        if self.socket is not None:
            self.socket._request_close()
            await self.socket.close()
            self.socket = None

        if self.transport is not None:
            self.transport.close()
            self.transport = None
        self.udp = None

        self._ready_event.clear()
        self._connected_event.clear()

        try:
            self.socket = VoiceSocket(self)
            await self.socket.connect()
            await asyncio.wait_for(self._connected_event.wait(), timeout)
        except Exception as exc:
            _log.debug(f"Soft reconnect for guild {self.guild_id} did not complete", exc_info=exc)
            return False

        return True

    async def _full_reconnect(self, close_code: int | None, *, force_refresh: bool = False) -> None:
        """ Re-issue op4 and run a fresh handshake, retrying with exponential backoff. """
        if self.socket is not None:
            self.socket._request_close()
            await self.socket.close()
            self.socket = None

        if self.transport is not None:
            self.transport.close()
            self.transport = None
        self.udp = None

        # Each attempt below deliberately re-issues op4 (change_voice_state) via
        # _connect(..., preserve_backoff=True). The backoff is reset once here
        # and then grows across attempts (_connect() skips resetting it).
        self.backoff.reset()

        max_attempts = self.client.voice_reconnect_attempts

        for attempt in range(1, max_attempts + 1):
            if self._closing:
                return

            delay = self.backoff.delay()
            _log.debug(
                f"Reconnecting voice for guild {self.guild_id} (close code {close_code}), "
                f"attempt {attempt}/{max_attempts} in {delay:.2f}s"
            )
            await asyncio.sleep(delay)

            try:
                if force_refresh:
                    # Force Discord to allocate a fresh voice server before
                    # rejoining (only needed for the 4006 leave/rejoin fallback).
                    await self._force_voice_refresh()
                await self._connect(
                    reconnect=self._reconnect,
                    reconnect_on_session_invalid=self._reconnect_on_session_invalid,
                    self_deaf=self._self_deaf,
                    self_mute=self._self_mute,
                    # Preserve the growing backoff across reconnect attempts.
                    preserve_backoff=True,
                )
            except Exception as exc:
                _log.debug(f"Voice reconnect attempt {attempt} for guild {self.guild_id} failed", exc_info=exc)
                continue
            else:
                _log.debug(f"Voice connection for guild {self.guild_id} reconnected")
                return

        _log.error(f"Voice connection for guild {self.guild_id} could not reconnect after {max_attempts} attempts; tearing down")
        await self._teardown_and_remove()

    async def _force_voice_refresh(self) -> None:
        """ Drop the gateway voice state so Discord re-allocates a fresh voice server. """
        client = self.client
        shard_id = client.get_shard_by_guild_id(self.guild_id)
        shard = client.gateway.get_shard(shard_id) if (client.gateway and shard_id is not None) else None
        if shard is None:
            return

        self._left_event.clear()
        try:
            await shard.change_voice_state(guild_id=self.guild_id, channel_id=None)
        except Exception as exc:
            _log.debug(f"Failed to send voice-state reset for guild {self.guild_id}", exc_info=exc)
            return

        try:
            await asyncio.wait_for(self._left_event.wait(), timeout=5.0)
        except TimeoutError:
            # No leave ack arrived (e.g. the bot was already out); a short settle
            # still lets the gateway register the reset before we rejoin.
            await asyncio.sleep(0.25)

    async def _teardown_and_remove(self) -> None:
        """ Tear down the connection and remove the voice client from the registry. """
        try:
            await self.voice_client.disconnect(force=True)
        except Exception as exc:
            _log.debug(f"Error during voice teardown for guild {self.guild_id}", exc_info=exc)

    def on_voice_state_update(self, data: dict) -> None:
        """ Handle a VOICE_STATE_UPDATE for the bot. """
        self.session_id = data.get("session_id") or self.session_id

        channel_id = data.get("channel_id")
        self.channel_id = int(channel_id) if channel_id is not None else None

        # Track leave/rejoin so the reconnect bounce can await the leave ack.
        if self.channel_id is None:
            self._left_event.set()
        else:
            self._left_event.clear()

        if self.session_id is not None:
            self._state_event.set()

    def on_voice_server_update(self, data: dict) -> None:
        """ Handle a VOICE_SERVER_UPDATE for the guild. """
        self.token = data.get("token")

        endpoint = data.get("endpoint")
        if endpoint:
            # Discord sends the endpoint as "host:port" without a scheme, and the
            # port is NOT always 443 (e.g. "c-ams20-....discord.media:2053"). The
            # token/session are bound to that specific host:port, so we MUST keep
            # the port intact -- connecting to host:443 instead reaches a
            # different voice server instance and Discord closes the socket with
            # 4006 "Session is no longer valid".
            #
            # ``urlparse`` (which ``utils.URL`` wraps) treats a bare "host:port"
            # as scheme:path, so we normalise by stripping any existing scheme
            # and prepending "wss://" before parsing, then reconstruct the
            # schemeless host[:port] string that self.endpoint is meant to hold.
            host_port = endpoint.rstrip("/")
            for scheme in ("wss://", "https://"):
                if host_port.startswith(scheme):
                    host_port = host_port[len(scheme):]
                    break

            url = URL("wss://" + host_port)
            if url.port is not None:
                self.endpoint = f"{url.host}:{url.port}"
            else:
                self.endpoint = url.host or host_port

        server_id = data.get("guild_id") or data.get("server_id")
        self.server_id = int(server_id) if server_id is not None else None

        if self.token is not None and self.endpoint is not None:
            self._server_event.set()

    async def on_ready(self, data: dict) -> None:
        """ Handle the voice READY (op 2): set up UDP and select the protocol. """
        self.ssrc = int(data["ssrc"])
        ip = data["ip"]
        port = int(data["port"])
        modes = data.get("modes", [])

        self.mode = next((m for m in SUPPORTED_MODES if m in modes), None)
        if self.mode is None:
            raise RuntimeError(
                "Discord advertised no encryption mode supported by this library; "
                f"offered {modes}, supported {list(SUPPORTED_MODES)}"
            )

        self.transport, self.udp = await create_udp(self, ip, port)

        discovered_ip, discovered_port = await self.udp.discover_ip(self.ssrc)
        self.endpoint_ip = discovered_ip
        self.endpoint_port = discovered_port

        self._ready_event.set()

        if self.socket is not None:
            await self.socket.send_select_protocol(discovered_ip, discovered_port, self.mode)

    async def on_session_description(self, data: dict) -> None:
        """ Handle the SESSION_DESCRIPTION (op 4): build the encryptor. """
        secret_key = bytes(data["secret_key"])
        self.secret_key = secret_key
        self.mode = data.get("mode", self.mode)
        self.encryptor = Encryptor(secret_key)

        dave_version = int(data.get("dave_protocol_version", 0) or 0)
        self.dave_protocol_version = dave_version
        if dave_version > 0:
            await self.reinit_dave_session()
        elif self.dave_session is not None:
            # DAVE was negotiated off (version 0) but a prior connection left a
            # session behind. Tear down the MLS session so can_encrypt() and the
            # opus wrappers don't keep using stale E2EE state. DaveManager has no
            # dedicated close/cleanup; reinit(0) clears its internal session, then
            # we drop the reference.
            await self.dave_session.reinit(0)
            self.dave_session = None

        self._connected_event.set()

    async def on_speaking(self, data: dict) -> None:
        """ Handle a SPEAKING (op 5) frame from another user. """
        receiver = self.voice_client._receiver
        if receiver is None:
            return

        ssrc = data.get("ssrc")
        user_id = data.get("user_id")
        if ssrc is not None and user_id is not None:
            receiver.add_ssrc(int(ssrc), int(user_id))

    async def on_resumed(self, data: dict) -> None:  # noqa: ARG002
        """ Handle the RESUMED (op 9) frame. """
        _log.debug(f"Voice connection for guild {self.guild_id} resumed")
        # A successful RESUMED frame means the connection is live again. _resume()
        # cleared _connected_event when re-opening the socket, so re-set it here;
        # otherwise is_connected() would stay False forever after a server crash.
        self._connected_event.set()

    async def on_dave_binary(self, opcode: int, payload: bytes) -> None:
        """ Handle an inbound binary DAVE frame. """
        if not has_dave:
            _log.warning(f"Received DAVE binary op {opcode} but the davey library is not available")
            return

        if self.dave_session is None:
            await self.reinit_dave_session()

        if self.dave_session is not None:
            await self.dave_session.handle_binary(opcode, payload)

    async def on_dave_json(self, opcode: int, data: dict) -> None:
        """ Handle an inbound JSON DAVE control op (transition/epoch, ops 21/22/24). """
        if not has_dave:
            _log.warning(f"Received DAVE JSON op {opcode} but the davey library is not available")
            return

        if self.dave_session is None:
            await self.reinit_dave_session()

        if self.dave_session is not None:
            await self.dave_session.handle_json(opcode, data)

    async def reinit_dave_session(self) -> None:
        """ Create or reset the DAVE session for the negotiated protocol version. """
        if not has_dave:
            if self.dave_protocol_version > 0:
                raise RuntimeError(
                    "Discord negotiated a DAVE protocol version but the davey library is not installed"
                )
            return

        if self.dave_session is None:
            self.dave_session = DaveManager(self)

        await self.dave_session.reinit(self.dave_protocol_version)

    def can_encrypt(self) -> bool:
        """ Whether a DAVE session is ready to encrypt Opus payloads. """
        return self.dave_session is not None and self.dave_session.ready

    def dave_encrypt_opus(self, opus: bytes) -> bytes:
        """ Encrypt an Opus payload through the DAVE session, or return it unchanged when inactive. """
        if self.dave_session is None or not self.dave_session.ready:
            return opus
        return self.dave_session.encrypt_opus(opus)

    def dave_decrypt_opus(self, user_id: int, opus: bytes) -> bytes:
        """ Decrypt an Opus payload through the DAVE session, or return it unchanged when inactive. """
        if self.dave_session is None or not self.dave_session.ready:
            return opus
        return self.dave_session.decrypt_opus(user_id, opus)

    def _cancel_reconnect_task(self) -> None:
        """ Cancel any pending reconnect task, unless it is the current task. """
        if self._reconnect_task is not None and self._reconnect_task is not asyncio.current_task():
            self._reconnect_task.cancel()
            self._reconnect_task = None

    def _clear_transport_state(self) -> None:
        """ Drop the transport/UDP/encryption state and clear the ready/connected events. """
        if self.transport is not None:
            self.transport.close()
            self.transport = None

        self.udp = None
        self.encryptor = None
        self.secret_key = None
        self.ssrc = None
        self._connected_event.clear()
        self._ready_event.clear()

    async def disconnect(self, *, force: bool = True) -> None:
        """ Tear down the voice connection, notifying the gateway via op4. """
        self._closing = True
        self._cancel_reconnect_task()

        # Request the close before sending op4 so the close handler does not
        # treat the impending socket close as an unexpected disconnect.
        if self.socket is not None:
            self.socket._request_close()

        client = self.client
        try:
            shard_id = client.get_shard_by_guild_id(self.guild_id)
            shard = client.gateway.get_shard(shard_id) if (client.gateway and shard_id is not None) else None
            if shard is not None:
                await shard.change_voice_state(guild_id=self.guild_id, channel_id=None)
        except Exception as exc:
            if not force:
                raise
            _log.debug(f"Failed to send voice disconnect for guild {self.guild_id}", exc_info=exc)

        if self.socket is not None:
            await self.socket.close()
            self.socket = None

        self._clear_transport_state()

    async def close_transport(self) -> None:
        """ Close the websocket and UDP transport without notifying the gateway. """
        # Used when the owning shard has been reset or killed, so op4 can no
        # longer be sent. Cancels any pending reconnect and clears local state.
        self._closing = True
        self._cancel_reconnect_task()

        if self.socket is not None:
            self.socket._request_close()
            await self.socket.close()
            self.socket = None

        self._clear_transport_state()

    async def move_to(self, channel: "PartialChannel") -> None:
        """ Move the connection to a different voice channel. """
        client = self.client

        shard_id = client.get_shard_by_guild_id(self.guild_id)
        shard = client.gateway.get_shard(shard_id) if (client.gateway and shard_id is not None) else None
        if shard is None:
            raise RuntimeError(f"Could not resolve a shard for guild {self.guild_id}")

        self.channel_id = channel.id
        await shard.change_voice_state(guild_id=self.guild_id, channel_id=channel.id)
