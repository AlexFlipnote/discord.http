import aiohttp
import asyncio
import json
import logging
import sys
import time
import yarl
import zlib

from datetime import datetime
from typing import Any, TYPE_CHECKING, overload

from .. import utils
from ..object import Snowflake

from .enums import PayloadType, ShardCloseType
from .flags import GatewayCacheFlags, Intents
from .object import PlayingStatus
from .parser import Parser, GuildMembersChunk

if TYPE_CHECKING:
    from ..member import Member
    from ..client import Client
    from ..guild import Guild

DEFAULT_GATEWAY = yarl.URL("wss://gateway.discord.gg/")
_log = logging.getLogger("discord_http")

__all__ = (
    "Shard",
)


class GatewayRatelimiter:
    def __init__(
        self,
        shard_id: int,
        count: int = 110,
        per: float = 60.0
    ) -> None:
        self.shard_id: int = shard_id

        self.max: int = count
        self.remaining: int = count
        self.window: float = 0.0
        self.per: float = per
        self.lock: asyncio.Lock = asyncio.Lock()

    def is_ratelimited(self) -> bool:
        current = time.time()
        if current > self.window + self.per:
            return False
        return self.remaining == 0

    def get_delay(self) -> float:
        current = time.time()

        if current > self.window + self.per:
            self.remaining = self.max

        if self.remaining == self.max:
            self.window = current

        if self.remaining == 0:
            return self.per - (current - self.window)

        self.remaining -= 1
        return 0.0

    async def block(self) -> None:
        async with self.lock:
            retry_after = self.get_delay()
            if retry_after:
                _log.warning(
                    "WebSocket ratelimit hit on ShardID "
                    f"{self.shard_id}, waiting {round(retry_after, 2)}s..."
                )
                await asyncio.sleep(retry_after)
                _log.info(f"WebSocket ratelimit released on ShardID {self.shard_id}")


class Status:
    def __init__(self, shard_id: int):
        self.shard_id = shard_id

        self.sequence: int | None = None
        self.session_id: str | None = None
        self.gateway = DEFAULT_GATEWAY

        self.latency: float = float("inf")
        self._last_ack: float = time.perf_counter()
        self._last_send: float = time.perf_counter()
        self._last_recv: float = time.perf_counter()
        self._last_heartbeat: float | None = None

    @property
    def ping(self) -> float:
        return self._last_recv - self._last_send

    def reset(self) -> None:
        self.sequence = None
        self.session_id = None
        self.gateway = DEFAULT_GATEWAY

    def can_resume(self) -> bool:
        return self.session_id is not None

    def update_sequence(self, sequence: int) -> None:
        self.sequence = sequence

    def update_ready_data(self, data: dict) -> None:
        self.session_id = data["session_id"]
        self.gateway = yarl.URL(data["resume_gateway_url"])

    def get_payload(self) -> dict:
        return {
            "op": int(PayloadType.heartbeat),
            "d": self.sequence
        }

    def update_send(self) -> None:
        self._last_send = time.perf_counter()

    def update_heartbeat(self) -> None:
        self._last_heartbeat = time.perf_counter()

    def tick(self) -> None:
        self._last_recv = time.perf_counter()

    def ack(
        self,
        *,
        ignore_warning: bool = False
    ) -> None:
        """
        Acknowledges the heartbeat

        Parameters
        ----------
        ignore_warning: `bool`
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
    def __init__(
        self,
        bot: "Client",
        intents: Intents | None,
        shard_id: int,
        *,
        cache_flags: GatewayCacheFlags | None = None,
        shard_count: int | None = None,
        debug_events: bool = False,
        api_version: int | None = 8
    ):
        self.bot = bot

        self.intents = intents
        self.cache_flags = cache_flags

        self.api_version = api_version
        self.shard_id = shard_id
        self.shard_count = shard_count
        self.debug_events = debug_events

        self.ws: aiohttp.ClientWebSocketResponse | None = None

        # Session was already made before, pyright is wrong
        self.session: aiohttp.ClientSession = self.bot.state.http.session  # type: ignore

        self.parser = Parser(bot)
        self.status = Status(shard_id)

        self.playing_status: PlayingStatus | None = bot.playing_status

        self._ready: asyncio.Event = asyncio.Event()
        self._guild_ready_timeout: float = float(bot.guild_ready_timeout)
        self._guild_create_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._ratelimiter: GatewayRatelimiter = GatewayRatelimiter(shard_id)

        self._connection = None
        self._should_kill = False

        self._buffer: bytearray = bytearray()
        self._zlib: zlib._Decompress = zlib.decompressobj()

        self._heartbeat_interval: float = 41_250 / 1000  # 41.25 seconds
        self._close_code: int | None = None
        self._last_activity: datetime = utils.utcnow()

    @property
    def url(self) -> str:
        """ Returns the websocket url for the client """
        if not isinstance(self.api_version, int):
            raise TypeError("api_version must be of type int")

        return self.status.gateway.with_query(
            v=self.api_version,
            encoding="json",
            compress="zlib-stream"
        ).human_repr()

    def _reset_buffer(self) -> None:
        self._buffer = bytearray()
        self._zlib = zlib.decompressobj()

    def _reset_instance(self) -> None:
        self._reset_buffer()
        self.status.reset()

    def _can_handle_close(self) -> bool:
        code = self._close_code or self.ws.close_code
        return code not in (1000, 4004, 4010, 4011, 4012, 4013, 4014)

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
        Sends a message to the websocket

        Parameters
        ----------
        message: `Union[dict, PayloadType]`
            The message to send to the websocket
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
        Closes the websocket for good, or forcefully

        Parameters
        ----------
        code: `Optional[int]`
            The close code to use
        kill: `bool`
            Whether to kill the shard and never reconnect instance
        """
        code = code or 1000
        self._close_code = code
        self._should_kill = kill
        await self.ws.close(code=code)

    async def received_message(self, raw_msg: str | bytes) -> None:
        """
        Handling the recieved data from the websocket

        Parameters
        ----------
        msg: `Union[bytes, str]`
            The message to receive
        """
        self._last_activity = utils.utcnow()

        if type(raw_msg) is bytes:
            self._buffer.extend(raw_msg)

            if len(raw_msg) < 4 or raw_msg[-4:] != b"\x00\x00\xff\xff":
                return None

            raw_msg = self._zlib.decompress(self._buffer)
            raw_msg = raw_msg.decode("utf-8")
            self._buffer = bytearray()

        msg: dict = json.loads(raw_msg)

        event = msg.get("t", None)

        if event:
            await self.on_event(event, msg)

        op = msg.get("op", None)
        data = msg.get("d", None)
        seq = msg.get("s", None)

        if seq is not None:
            self.status.update_sequence(seq)

        self.status.tick()

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

                    if self.status.can_resume():
                        _log.debug(f"Shard {self.shard_id} resuming session")
                        await self.send_message(PayloadType.resume)

                    else:
                        _log.debug(f"Shard {self.shard_id} identifying...")
                        await self.send_message(PayloadType.identify)

                case PayloadType.invalidate_session:
                    self._reset_instance()

                    if data is True:
                        _log.error(f"Shard {self.shard_id} session invalidated, not attempting reboot...")
                        # TODO: Add a way to kill shard maybe?

                    elif data is False:
                        _log.warning(f"Shard {self.shard_id} session invalidated, resetting instance")

                    _log.debug(f"Shard {self.shard_id} invalidation data: {msg}")

                    await self.close()

                case _:
                    pass  # Not handled, pass for now

            return None  # In the end, we don't need to process anymore

        match event:
            case "READY":
                self.status.update_sequence(msg["s"])
                self.status.update_ready_data(data)
                asyncio.create_task(self._delay_ready())

            case "RESUMED":
                if self.bot.has_any_dispatch("shard_resumed"):
                    self.bot.dispatch("shard_resumed", self)
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
        payload = {
            "guild_id": str(guild_id),
            "limit": int(limit),
        }

        if user_ids is not None:
            payload["user_ids"] = [str(int(g)) for g in user_ids]
        if query is not None:
            payload["query"] = str(query)
        if presences is True:
            payload["presences"] = True

        if nonce is not None:
            _nonce = str(nonce)
            if len(_nonce) > 32:
                _log.warning("Nonce is probably too long, it might be ignored by Discord")

            payload["nonce"] = str(nonce)

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
        """ test """
        chunker = GuildMembersChunk(state=self.bot.state, guild_id=int(guild_id))
        self.parser._chunk_requests[chunker.nonce] = chunker

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
        except asyncio.TimeoutError:
            _log.warning(
                "Timed out while waiting for guild members chunk "
                f"(guild_id={guild_id}, query={query}, limit={limit})"
            )
            raise

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
        chunker = GuildMembersChunk(
            state=self.bot.state, guild_id=int(guild_id),
            cache=True
        )
        self.parser._chunk_requests[chunker.nonce] = chunker

        await self.send_guild_members_chunk(
            guild_id=guild_id,
            query="",
            limit=0,
            nonce=chunker.nonce
        )

        if wait:
            return await chunker.wait()
        return chunker.get_future()

    def _dispatch_close_reason(self, reason: str, enum: ShardCloseType) -> None:
        if self.bot.has_any_dispatch("shard_closed"):
            self.bot.dispatch("shard_closed", self.shard_id, enum)
        else:
            _log.warning(reason)

    async def _socket_manager(self) -> None:
        try:
            keep_waiting: bool = True
            self._reset_buffer()

            kwargs = {
                "max_msg_size": 0,
                "timeout": 30.0,
                "headers": {"User-Agent": self.bot.state._headers},
                "autoclose": False,
                "compress": 0,
            }

            async with self.session.ws_connect(self.url, **kwargs) as ws:
                self.ws = ws

                try:
                    while keep_waiting:
                        if (
                            not self.status._last_heartbeat or
                            time.perf_counter() - self.status._last_heartbeat > self._heartbeat_interval
                        ):
                            _log.debug(f"Shard {self.shard_id} heartbeat from if-case")
                            await self.send_message(PayloadType.heartbeat)

                        try:
                            evt = await asyncio.wait_for(
                                self.ws.receive(),
                                timeout=self._heartbeat_interval
                            )

                        except asyncio.TimeoutError:
                            # No event received, send in case..
                            _log.debug(f"Shard {self.shard_id} heartbeat from except-case")
                            await self.send_message(PayloadType.heartbeat)

                        except asyncio.CancelledError:
                            await self.ws.ping()

                        else:
                            await self.received_message(evt.data)

                except Exception as e:
                    keep_waiting = False

                    if self._should_kill is True:
                        # Custom close code, only used when shutting down
                        return None

                    _log.debug(f"Shard {self.shard_id} error", exc_info=e)

                    if self._can_handle_close():
                        self._reset_buffer()

                        self._dispatch_close_reason(
                            f"Shard {self.shard_id} closed, attempting reconnect",
                            ShardCloseType.resume
                        )

                    else:  # Something went wrong, reset the instance
                        self._reset_instance()
                        if self._was_normal_close():
                            # Possibly Discord closed the connection due to load balancing
                            self._dispatch_close_reason(
                                f"Shard {self.shard_id} closed, attempting new connection",
                                ShardCloseType.reconnect
                            )

                        else:
                            _log.error(f"Shard {self.shard_id} crashed", exc_info=e)

                    self.connect()

        except Exception as e:
            self._reset_instance()
            _log.error(f"Shard {self.shard_id} crashed completly", exc_info=e)

    def _guild_needs_chunking(self, guild: "Guild") -> bool:
        return (
            self.bot.chunk_guilds_on_startup and
            not guild.chunked and
            not (
                Intents.guild_presences in self.bot.intents and
                not guild.large
            )
        )

    def _chunk_timeout(self, guild: "Guild") -> float:
        return max(5.0, (guild.member_count or 0) / 10_000)

    async def _delay_ready(self) -> None:
        """
        Purposfully delays the ready event
        Then make shard ready when last GUILD_CREATE is received
        """
        try:
            states: list[tuple[Guild, asyncio.Future[list[Member]]]] = []
            while True:
                try:
                    guild_data = await asyncio.wait_for(
                        self._guild_create_queue.get(),
                        timeout=self._guild_ready_timeout
                    )
                except asyncio.TimeoutError:
                    break  # It's supposed to timeout
                else:
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
                    except asyncio.TimeoutError:
                        _log.warning(
                            f"Timed out while waiting for guild members chunk "
                            f"(guild_id={guild.id}, timeout={timeout})"
                        )

        except asyncio.CancelledError:
            pass

        self._ready.set()
        self.parser._chunk_requests.clear()

        if self.bot.has_any_dispatch("shard_ready"):
            self.bot.dispatch("shard_ready", self)
        else:
            _log.info(f"Shard {self.shard_id} ready")

    async def wait_until_ready(self) -> None:
        """
        Waits until the shard is ready
        """
        await self._ready.wait()

    async def on_event(self, name: str, event: Any) -> None:
        new_name = name.lower()
        data: dict = event.get("d", {})

        if not data:
            return None

        if self.debug_events:
            self.bot.dispatch("raw_socket_received", event)

        _parse_event = getattr(self.parser, new_name, None)
        if not _parse_event:
            return None

        match name:
            case "GUILD_CREATE":
                await self._parse_guild_create(data)

            case "GUILD_DELETE":
                self._parse_guild_delete(data)

            case _:  # Any other event that does not need special handling
                try:
                    self._send_dispatch(new_name, *_parse_event(data))
                except Exception as e:
                    _log.error(f"Error while parsing event {new_name}", exc_info=e)

    def _send_dispatch(self, name: str, *args: Any) -> None:
        try:
            self.bot.dispatch(name, *args)
        except Exception as e:
            _log.error(f"Error while parsing event {name}", exc_info=e)

    async def _parse_guild_create(self, data: dict) -> None:
        unavailable = data.get("unavailable", None)
        if unavailable is True:
            return None

        if unavailable is False:
            (guild,) = self.parser.guild_available(data)
            guild.unavailable = False
            _event_name = "guild_available"

        else:
            (guild,) = self.parser.guild_create(data)
            _event_name = "guild_create"

        if not self._ready.is_set():
            # We still want to parse GUILD_CREATE
            # But we do not want to dispatch event just yet
            self._guild_create_queue.put_nowait(data)
            return None

        self._send_dispatch(_event_name, guild)

    def _parse_guild_delete(self, data: dict) -> None:
        if data.get("unavailable", False):
            (guild,) = self.parser.guild_unavailable(data)
            guild.unavailable = True
            _event_name = "guild_unavailable"

        else:
            (guild,) = self.parser.guild_delete(data)
            _event_name = "guild_delete"

        self._send_dispatch(_event_name, guild)

    def connect(self) -> None:
        """ Connect the websocket """
        self._connection = asyncio.ensure_future(
            self._socket_manager()
        )

    async def change_presence(self, status: PlayingStatus) -> None:
        """
        Changes the presence of the shard to the specified status.

        Parameters
        ----------
        status: `PlayingStatus`
            The status to change to.
        """
        _log.debug(f"Changing presence in Shard {self.shard_id} to {status}")
        await self.send_message({
            "op": int(PayloadType.presence),
            "d": status.to_dict()
        })

    def payload(self, op: PayloadType) -> dict:
        """ Returns a payload for the websocket """
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

                return payload
