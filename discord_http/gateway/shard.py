import asyncio
import logging
import orjson
import sys
import time
import zlib

from aiohttp import WSMsgType, ClientWebSocketResponse, ClientSession
from collections.abc import Callable
from datetime import datetime
from typing import Any, TYPE_CHECKING, overload, Literal

from .. import utils
from ..object import Snowflake

from .enums import PayloadType, ShardCloseType
from .flags import GatewayCacheFlags, GatewayCapabilities, Intents
from .object import PlayingStatus
from .parser import Parser, GuildMembersChunk

if TYPE_CHECKING:
    from ..client import Client
    from ..guild import Guild, PartialGuild
    from ..member import Member

DEFAULT_GATEWAY = utils.URL("wss://gateway.discord.gg/")
_log = logging.getLogger("discord_http")

__all__ = (
    "Shard",
    "ShardEventPayload",
)


class ShardEventPayload:
    """ Represents the payload for shard events. """

    __slots__ = (
        "close_type",
        "exception",
        "id",
        "reason",
        "shard",
    )

    def __init__(
        self,
        shard: "Shard",
        *,
        reason: str | None = None,
        exception: Exception | None = None,
        close_type: ShardCloseType | None = None,
    ):
        self.id: int = shard.shard_id
        """ The ID of the shard that the event is related to. """

        self.shard: "Shard" = shard
        """ The shard that the event is related to. """

        self.reason: str | None = reason
        """ The reason for the event, if any. """

        self.exception: Exception | None = exception
        """ The exception that caused the event, if any. """

        self.close_type: ShardCloseType | None = close_type
        """ The type of close that caused the event, if any. """

    def __repr__(self) -> str:
        return f"<ShardEventPayload id={self.id} shard={self.shard} reason={self.reason}>"

    def is_dead(self) -> bool:
        """ Whether the shard is crashed or not. """
        return self.close_type == ShardCloseType.hard_crash

    def reconnect(self) -> None:
        """ Attempt to reconnect the shard. """
        if self.shard._connection is not None and not self.shard._connection.done():
            self.shard._connection.cancel()

        _log.debug(f"Shard {self.shard.shard_id} reconnecting")
        self.shard.connect()


class GatewayRatelimiter:
    """ Represents the ratelimiter for the gateway. """
    __slots__ = (
        "lock",
        "max",
        "per",
        "remaining",
        "shard_id",
        "window",
    )

    def __init__(
        self,
        shard_id: int,
        count: int = 110,
        per: float = 60.0
    ) -> None:
        self.shard_id: int = shard_id
        """ The ID of the shard that the ratelimiter is for. """

        self.max: int = count
        """ The maximum number of messages that can be sent in the current window. """

        self.remaining: int = count
        """ The number of messages remaining in the current window. """

        self.window: float = 0.0
        """ The start time of the current window. """

        self.per: float = per
        """ The length of the window in seconds. """

        self.lock: asyncio.Lock = asyncio.Lock()
        """ The lock for the ratelimiter, used to block when the ratelimit is hit. """

    def reset(self) -> None:
        """ Resets the ratelimiter. """
        self.remaining = self.max
        self.window = 0.0

    def is_ratelimited(self) -> bool:
        """ Returns whether the shard is currently ratelimited. """
        current = time.monotonic()
        if current > self.window + self.per:
            return False
        return self.remaining == 0

    def get_delay(self) -> float:
        """ Returns the number of seconds to wait before the next send, or 0.0 if not ratelimited. """
        current = time.monotonic()

        # Reset the window if the period has passed
        if current > self.window + self.per:
            self.remaining = self.max
            self.window = current

        if self.remaining > 0:
            self.remaining -= 1
            return 0.0

        # Return how much time is left until the window resets
        return self.per - (current - self.window)

    async def block(self) -> None:
        """ Acquires the lock and sleeps if the shard is ratelimited. """
        async with self.lock:
            retry_after = self.get_delay()
            if retry_after:
                _log.warning(
                    "WebSocket ratelimit hit on ShardID "
                    f"{self.shard_id}, waiting {retry_after:.2f}s..."
                )
                await asyncio.sleep(retry_after)
                _log.info(f"WebSocket ratelimit released on ShardID {self.shard_id}")


class Status:
    """ Represents the status of a shard. """
    __slots__ = (
        "_last_ack",
        "_last_heartbeat",
        "_last_recv",
        "_last_send",
        "gateway",
        "latency",
        "sequence",
        "session_id",
        "shard_id",
    )

    def __init__(self, shard_id: int):
        self.shard_id = shard_id
        """ The ID of the shard. """

        self.sequence: int | None = None
        """ The last sequence number received from the gateway, if any. """

        self.session_id: str | None = None
        """ The session ID of the shard, if any. """

        self.gateway = DEFAULT_GATEWAY
        """ The gateway URL for the shard. """

        self.latency: float = float("inf")
        """ The latency of the shard, in seconds. """

        now = time.perf_counter()
        self._last_ack: float = now
        self._last_send: float = now
        self._last_recv: float = now
        self._last_heartbeat: float | None = None

    @property
    def ping(self) -> float:
        """ The round-trip latency between the last send and receive, or 0.0 if not connected. """
        if not self.can_resume():
            return 0.0
        return self._last_recv - self._last_send

    def reset(self) -> None:
        """ Resets the shard status, clearing the session and sequence. """
        self.sequence = None
        self.session_id = None
        self.gateway = DEFAULT_GATEWAY

        self.latency = float("inf")

        now = time.perf_counter()
        self._last_ack = now
        self._last_send = now
        self._last_recv = now
        self._last_heartbeat = None

    def can_resume(self) -> bool:
        """ Returns whether the shard can resume its session. """
        return self.session_id is not None

    def is_zombied(self) -> bool:
        """ Returns whether the last heartbeat we sent was never acknowledged. """
        if self._last_heartbeat is None:
            return False
        return self._last_ack < self._last_heartbeat

    def reset_heartbeat(self) -> None:
        """ Clears heartbeat/ack tracking, used when a new physical connection is established. """
        now = time.perf_counter()
        self._last_ack = now
        self._last_heartbeat = None

    def update_sequence(self, sequence: int) -> None:
        """ Updates the last received sequence number. """
        self.sequence = sequence

    def update_ready_data(self, data: dict | None) -> None:
        """ Updates the session ID and resume gateway URL from a READY payload. """
        if data is None:
            # This should never really happen
            return

        self.session_id = data["session_id"]
        self.gateway = utils.URL(data["resume_gateway_url"])

    def get_payload(self) -> dict:
        """ Returns the heartbeat payload to send to the gateway. """
        return {
            "op": int(PayloadType.heartbeat),
            "d": self.sequence
        }

    def update_send(self) -> None:
        """ Records the current time as the last send timestamp. """
        self._last_send = time.perf_counter()

    def update_heartbeat(self) -> None:
        """ Records the current time as the last heartbeat timestamp. """
        self._last_heartbeat = time.perf_counter()

    def tick(self) -> None:
        """ Records the current time as the last receive timestamp. """
        self._last_recv = time.perf_counter()

    def ack(
        self,
        *,
        ignore_warning: bool = False
    ) -> None:
        """
        Acknowledges the heartbeat.

        Parameters
        ----------
        ignore_warning
            Whether to ignore the warning or not
            (This is only used before the shard is ready)
            ((If I find a way to fix it, I will remove this))
        """
        ack_time = time.perf_counter()
        self._last_ack = ack_time
        self.latency = ack_time - self._last_send

        if (
            self.latency > 10 and
            not ignore_warning
        ):
            _log.warning(f"Shard {self.shard_id} latency is {self.latency:.2f}s behind")


class Shard:
    """ Represents a shard for the gateway. """
    def __init__(
        self,
        bot: "Client",
        intents: Intents | None,
        shard_id: int,
        *,
        api_version: int,
        cache_flags: GatewayCacheFlags | None = None,
        shard_count: int | None = None,
        debug_events: bool = False,
    ):
        self.bot = bot
        """ The bot instance that the shard belongs to. """

        self.intents: Intents = intents or Intents.none()
        """ The intents that the shard is using, or `None` if not specified. """

        self.capabilities: GatewayCapabilities | None = bot.gateway_capabilities
        """ The opt-in Gateway capabilities bitfield to send in the Identify payload, if any. """

        self.cache_flags = cache_flags
        """ The cache flags that the shard is using, or `None` if not specified. """

        self.api_version = api_version
        """ The API version that the shard is using. """

        self.shard_id = shard_id
        """ The ID of the shard. """

        self.shard_count = shard_count
        """ The total number of shards, or `None` if not specified. """

        self.debug_events = debug_events
        """ Whether to debug events or not. """

        self.ws: ClientWebSocketResponse | None = None
        """ The websocket connection for the shard, if any. """

        # Session was already made before, pyright is wrong
        self.session: ClientSession = self.bot.state.http.session  # type: ignore
        """ The HTTP session for the shard. """

        self.parser = Parser(bot)
        """ The parser for the shard. """

        self.status = Status(shard_id)
        """ The status of the shard. """

        self.playing_status: PlayingStatus | None = bot.playing_status
        """ The playing status of the shard, if any. """

        self._ready: asyncio.Event = asyncio.Event()
        self._identified: asyncio.Event = asyncio.Event()
        self._ready_task: asyncio.Task | None = None
        self._guild_ready_timeout: float = float(bot.guild_ready_timeout)
        self._expected_guild_count: int = 0
        self._guild_create_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._ratelimiter: GatewayRatelimiter = GatewayRatelimiter(shard_id)

        self._connection = None
        self._should_kill = False
        self._reconnect_attempts: int = 0

        self._buffer: bytearray = bytearray()
        self._zlib: zlib._Decompress = zlib.decompressobj()

        self._heartbeat_interval: float = 41_250 / 1000  # 41.25 seconds
        self._close_code: int | None = None
        self._last_activity: datetime = utils.utcnow()

        self._parser_cache = {}
        self._special_handlers: dict[str, tuple[Callable, bool]] = {
            "GUILD_CREATE": (self._parse_guild_create, True),
            "GUILD_DELETE": (self._parse_guild_delete, False),
            "GUILD_MEMBERS_CHUNK": (self._parse_guild_members_chunk, True),
        }

    @property
    def url(self) -> str:
        """ The websocket url for the client. """
        if not isinstance(self.api_version, int):
            raise TypeError("api_version must be of type int")

        return str(self.status.gateway.update_query(
            v=self.api_version,
            encoding="json",
            compress="zlib-stream"
        ))

    def _reset_buffer(self) -> None:
        self._buffer = bytearray()
        self._zlib = zlib.decompressobj()

    def _reset_instance(self) -> None:
        self._reset_buffer()
        self.status.reset()

        self._close_code = None
        self._ready.clear()
        self._identified.clear()
        self._expected_guild_count = 0
        self._guild_create_queue = asyncio.Queue()

        if self._ready_task is not None and not self._ready_task.done():
            self._ready_task.cancel()
            self._ready_task = None

        for chunk_request in self.parser._chunk_requests.values():
            chunk_request.fail(
                ConnectionResetError("Shard connection was reset while waiting for a member chunk")
            )

        self.parser._chunk_requests.clear()

    def _is_fatal_close(self) -> bool:
        """ Check if the close code is completely unrecoverable. """
        code = self._close_code or (self.ws.close_code if self.ws else None)
        # 4004: Authentication failed
        # 4010: Invalid shard
        # 4011: Sharding required
        # 4012: Invalid API version
        # 4013: Invalid intent(s)
        # 4014: Disallowed intent(s)
        return code in (4004, 4010, 4011, 4012, 4013, 4014)

    def _can_handle_close(self) -> bool:
        if self._is_fatal_close():
            return False

        code = self._close_code or (self.ws.close_code if self.ws else None)
        return code != 1000

    def _was_normal_close(self) -> bool:
        code = self._close_code or self.ws.close_code
        return code == 1000

    async def send_message(
        self,
        message: dict | PayloadType,
        *,
        ratelimit: bool = False
    ) -> None:
        """
        Sends a message to the websocket.

        Parameters
        ----------
        message
            The message to send to the websocket
        ratelimit
            Whether to ratelimit the message or not
        """
        if isinstance(message, PayloadType):
            message = self.payload(message)

        if not isinstance(message, dict):
            raise TypeError("message must be of type dict")

        if ratelimit:
            await self._ratelimiter.block()

        if self.debug_events:
            self.bot.dispatch("raw_socket_sent", message)

        _log.debug(f"Sending message: {message}")
        await self.ws.send_json(message)

        self.status.update_send()
        self._last_activity = utils.utcnow()

    async def close(
        self,
        code: int | None = 1000,
        *,
        kill: bool = False
    ) -> None:
        """
        Closes the websocket for good, or forcefully.

        Parameters
        ----------
        code
            The close code to use
        kill
            Whether to kill the shard and never reconnect instance
        """
        code = code or 1000
        self._close_code = code
        self._should_kill = kill
        await self.ws.close(code=code)

    async def received_message(self, raw_msg: str | bytes) -> None:
        """
        Handling the recieved data from the websocket.

        Parameters
        ----------
        raw_msg
            The message to receive
        """
        self._last_activity = utils.utcnow()

        if type(raw_msg) is bytes:
            self._buffer.extend(raw_msg)

            # Discord's zlib-stream suffix
            if len(raw_msg) < 4 or raw_msg[-4:] != b"\x00\x00\xff\xff":
                return

            decompressed_bytes = self._zlib.decompress(self._buffer)
            msg: dict = orjson.loads(decompressed_bytes)

            # There has been times it keeps in memory
            # Thanks Python, very cool...
            del decompressed_bytes
            self._buffer = bytearray()
        else:
            msg: dict = orjson.loads(raw_msg)

        op = PayloadType(msg.get("op"))
        data = msg.get("d")
        seq = msg.get("s")

        if seq is not None:
            self.status.update_sequence(seq)

        self.status.tick()

        event = msg.get("t")

        if event:
            await self.on_event(event, msg)

        if op != PayloadType.dispatch:
            match op:
                case PayloadType.reconnect:
                    _log.debug(f"Shard {self.shard_id} got requrested to reconnect")
                    await self.close(code=1013)  # 1013 = Try again later

                case PayloadType.heartbeat_ack:
                    self.status.ack(
                        ignore_warning=not self._ready.is_set()
                    )
                    _log.debug(f"Shard {self.shard_id} heartbeat ACK")

                case PayloadType.heartbeat:
                    _log.debug(f"Shard {self.shard_id} heartbeat from event-case")
                    await self.send_message(PayloadType.heartbeat)

                case PayloadType.hello:
                    self._heartbeat_interval = (
                        int(data["heartbeat_interval"]) / 1000
                    )

                    self._reconnect_attempts = 0

                    if self.status.can_resume():
                        _log.debug(f"Shard {self.shard_id} resuming session")
                        await self.send_message(PayloadType.resume)

                    else:
                        _log.debug(f"Shard {self.shard_id} identifying...")
                        await self.send_message(PayloadType.identify)

                case PayloadType.invalidate_session:
                    if data is True:
                        # Session is still resumable, keep session_id/sequence intact
                        _log.warning(f"Shard {self.shard_id} session invalidated, will attempt to resume")
                    else:
                        # Session is no longer resumable, must identify fresh
                        _log.warning(f"Shard {self.shard_id} session invalidated, resetting instance")
                        self._reset_instance()

                    _log.debug(f"Shard {self.shard_id} invalidation data: {msg}")

                    await self.close(code=4000)

                case _:
                    pass  # Not handled, pass for now

            return  # In the end, we don't need to process anymore

        match event:
            case "READY":
                self.status.update_sequence(msg["s"])
                self.status.update_ready_data(data)
                self._expected_guild_count = len(data.get("guilds") or [])
                self._identified.set()

                if self._ready_task is not None and not self._ready_task.done():
                    self._ready_task.cancel()

                self._ready_task = asyncio.create_task(
                    self._delay_ready(),
                    name=f"discord.http/gateway/shard-{self.shard_id}/delay_ready"
                )

            case "RESUMED":
                if self.bot.has_any_dispatch("shard_resumed"):
                    self.bot.dispatch(
                        "shard_resumed",
                        ShardEventPayload(
                            shard=self,
                            reason=f"Shard {self.shard_id} resumed from gateway."
                        )
                    )
                else:
                    _log.info(f"Shard {self.shard_id} resumed")

            case _:
                pass

    async def send_guild_members_chunk(
        self,
        guild_id: Snowflake | int,
        *,
        query: str | None = None,
        limit: int = 0,
        presences: bool = False,
        user_ids: list[Snowflake | int] | None = None,
        nonce: str | None = None
    ) -> None:
        """
        Sends a guild members chunk.

        Parameters
        ----------
        guild_id
            The guild id to send the chunk to
        query
            What to query for, by default None
        limit
            The limit of members to fetch, by default 0
        presences
            If to fetch presences, by default False
        user_ids
            UserIDs to find, by default None
        nonce
            The nonce to use, by default None
        """
        payload: dict[str, str | int | list[str]] = {
            "guild_id": str(guild_id)
        }

        if user_ids:
            payload["user_ids"] = [str(int(g)) for g in user_ids]
        else:
            payload["query"] = str(query or "")
            payload["limit"] = int(limit)

        if presences:
            payload["presences"] = True

        if nonce is not None:
            nonce_ = str(nonce)
            if len(nonce_) > 32:
                _log.warning("Nonce is probably too long, it might be ignored by Discord")

            payload["nonce"] = nonce_

        await self.send_message(
            {"op": int(PayloadType.request_guild_members), "d": payload},
            ratelimit=True
        )

    async def query_members(
        self,
        guild_id: Snowflake | int,
        *,
        query: str | None = None,
        limit: int = 0,
        presences: bool = False,
        user_ids: list[Snowflake | int] | None = None
    ) -> list["Member"]:
        """
        Query members.

        Parameters
        ----------
        guild_id
            The guild id to query
        query
            The query to use, by default None
        limit
            The limit of members to fetch, by default 0
        presences
            If to fetch presences, by default False
        user_ids
            UserIDs to find, by default None

        Returns
        -------
            The members found
        """
        chunker = GuildMembersChunk(state=self.bot.state, guild_id=int(guild_id))
        self.parser._chunk_requests[chunker.nonce] = chunker

        try:
            await self.send_guild_members_chunk(
                guild_id=guild_id,
                query=query,
                limit=limit,
                presences=presences,
                user_ids=user_ids,
                nonce=chunker.nonce
            )

            try:
                return await asyncio.wait_for(chunker.wait(), timeout=30.0)
            except TimeoutError:
                _log.warning(
                    "Timed out while waiting for guild members chunk "
                    f"(guild_id={guild_id}, query={query}, limit={limit})"
                )
                raise
        finally:
            self.parser._chunk_requests.pop(chunker.nonce, None)

    @overload
    async def chunk_guild(
        self,
        guild_id: Snowflake | int,
        *,
        wait: bool = False
    ) -> asyncio.Future[list["Member"]]:
        ...

    @overload
    async def chunk_guild(
        self,
        guild_id: Snowflake | int,
        *,
        wait: bool = True
    ) -> list["Member"]:
        ...

    async def chunk_guild(
        self,
        guild_id: Snowflake | int,
        *,
        wait: bool = True
    ) -> list["Member"] | asyncio.Future[list["Member"]]:
        """
        Chunks the guild.

        Parameters
        ----------
        guild_id
            The guild id to chunk
        wait
            Whether to wait for the chunk to be ready or not

        Returns
        -------
            The chunk of members
        """
        chunker = GuildMembersChunk(
            state=self.bot.state, guild_id=int(guild_id),
            cache=True
        )
        self.parser._chunk_requests[chunker.nonce] = chunker

        try:
            await self.send_guild_members_chunk(
                guild_id=guild_id,
                query="",
                limit=0,
                nonce=chunker.nonce
            )
        except Exception:
            self.parser._chunk_requests.pop(chunker.nonce, None)
            raise

        if wait:
            try:
                return await chunker.wait()
            finally:
                self.parser._chunk_requests.pop(chunker.nonce, None)
        return chunker.get_future()

    def _dispatch_close_reason(
        self,
        reason: str,
        close_type: ShardCloseType,
        *,
        exception: Exception | None = None,
    ) -> None:
        if self.bot.has_any_dispatch("shard_closed"):
            payload = ShardEventPayload(
                shard=self,
                reason=reason,
                exception=exception,
                close_type=close_type
            )
            self.bot.dispatch("shard_closed", payload)
        else:
            _log.warning(reason)

    async def _socket_manager(self) -> None:
        try:
            keep_waiting: bool = True
            self._reset_buffer()
            self._ratelimiter.reset()

            kwargs = {
                "max_msg_size": 0,
                "timeout": 30.0,
                "headers": {
                    "User-Agent": self.bot.state._default_headers["User-Agent"]
                },
                "autoclose": False,
                "compress": 0,
            }

            async with self.session.ws_connect(self.url, **kwargs) as ws:
                self.ws = ws
                self.status.reset_heartbeat()

                try:
                    while keep_waiting:
                        if (
                            not self.status._last_heartbeat or
                            time.perf_counter() - self.status._last_heartbeat > self._heartbeat_interval
                        ):
                            if self.status.is_zombied():
                                raise ConnectionAbortedError(
                                    f"Shard {self.shard_id} did not receive a heartbeat ACK, connection is zombied"
                                )

                            _log.debug(f"Shard {self.shard_id} heartbeat from if-case")
                            await self.send_message(PayloadType.heartbeat)

                        try:
                            evt = await asyncio.wait_for(
                                self.ws.receive(),
                                timeout=self._heartbeat_interval
                            )

                        except TimeoutError:
                            if self.status.is_zombied():
                                raise ConnectionAbortedError(
                                    f"Shard {self.shard_id} did not receive a heartbeat ACK, connection is zombied"
                                )

                            # No event received, send in case..
                            _log.debug(f"Shard {self.shard_id} heartbeat from except-case")
                            await self.send_message(PayloadType.heartbeat)

                        except asyncio.CancelledError:
                            await self.ws.ping()
                            raise

                        else:
                            match evt.type:
                                case WSMsgType.TEXT | WSMsgType.BINARY:
                                    await self.received_message(evt.data)

                                case WSMsgType.CLOSE | WSMsgType.CLOSED | WSMsgType.CLOSING:
                                    self._close_code = evt.data
                                    raise ConnectionAbortedError(
                                        f"Shard {self.shard_id} received close frame with code {evt.data}"
                                    )

                                case WSMsgType.ERROR:
                                    raise ConnectionError(f"Shard {self.shard_id} received websocket error: {evt.data}")

                except Exception as e:
                    keep_waiting = False

                    if self._should_kill is True:
                        # Library is shutting down, custom close was called
                        _log.debug(f"Shard {self.shard_id} received a kill signal, shutting down")
                        return

                    if self._is_fatal_close():
                        # Fatal close code received, do not attempt to reconnect, just shutdown the shard
                        self._dispatch_close_reason(
                            f"Shard {self.shard_id} received fatal close code {self._close_code}, shutting down.",
                            ShardCloseType.hard_crash,
                            exception=e
                        )
                        return

                    _log.debug(f"Shard {self.shard_id} error", exc_info=e)

                    if self._can_handle_close():
                        self._reset_buffer()
                        self._dispatch_close_reason(
                            f"Shard {self.shard_id} closed, attempting reconnect due to resume event.",
                            ShardCloseType.resume,
                            exception=e
                        )

                    else:  # Something went wrong, reset the instance
                        self._reset_instance()
                        if self._was_normal_close():
                            # Possibly Discord closed the connection due to load balancing
                            self._dispatch_close_reason(
                                f"Shard {self.shard_id} closed, attempting new connection due to normal close.",
                                ShardCloseType.reconnect,
                                exception=e
                            )

                        else:
                            self._dispatch_close_reason(
                                f"Shard {self.shard_id} crashed, attempting new connection.",
                                ShardCloseType.normal_crash,
                                exception=e
                            )

                    # Reset back to 0 as soon as HELLO confirms a real connection.
                    self._reconnect_attempts += 1

                    # First attempt reconnects instantly (the common case: a brief
                    # blip). Only a second consecutive failure starts backing off.
                    backoff = (
                        0.0 if self._reconnect_attempts <= 1
                        else min(2 ** min(self._reconnect_attempts - 2, 6), 60)
                    )

                    if backoff:
                        jitter = backoff * 0.25 * self.bot.state.create_jitter()
                        _log.debug(
                            f"Shard {self.shard_id} waiting {backoff + jitter:.2f}s before reconnecting "
                            f"(attempt {self._reconnect_attempts})"
                        )
                        await asyncio.sleep(backoff + jitter)

                    self.connect()

        except Exception as e:
            self._reset_instance()
            _log.error(f"Shard {self.shard_id} crashed completly", exc_info=e)
            self._dispatch_close_reason(
                f"Shard {self.shard_id} crashed completly: {e}",
                ShardCloseType.hard_crash,
                exception=e
            )

    def _guild_needs_chunking(self, guild: "Guild | PartialGuild") -> bool:
        return (
            self.bot.chunk_guilds_on_startup and
            not guild.chunked and
            not (
                Intents.guild_presences in self.intents and
                not guild.large
            )
        )

    def _chunk_timeout(self, guild: "Guild | PartialGuild") -> float:
        return max(5.0, (guild.member_count or 0) / 10_000)

    async def _chunk_and_dispatch(
        self,
        guild_data: dict,
        event_name: str
    ) -> None:
        (parsed_guild,) = self.parser.guild_create(guild_data)

        timeout = self._chunk_timeout(parsed_guild)

        try:
            await asyncio.wait_for(self.chunk_guild(parsed_guild.id), timeout=timeout)
        except TimeoutError:
            _log.warning(
                f"Timed out while waiting for guild members chunk "
                f"(guild_id={parsed_guild.id}, timeout={timeout})"
            )

        self._send_dispatch(event_name, parsed_guild)

    async def _delay_ready(self) -> None:
        """
        Purposfully delays the ready event.

        Then make shard ready as soon as every guild reported in the READY
        payload has sent its GUILD_CREATE, or when GUILD_CREATE traffic goes
        quiet for `guild_ready_timeout` seconds, whichever happens first.
        The timeout is only a fallback for a guild stuck unavailable.
        """
        try:
            states: list[tuple[Guild | PartialGuild, asyncio.Future[list[Member]]]] = []
            received = 0
            while received < self._expected_guild_count:
                try:
                    guild_data = await asyncio.wait_for(
                        self._guild_create_queue.get(),
                        timeout=self._guild_ready_timeout
                    )
                except TimeoutError:
                    break  # It's supposed to timeout
                else:
                    received += 1
                    # Start adding guilds to cache if it's enabled
                    (parsed_guild,) = self.parser.guild_create(guild_data)

                    if self._guild_needs_chunking(parsed_guild):
                        future = await self.chunk_guild(parsed_guild.id, wait=False)
                        states.append((parsed_guild, future))

            for guild, future in states:
                timeout = self._chunk_timeout(guild)

                if not future.done():
                    try:
                        await asyncio.wait_for(future, timeout=timeout)
                    except TimeoutError:
                        _log.warning(
                            f"Timed out while waiting for guild members chunk "
                            f"(guild_id={guild.id}, timeout={timeout})"
                        )

        except asyncio.CancelledError:
            return

        self._ready.set()
        self.parser._chunk_requests.clear()

        if self.bot.has_any_dispatch("shard_ready"):
            self.bot.dispatch(
                "shard_ready",
                ShardEventPayload(
                    shard=self,
                    reason=f"Shard {self.shard_id} is now ready."
                )
            )
        else:
            _log.info(f"Shard {self.shard_id} ready")

    async def wait_until_ready(self) -> None:
        """ Waits until the shard is ready. """
        await self._ready.wait()

    async def on_event(self, name: str, event: dict) -> None:
        """
        Handles an event.

        Parameters
        ----------
        name
            The name of the event
        event
            The event data
        """
        if not (data := event.get("d")):
            return

        if self.debug_events:
            self.bot.dispatch("raw_socket_received", event)

        # First check special shard-level overrides
        if name in self._special_handlers:
            handler, is_coro = self._special_handlers[name]
            try:
                await handler(data) if is_coro else handler(data)
            except Exception as e:
                _log.error(f"Error while handling event {name}", exc_info=e)
            return

        # Check if parser has the method cached (keyed by the original,
        # un-lowered name so repeat dispatches skip the .lower() call too)
        cached: tuple[str, Callable[[dict], tuple[Any, ...]] | Literal[False]] | None = self._parser_cache.get(name)

        if cached is None:
            # If not, now use getattr to get it and cache it if found
            new_name = name.lower()
            # Pyright likes to complain here, but the type above is correct
            parser_method: Callable[[dict], tuple[Any, ...]] | Literal[False] = getattr(  # pyright: ignore[reportAssignmentType]
                self.parser, new_name, False
            )
            cached = (new_name, parser_method)
            self._parser_cache[name] = cached

        new_name, parser_method = cached

        if parser_method:
            # Parse data, this will also cache depending on developer flags
            try:
                payload = parser_method(data)
            except Exception as e:
                _log.error(f"Error while parsing payload for event {new_name}", exc_info=e)
                return

            # If the developer is listening to the event, dispatch it
            if self.bot.has_any_dispatch(new_name):
                try:
                    self._send_dispatch(new_name, *payload)
                except Exception as e:
                    _log.error(f"Error while parsing event {new_name}", exc_info=e)

    def _send_dispatch(self, name: str, *args: Any) -> None:  # ruff: ignore[any-type]
        try:
            self.bot.dispatch(name, *args)
        except Exception as e:
            _log.error(f"Error while parsing event {name}", exc_info=e)

    async def _parse_guild_create(self, data: dict) -> None:
        unavailable = data.get("unavailable")
        if unavailable is True:
            return

        if unavailable is False:
            (guild,) = self.parser.guild_available(data)
            guild.unavailable = False
            event_name = "guild_available"

        else:
            (guild,) = self.parser.guild_create(data)
            event_name = "guild_create"

        if not self._ready.is_set():
            # We still want to parse GUILD_CREATE
            # But we do not want to dispatch event just yet
            self._guild_create_queue.put_nowait(data)
            return

        if self._guild_needs_chunking(guild):
            task = asyncio.create_task(
                self._chunk_and_dispatch(data, event_name),
                name=f"discord.http/gateway/shard-{self.shard_id}/chunk-{guild.id}"
            )
            self.bot._background_tasks.add(task)
            task.add_done_callback(self.bot._cleanup_task)
            return

        self._send_dispatch(event_name, guild)

    def _parse_guild_delete(self, data: dict) -> None:
        if data.get("unavailable"):
            (guild,) = self.parser.guild_unavailable(data)
            guild.unavailable = True
            event_name = "guild_unavailable"

        else:
            (guild,) = self.parser.guild_delete(data)
            event_name = "guild_delete"

        self._send_dispatch(event_name, guild)

    async def _parse_guild_members_chunk(self, data: dict) -> None:
        result = self.parser.guild_members_chunk(data)

        # If the user IS actually listening to the event, dispatch it
        if self.bot.has_any_dispatch("guild_members_chunk"):
            self._send_dispatch("guild_members_chunk", *result)

    def connect(self) -> None:
        """ Connect the websocket. """
        current_task = asyncio.current_task()
        if (
            self._connection is not None and
            self._connection is not current_task and
            not self._connection.done()
        ):
            self._connection.cancel()
        self._connection = asyncio.ensure_future(self._socket_manager())

    async def change_presence(self, status: PlayingStatus) -> None:
        """
        Changes the presence of the shard to the specified status.

        Parameters
        ----------
        status
            The status to change to.
        """
        _log.debug(f"Changing presence in Shard {self.shard_id} to {status}")
        await self.send_message({
            "op": int(PayloadType.presence),
            "d": status.to_dict()
        })

    def payload(self, op: PayloadType) -> dict:
        """
        Returns a payload for the websocket.

        Parameters
        ----------
        op
            The op to get the payload for

        Returns
        -------
            The payload
        """
        if not isinstance(op, PayloadType):
            raise TypeError("op must be of type PayloadType")

        match op:
            case PayloadType.heartbeat:
                self.status.update_heartbeat()
                return self.status.get_payload()

            case PayloadType.hello:
                return {
                    "op": int(op),
                    "d": {
                        "heartbeat_interval": int(self._heartbeat_interval * 1000)
                    }
                }

            case PayloadType.resume:
                return {
                    "op": int(op),
                    "d": {
                        "seq": self.status.sequence,
                        "session_id": self.status.session_id,
                        "token": self.bot.token,
                    }
                }

            case _:
                payload = {
                    "op": int(op),
                    "d": {
                        "token": self.bot.token,
                        "intents": (
                            self.intents.value
                            if self.intents else 0
                        ),
                        "properties": {
                            "os": sys.platform,
                            "browser": "discord.http",
                            "device": "discord.http"
                        },
                        "compress": True,
                        "large_threshold": 250,
                    }
                }

                if self.shard_count is not None:
                    payload["d"]["shard"] = [self.shard_id, int(self.shard_count)]

                if self.playing_status is not None:
                    payload["d"]["presence"] = self.playing_status.to_dict()

                if self.capabilities is not None:
                    payload["d"]["capabilities"] = int(self.capabilities)

                return payload
