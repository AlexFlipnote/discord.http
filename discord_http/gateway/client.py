
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
        self.intents = intents
        self.cache_flags = cache_flags

        self.automatic_shards = automatic_shards
        self.shard_id = shard_id
        self.shard_count = shard_count
        self.shard_ids = shard_ids
        self.max_concurrency = max_concurrency

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
        shard_id:
            The ID of the shard to get.

        Returns
        -------
            The shard object with the specified ID, or `None` if not found.
        """
        return self.__shards.get(shard_id, None)

    async def change_presence(self, status: PlayingStatus) -> None:
        """
        Changes the presence of all shards to the specified status.

        Parameters
        ----------
        status:
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
        shard_id:
            The shard ID to launch
        """
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

            while not shard.status.session_id:
                await asyncio.sleep(0.5)

        except Exception as e:
            _log.error("Error launching shard, trying again...", exc_info=e)
            return await self._launch_shard(shard_id)

        self.__shards[shard_id] = shard
        return None

    def shard_by_guild_id(self, guild_id: "Snowflake | int") -> int:
        """
        Returns the shard ID of the shard that the guild is in.

        Parameters
        ----------
        guild_id:
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

            for i, shard_chunk in enumerate(chunks, start=1):
                booting: list[Coroutine] = [
                    self._launch_shard(shard_id)
                    for shard_id in shard_chunk
                ]

                _log.debug(f"Launching bucket {i}/{len(chunks)}")
                await asyncio.gather(*booting)

                if i != len(chunks):
                    _log.debug(f"Bucket {i}/{len(chunks)} shards launched, waiting (5s/bucket)")
                    await asyncio.sleep(5)
                else:
                    _log.debug(f"Bucket {i}/{len(chunks)} shards launched, last bucket, skipping wait")

            _log.debug(f"All {len(chunks)} bucket(s) have launched a total of {self.shard_count} shard(s)")

        asyncio.create_task(self._delay_full_ready())  # noqa: RUF006

    async def _delay_full_ready(self) -> None:
        waiting: list[Coroutine] = [
            g.wait_until_ready()
            for g in self.__shards.values()
        ]

        # Gather all shards to now wait until they are ready
        await asyncio.gather(*waiting)

        self.bot._shards_ready.set()
        _log.info("discord.http/gateway is now ready")

    def start(self) -> None:
        """ Start the gateway client. """
        self.bot.loop.create_task(self._launch_all_shards())

    async def close(self) -> None:
        """ Close the gateway client. """
        async def _close() -> None:
            to_close = [
                asyncio.ensure_future(shard.close(kill=True))
                for shard in self.__shards.values()
            ]

            if to_close:
                await asyncio.wait(to_close)

        task = asyncio.create_task(_close())
        await task
