import asyncio
import logging
import struct
import time

import orjson

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from collections import deque
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from enum import IntEnum

from .enums import VoiceOp

if TYPE_CHECKING:
    from .connection import VoiceConnection

__all__ = ("VoiceCloseCode", "VoiceSocket")

_log = logging.getLogger(__name__)


class VoiceCloseCode(IntEnum):
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
        self._own_session: bool = False
        self._session: ClientSession | None = None

        self._heartbeat_interval: float = 0.0
        self._heartbeat_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None

        self._out_seq: int = 0
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

    def _get_session(self) -> ClientSession:
        """
        Return a usable aiohttp session, reusing the bot's if reachable.

        Returns
        -------
            The shared HTTP session, or a freshly created one owned by this socket.
        """
        try:
            session = self.connection.voice_client.client.state.http.session
        except AttributeError:
            session = None

        if session is not None:
            return session

        self._own_session = True
        self._session = ClientSession()
        return self._session

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
        session = self._get_session()
        endpoint = self.connection.endpoint
        self.ws = await session.ws_connect(f"wss://{endpoint}/?v=8")

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
            async for msg in ws:
                if msg.type is WSMsgType.TEXT:
                    self._dispatch_text(msg.data)

                elif msg.type is WSMsgType.BINARY:
                    self._dispatch_binary(msg.data)

                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                    _log.debug("Voice socket for guild %s received close frame", self.connection.guild_id)
                    break

                elif msg.type is WSMsgType.ERROR:
                    _log.warning("Voice socket for guild %s received error: %s", self.connection.guild_id, msg.data)
                    break

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            _log.debug("Voice socket for guild %s receive loop ended", self.connection.guild_id, exc_info=exc)

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
            voice_op = VoiceOp(op)
        except ValueError:
            _log.debug("Voice socket for guild %s received unknown op %s", self.connection.guild_id, op)
            return

        match voice_op:
            case VoiceOp.hello:
                self._heartbeat_interval = float(data["heartbeat_interval"]) / 1000
                self._start_heartbeat()
                if self._resuming:
                    self._schedule(self.send_resume())
                else:
                    self._schedule(self.send_identify())

            case VoiceOp.ready:
                self._schedule(self.connection.on_ready(data))

            case VoiceOp.session_description:
                self._schedule(self.connection.on_session_description(data))

            case VoiceOp.speaking:
                self._schedule(self.connection.on_speaking(data))

            case VoiceOp.heartbeat_ack:
                if self._last_send:
                    self._latencies.append(time.perf_counter() - self._last_send)

            case VoiceOp.resumed:
                self._schedule(self.connection.on_resumed(data))

            case _:
                _log.debug("Voice socket for guild %s received unhandled op %s", self.connection.guild_id, voice_op)

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
            _log.error("Error in voice socket handler for guild %s", self.connection.guild_id, exc_info=exc)

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
                await self._send_heartbeat()
                await asyncio.sleep(self._heartbeat_interval)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _log.debug("Voice heartbeat for guild %s stopped", self.connection.guild_id, exc_info=exc)

    async def _send_heartbeat(self) -> None:
        """ Send a single heartbeat frame, recording the send time for latency. """
        self._last_send = time.perf_counter()
        nonce = int(time.time() * 1000)
        await self._send_json({
            "op": int(VoiceOp.heartbeat),
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
        await self.ws.send_bytes(orjson.dumps(payload))

    async def send_identify(self) -> None:
        """ Send the IDENTIFY (op 0) frame, advertising DAVE support. """
        from .dave import max_protocol_version

        await self._send_json({
            "op": int(VoiceOp.identify),
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
            "op": int(VoiceOp.select_protocol),
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
            "op": int(VoiceOp.speaking),
            "d": {
                "speaking": int(speaking),
                "delay": int(delay),
                "ssrc": int(ssrc),
            }
        })

    async def send_resume(self) -> None:
        """ Send the RESUME (op 7) frame to resume an interrupted session. """
        await self._send_json({
            "op": int(VoiceOp.resume),
            "d": {
                "server_id": str(self.connection.guild_id),
                "session_id": self.connection.session_id,
                "token": self.connection.token,
                "seq_ack": self.seq_ack,
            }
        })

    async def send_binary(self, opcode: int, payload: bytes) -> None:
        """
        Send a binary DAVE frame.

        Parameters
        ----------
        opcode:
            The voice opcode for the binary frame.
        payload:
            The binary payload to send after the opcode.
        """
        if self.ws is None or self.ws.closed:
            return

        self._out_seq = (self._out_seq + 1) & 0xFFFF
        frame = struct.pack(">H", 0) + bytes([opcode & 0xFF]) + payload
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

        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._own_session = False
