import asyncio
import logging
import struct
import time

import orjson

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from collections import deque
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from ..enums import BaseEnum
from .enums import VoiceOpType

if TYPE_CHECKING:
    from .connection import VoiceConnection

__all__ = ("VoiceCloseCode", "VoiceSocket")

_log = logging.getLogger(__name__)


class VoiceCloseCode(BaseEnum):
    """ The voice gateway websocket close codes that govern reconnect behaviour. """

    normal = 1000
    going_away = 1001
    disconnected = 4014
    voice_server_crashed = 4015
    unknown_encryption_mode = 4016
    bad_request = 4020
    rate_limited = 4021
    call_terminated = 4022


class VoiceSocket:
    """
    The voice gateway websocket connection.

    Handles the voice gateway protocol (version 8): the initial handshake,
    heartbeating, latency tracking, and dispatching of both JSON and binary
    (DAVE) frames to the owning :class:`VoiceConnection`.
    """

    def __init__(self, connection: "VoiceConnection"):
        self.connection: "VoiceConnection" = connection
        """ The voice connection that owns this socket. """

        self.ws: ClientWebSocketResponse | None = None
        """ The underlying websocket connection, if open. """

        self.seq_ack: int = -1
        """ The last sequence number received from the voice gateway. """

        self._closing: bool = False
        self._resuming: bool = False

        self._heartbeat_interval: float = 0.0
        self._heartbeat_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None

        self._last_send: float = 0.0
        self._latencies: deque[float] = deque(maxlen=20)

    @property
    def latency(self) -> float:
        """ The latency of the most recent heartbeat, in seconds, or ``inf`` if unknown. """
        if not self._latencies:
            return float("inf")
        return self._latencies[-1]

    @property
    def average_latency(self) -> float:
        """ The average latency over the last few heartbeats, in seconds, or ``inf`` if unknown. """
        if not self._latencies:
            return float("inf")
        return sum(self._latencies) / len(self._latencies)

    @property
    def session(self) -> ClientSession:
        """
        The shared aiohttp session from the bot's HTTP client.

        Returns
        -------
            The bot's HTTP session, reused for the voice websocket.

        Raises
        ------
        RuntimeError
            If the HTTP session is not available (the client is not running).
        """
        session = self.connection.voice_client.client.state.http.session
        if session is None:
            raise RuntimeError("HTTP session is not available; the client must be running to open a voice socket")
        return session

    async def connect(self, *, resume: bool = False) -> None:
        """
        Open the voice websocket and start the receive loop.

        Parameters
        ----------
        resume:
            Whether to RESUME (op 7) an existing session rather than IDENTIFY (op 0).
        """
        self._closing = False
        self._resuming = resume
        endpoint = self.connection.endpoint
        self.ws = await self.session.ws_connect(f"wss://{endpoint}/?v=8")

        self._receive_task = asyncio.create_task(
            self._receive_loop(),
            name=f"discord.http/voice/socket-{self.connection.guild_id}/receive"
        )

    async def _receive_loop(self) -> None:
        """ Continuously receive frames and dispatch them; never blocks on handlers. """
        ws = self.ws
        if ws is None:
            return

        close_code: int | None = None

        try:
            while True:
                msg = await ws.receive()

                if msg.type is WSMsgType.TEXT:
                    self._dispatch_text(msg.data)

                elif msg.type is WSMsgType.BINARY:
                    self._dispatch_binary(msg.data)

                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                    # Discord's close reason (msg.extra) is invaluable for diagnosing
                    # voice failures (e.g. "E2EE/DAVE protocol required" for 4017),
                    # so surface it alongside the code.
                    _log.debug(
                        f"Voice socket for guild {self.connection.guild_id} received close frame "
                        f"(code={msg.data!r}, reason={msg.extra!r})"
                    )
                    break

                elif msg.type is WSMsgType.ERROR:
                    _log.warning(f"Voice socket for guild {self.connection.guild_id} received error: {msg.data}")
                    break

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            _log.debug(f"Voice socket for guild {self.connection.guild_id} receive loop ended", exc_info=exc)

        close_code = ws.close_code

        if not self._closing:
            self.connection._on_socket_closed(close_code)

    def _request_close(self) -> None:
        """ Mark the socket as intentionally closing so the receive loop suppresses reconnect. """
        self._closing = True

    def _dispatch_text(self, raw: str | bytes) -> None:
        """
        Parse and dispatch a text frame by its voice opcode.

        Parameters
        ----------
        raw:
            The raw JSON text frame received from the voice gateway.
        """
        payload: dict = orjson.loads(raw)

        seq = payload.get("seq")
        if seq is not None:
            self.seq_ack = seq

        op = payload.get("op")
        data: dict = payload.get("d") or {}

        try:
            voice_op = VoiceOpType(op)
        except ValueError:
            _log.debug(f"Voice socket for guild {self.connection.guild_id} received unknown op {op}")
            return

        match voice_op:
            case VoiceOpType.hello:
                self._heartbeat_interval = float(data["heartbeat_interval"]) / 1000
                self._schedule(self._handle_hello())

            case VoiceOpType.ready:
                self._schedule(self.connection.on_ready(data))

            case VoiceOpType.session_description:
                self._schedule(self.connection.on_session_description(data))

            case VoiceOpType.speaking:
                self._schedule(self.connection.on_speaking(data))

            case VoiceOpType.heartbeat_ack:
                if self._last_send:
                    self._latencies.append(time.perf_counter() - self._last_send)

            case VoiceOpType.resumed:
                self._schedule(self.connection.on_resumed(data))

            case _:
                _log.debug(f"Voice socket for guild {self.connection.guild_id} received unhandled op {voice_op}")

    def _dispatch_binary(self, raw: bytes) -> None:
        """
        Parse and dispatch a binary DAVE frame.

        Parameters
        ----------
        raw:
            The raw binary frame: ``seq(2B >H) + opcode(1B) + payload``.
        """
        if len(raw) < 3:
            return

        seq, opcode = struct.unpack_from(">HB", raw, 0)
        payload = raw[3:]

        self.seq_ack = seq

        self._schedule(self.connection.on_dave_binary(opcode, payload))

    def _schedule(self, coro: Coroutine[Any, Any, Any]) -> None:
        """
        Schedule a coroutine as a task so the receive loop never blocks.

        Parameters
        ----------
        coro:
            The coroutine to run independently of the receive loop.
        """
        asyncio.create_task(  # noqa: RUF006
            self._guard(coro),
            name=f"discord.http/voice/socket-{self.connection.guild_id}/dispatch"
        )

    async def _guard(self, coro: Coroutine[Any, Any, Any]) -> None:
        """
        Run a scheduled coroutine, logging any exception it raises.

        Parameters
        ----------
        coro:
            The coroutine to await.
        """
        try:
            await coro
        except Exception as exc:
            _log.error(f"Error in voice socket handler for guild {self.connection.guild_id}", exc_info=exc)

    async def _handle_hello(self) -> None:
        """
        React to HELLO (op 8): authenticate, then start heartbeating.

        IDENTIFY/RESUME MUST be the first payload sent on the voice gateway.
        The heartbeat loop emits a heartbeat (op 3) immediately, so it can only
        be started *after* authentication has been sent; otherwise Discord sees
        a payload before IDENTIFY and closes the socket with code 4003
        ("Not authenticated").
        """
        if self._resuming:
            await self.send_resume()
        else:
            await self.send_identify()

        self._start_heartbeat()

    def _start_heartbeat(self) -> None:
        """ (Re)start the heartbeat task using the negotiated interval. """
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name=f"discord.http/voice/socket-{self.connection.guild_id}/heartbeat"
        )

    async def _heartbeat_loop(self) -> None:
        """ Send a heartbeat (op 3) every interval until cancelled. """
        try:
            while True:
                # Sleep *before* the first beat: the voice gateway must complete
                # the IDENTIFY -> READY -> SESSION_DESCRIPTION handshake without
                # any heartbeat interleaved. Sending op 3 before READY makes
                # Discord invalidate the session (close code 4006). This mirrors
                # discord.py's voice keep-alive, which also waits one interval.
                await asyncio.sleep(self._heartbeat_interval)
                await self._send_heartbeat()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _log.debug(f"Voice heartbeat for guild {self.connection.guild_id} stopped", exc_info=exc)

    async def _send_heartbeat(self) -> None:
        """ Send a single heartbeat frame, recording the send time for latency. """
        self._last_send = time.perf_counter()
        nonce = int(time.time() * 1000)
        await self._send_json({
            "op": int(VoiceOpType.heartbeat),
            "d": {
                "t": nonce,
                "seq_ack": self.seq_ack,
            }
        })

    async def _send_json(self, payload: dict) -> None:
        """
        Send a JSON frame over the websocket.

        Parameters
        ----------
        payload:
            The payload to serialise and send.
        """
        if self.ws is None or self.ws.closed:
            return
        # JSON control frames MUST be sent as text frames: the voice gateway
        # reserves binary frames for DAVE/E2EE opcodes (see ``send_binary`` and
        # ``_dispatch_binary``). Sending JSON via ``send_bytes`` makes Discord
        # treat IDENTIFY as a malformed DAVE frame, so it never replies with
        # READY/SESSION_DESCRIPTION and the handshake times out.
        await self.ws.send_str(orjson.dumps(payload).decode("utf-8"))

    async def send_identify(self) -> None:
        """ Send the IDENTIFY (op 0) frame, advertising DAVE support. """
        from .dave import max_protocol_version

        await self._send_json({
            "op": int(VoiceOpType.identify),
            "d": {
                "server_id": str(self.connection.guild_id),
                "user_id": str(self.connection.user_id),
                "session_id": self.connection.session_id,
                "token": self.connection.token,
                "max_dave_protocol_version": max_protocol_version(),
            }
        })

    async def send_select_protocol(self, ip: str, port: int, mode: str) -> None:
        """
        Send the SELECT_PROTOCOL (op 1) frame after IP discovery.

        Parameters
        ----------
        ip:
            The externally discovered IP address.
        port:
            The externally discovered UDP port.
        mode:
            The negotiated encryption mode.
        """
        await self._send_json({
            "op": int(VoiceOpType.select_protocol),
            "d": {
                "protocol": "udp",
                "data": {
                    "address": ip,
                    "port": port,
                    "mode": mode,
                }
            }
        })

    async def send_speaking(self, speaking: int, *, ssrc: int, delay: int = 0) -> None:
        """
        Send the SPEAKING (op 5) frame.

        Parameters
        ----------
        speaking:
            The speaking bitflag (1 to indicate microphone audio).
        ssrc:
            The SSRC of the connection.
        delay:
            The voice delay, in milliseconds.
        """
        await self._send_json({
            "op": int(VoiceOpType.speaking),
            "d": {
                "speaking": int(speaking),
                "delay": int(delay),
                "ssrc": int(ssrc),
            }
        })

    async def send_resume(self) -> None:
        """ Send the RESUME (op 7) frame to resume an interrupted session. """
        await self._send_json({
            "op": int(VoiceOpType.resume),
            "d": {
                "server_id": str(self.connection.guild_id),
                "session_id": self.connection.session_id,
                "token": self.connection.token,
                "seq_ack": self.seq_ack,
            }
        })

    async def send_transition_ready(self, transition_id: int) -> None:
        """
        Send the DAVE TRANSITION_READY (op 23) acknowledgement.

        This is a JSON control frame (not a binary DAVE frame): it carries the
        ``transition_id`` as JSON, matching the voice gateway protocol.

        Parameters
        ----------
        transition_id:
            The id of the transition being acknowledged.
        """
        await self._send_json({
            "op": int(VoiceOpType.dave_transition_ready),
            "d": {
                "transition_id": transition_id,
            }
        })

    async def send_binary(self, opcode: int, payload: bytes) -> None:
        """
        Send a binary DAVE frame.

        Outbound binary frames are framed as ``opcode(1B) + payload`` with NO
        sequence prefix. This is asymmetric with *inbound* binary frames, which
        Discord prefixes with a 2-byte sequence number (``seq(2B) + opcode(1B) +
        payload``, handled in :meth:`_dispatch_binary`). Prefixing outbound
        frames with the 2-byte sequence makes Discord read the leading ``0x00``
        byte as opcode 0 (IDENTIFY) and close the socket with 4005
        ("Already authenticated").

        Parameters
        ----------
        opcode:
            The voice opcode for the binary frame.
        payload:
            The binary payload to send after the opcode.
        """
        if self.ws is None or self.ws.closed:
            return

        frame = bytes([opcode & 0xFF]) + payload
        await self.ws.send_bytes(frame)

    async def close(self) -> None:
        """ Cancel the background tasks and close the websocket. """
        self._closing = True

        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._receive_task is not None:
            self._receive_task.cancel()
            self._receive_task = None

        if self.ws is not None and not self.ws.closed:
            await self.ws.close()
        self.ws = None
