
import asyncio
import logging
import operator

from aiohttp import web
from collections.abc import Coroutine
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from .object import PlayingStatus
from .shard import Shard

if TYPE_CHECKING:
    from ..client import GatewayCacheFlags, Client, Intents
    from ..object import Snowflake

_log = logging.getLogger("discord_http")

__all__ = (
    "GatewayClient",
)


class GatewayClient:
    """ Represents the discord.http/gateway client of the bot. """
    def __init__(
        self,
        bot: "Client",
        *,
        cache_flags: "GatewayCacheFlags | None" = None,
        intents: "Intents | None" = None,
        automatic_shards: bool = True,
        shard_id: int | None = None,
        shard_count: int = 1,
        shard_ids: list[int] | None = None,
        max_concurrency: int | None = None
    ):
        self.bot = bot
        """ The bot instance that this gateway client belongs to. """

        self.intents = intents
        """ The intents that the gateway client is using, or `None` if not specified. """

        self.cache_flags = cache_flags
        """ The cache flags that the gateway client is using, or `None` if not specified. """

        self.automatic_shards = automatic_shards
        """ Whether to automatically determine the number of shards to launch based on the gateway response. """

        self.shard_id = shard_id
        """ The shard ID to launch, or `None` if not specified. """

        self.shard_count = shard_count
        """ The total number of shards to launch, defaults to 1. """

        self.shard_ids = shard_ids
        """ A list of shard IDs to launch, or `None` to launch all shards from 0 to `shard_count - 1`. """

        self.max_concurrency = max_concurrency
        """ The maximum number of shards to launch concurrently, or `None` to launch all shards at once. """

        self.__shards: dict[int, Shard] = {}

        self.bot.backend.router.add_get(
            "/shards",
            self._index_websocket_status,
        )

    def get_shard(self, shard_id: int) -> Shard | None:
        """
        Returns the shard object of the shard with the specified ID.

        Parameters
        ----------
        shard_id
            The ID of the shard to get.

        Returns
        -------
            The shard object with the specified ID, or `None` if not found.
        """
        return self.__shards.get(shard_id)

    async def change_presence(self, status: PlayingStatus) -> None:
        """
        Changes the presence of all shards to the specified status.

        Parameters
        ----------
        status
            The status to change to.
        """
        for shard in self.__shards.values():
            await shard.change_presence(status)

    async def _index_websocket_status(self, _: web.Request) -> web.Response:
        now = datetime.now(UTC)
        payload = {
            str(shard_id): {
                "ping": shard.status.ping,
                "latency": shard.status.latency,
                "activity": {
                    "last": str(shard._last_activity),
                    "between": str(now - shard._last_activity)
                }
            }
            for shard_id, shard in sorted(
                self.__shards.items(), key=operator.itemgetter(0)
            )
        }

        return self.bot.backend.jsonify(payload)

    async def _fetch_gateway(self) -> tuple[int, int]:
        r = await self.bot.state.query("GET", "/gateway/bot")

        return (
            r.response["shards"],
            r.response["session_start_limit"]["max_concurrency"]
        )

    async def _launch_shard(self, shard_id: int) -> None:
        """
        Individual shard launching.

        Parameters
        ----------
        shard_id
            The shard ID to launch
        """
        attempt = 0
        while True:
            shard = None
            try:
                shard = Shard(
                    bot=self.bot,
                    intents=self.intents,
                    cache_flags=self.cache_flags,
                    shard_id=shard_id,
                    shard_count=self.shard_count,
                    api_version=self.bot.api_version,
                    debug_events=self.bot.debug_events
                )

                shard.connect()
                if (connection := shard._connection) is None:
                    raise RuntimeError(f"Shard {shard_id} connection was not established")

                identify_wait = asyncio.ensure_future(shard._identified.wait())
                try:
                    done, _ = await asyncio.wait(
                        {identify_wait, connection},
                        timeout=30,
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    if identify_wait not in done:
                        if connection in done:
                            raise RuntimeError(f"Shard {shard_id} connection ended before it could identify")
                        raise TimeoutError(f"Shard {shard_id} timed out waiting to identify")
                finally:
                    if not identify_wait.done():
                        identify_wait.cancel()
                        try:
                            await identify_wait
                        except asyncio.CancelledError:
                            pass

            except Exception as e:
                if shard is not None and shard._is_fatal_close():
                    _log.error(
                        f"Shard {shard_id} received a fatal close code "
                        f"({shard._close_code}), aborting startup",
                        exc_info=e
                    )
                    if shard._connection is not None:
                        shard._connection.cancel()
                    raise

                _log.error("Error launching shard, trying again...", exc_info=e)
                if shard is not None and shard._connection is not None:
                    shard._connection.cancel()
                attempt += 1
                await asyncio.sleep(min(2 ** attempt, 30) + self.bot.state.create_jitter())
                continue

            self.__shards[shard_id] = shard
            return

    def shard_by_guild_id(self, guild_id: "Snowflake | int") -> int:
        """
        Returns the shard ID of the shard that the guild is in.

        Parameters
        ----------
        guild_id
            The ID of the guild to get the shard ID of

        Returns
        -------
            The shard ID of the guild
        """
        return (int(guild_id) >> 22) % self.shard_count

    async def _launch_all_shards(self) -> None:
        """ Launches all the shards. """
        if self.automatic_shards:
            self.shard_count, self.max_concurrency = await self._fetch_gateway()

        if self.shard_count == 1:
            # There is no need to shard if there is only 1 shard
            _log.debug("Sharding disabled, no point in sharding 1 shard")
            self.max_concurrency = None

        shard_ids = self.shard_ids or range(self.shard_count)

        if not self.max_concurrency:
            for shard_id in shard_ids:
                await self._launch_shard(shard_id)

            _log.debug(f"All {len(shard_ids)} shard(s) have launched")

        else:
            chunks = [
                list(shard_ids[i:i + self.max_concurrency])
                for i in range(0, len(shard_ids), self.max_concurrency)
            ]

            booting: list[asyncio.Task] = []

            for i, shard_chunk in enumerate(chunks, start=1):
                _log.debug(f"Launching bucket {i}/{len(chunks)}")
                booting.extend(
                    asyncio.ensure_future(self._launch_shard(shard_id))
                    for shard_id in shard_chunk
                )

                if i == len(chunks):
                    break

                if any(
                    task.done() and not task.cancelled() and task.exception() is not None
                    for task in booting
                ):
                    # A previous bucket already failed fatally, no point pacing
                    # further buckets for a boot that's already going to error out
                    _log.debug("A shard failed during startup, stopping further bucket launches")
                    break

                await asyncio.sleep(5)

            await asyncio.gather(*booting)
            _log.debug(f"All {len(chunks)} bucket(s) have launched a total of {self.shard_count} shard(s)")

        task = asyncio.create_task(
            self._delay_full_ready(),
            name="discord.http/gateway/delay_full_ready"
        )
        self.bot._background_tasks.add(task)
        task.add_done_callback(self.bot._cleanup_task)

    async def _delay_full_ready(self) -> None:
        waiting: list[Coroutine] = [
            g.wait_until_ready()
            for g in self.__shards.values()
        ]

        # Gather all shards to now wait until they are ready
        # return_exceptions so a future failure in one shard can't orphan the rest
        results = await asyncio.gather(*waiting, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                _log.error("Error while waiting for a shard to become ready", exc_info=result)

        self.bot._shards_ready.set()
        _log.info("discord.http/gateway is now ready")

    def start(self) -> None:
        """ Start the gateway client. """
        task = self.bot.loop.create_task(
            self._launch_all_shards(),
            name="discord.http/gateway/launch_all_shards"
        )
        self.bot._background_tasks.add(task)
        task.add_done_callback(self.bot._cleanup_task)

    async def close(self) -> None:
        """ Close the gateway client. """
        to_close = [
            asyncio.ensure_future(shard.close(kill=True))
            for shard in self.__shards.values()
        ]

        if to_close:
            done, pending = await asyncio.wait(to_close, timeout=10.0)

            for fut in pending:
                fut.cancel()

            for fut in done:
                if not fut.cancelled() and (exc := fut.exception()):
                    _log.error("Error while closing a shard", exc_info=exc)

        self.__shards.clear()
