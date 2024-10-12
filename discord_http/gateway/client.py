
import logging
import asyncio

from datetime import datetime, UTC
from typing import Optional, Coroutine, TYPE_CHECKING

from .shard import Shard
from .object import PlayingStatus

if TYPE_CHECKING:
    from ..client import GatewayCacheFlags, Client, Intents

_log = logging.getLogger("discord_http")

__all__ = (
    "GatewayClient",
)


class GatewayClient:
    def __init__(
        self,
        bot: "Client",
        *,
        cache_flags: Optional["GatewayCacheFlags"] = None,
        intents: Optional["Intents"] = None,
        automatic_shards: bool = True,
        shard_id: Optional[int] = None,
        shard_count: Optional[int] = None,
        shard_ids: Optional[list[int]] = None,
        max_concurrency: Optional[int] = None,
        api_version: Optional[int] = 8
    ):
        self.bot = bot
        self.intents = intents
        self.cache_flags = cache_flags

        self.automatic_shards = automatic_shards
        self.api_version = api_version
        self.shard_id = shard_id
        self.shard_count = shard_count
        self.shard_ids = shard_ids
        self.max_concurrency = max_concurrency

        self.__shards: dict[int, Shard] = {}

        self.bot.backend.add_url_rule(
            "/shards",
            "shards",
            self._index_websocket_status,
            methods=["GET"]
        )

    def get_shard(self, shard_id: int) -> Optional[Shard]:
        """
        Returns the shard object of the shard with the specified ID.

        Parameters
        ----------
        shard_id: `int`
            The ID of the shard to get.

        Returns
        -------
        `Optional[Shard]`
            The shard object with the specified ID, or `None` if not found.
        """
        return self.__shards.get(shard_id, None)

    async def change_presence(self, status: PlayingStatus) -> None:
        """
        Changes the presence of all shards to the specified status.

        Parameters
        ----------
        status: `PlayingStatus`
            The status to change to.
        """
        for shard in self.__shards.values():
            await shard.change_presence(status)

    async def _index_websocket_status(self) -> dict[int, dict]:
        _now = datetime.now(UTC)
        return {
            shard_id: {
                "ping": shard.status.ping,
                "latency": shard.status.latency,
                "activity": {
                    "last": str(shard._last_activity),
                    "between": str(_now - shard._last_activity)
                }
            }
            for shard_id, shard in sorted(
                self.__shards.items(), key=lambda x: x[0]
            )
        }

    async def _fetch_gateway(self) -> tuple[int, int]:
        r = await self.bot.state.query("GET", "/gateway/bot")

        return (
            r.response["shards"],
            r.response["session_start_limit"]["max_concurrency"]
        )

    async def _launch_shard(self, shard_id: int) -> None:
        """
        Individual shard launching

        Parameters
        ----------
        shard_id: `int`
            The shard ID to launch
        """
        try:
            shard = Shard(
                bot=self.bot,
                intents=self.intents,
                cache_flags=self.cache_flags,
                shard_id=shard_id,
                shard_count=self.shard_count,
                api_version=self.api_version,
                debug_events=self.bot.debug_events
            )

            shard.connect()

            while not shard.status.session_id:
                await asyncio.sleep(0.5)

        except Exception as e:
            _log.error("Error launching shard, trying again...", exc_info=e)
            return await self._launch_shard(shard_id)

        self.__shards[shard_id] = shard

    async def _launch_all_shards(self) -> None:
        """ Launches all the shards """
        if self.automatic_shards:
            self.shard_count, self.max_concurrency = await self._fetch_gateway()

            if self.shard_count == 1:
                # There is no need to shard if there is only 1 shard
                _log.debug("Sharding disabled, no point in sharding 1 shard")
                self.shard_count = None
                self.max_concurrency = None

        _shard_count = self.shard_count or 1
        shard_ids = self.shard_ids or range(_shard_count)

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
                _booting: list[Coroutine] = [
                    self._launch_shard(shard_id)
                    for shard_id in shard_chunk
                ]

                _log.debug(f"Launching bucket {i}/{len(chunks)}")
                await asyncio.gather(*_booting)

                if i != len(chunks):
                    _log.debug(f"Bucket {i}/{len(chunks)} shards launched, waiting (5s/bucket)")
                    await asyncio.sleep(5)
                else:
                    _log.debug(f"Bucket {i}/{len(chunks)} shards launched, last bucket, skipping wait")

            _log.debug(f"All {len(chunks)} bucket(s) have launched a total of {_shard_count} shard(s)")

        asyncio.create_task(self._delay_full_ready())

    async def _delay_full_ready(self) -> None:
        _waiting: list[Coroutine] = [
            g.wait_until_ready()
            for g in self.__shards.values()
        ]

        # Gather all shards to now wait until they are ready
        await asyncio.gather(*_waiting)

        self.bot._shards_ready.set()
        _log.info("discord.http/gateway is now ready")

    def start(self) -> None:
        """ Start the gateway client """
        self.bot.loop.create_task(self._launch_all_shards())

    async def close(self) -> None:
        """ Close the gateway client """
        async def _close():
            to_close = [
                asyncio.ensure_future(shard.close(kill=True))
                for shard in self.__shards.values()
            ]

            if to_close:
                await asyncio.wait(to_close)

        _task = asyncio.create_task(_close())
        await _task
