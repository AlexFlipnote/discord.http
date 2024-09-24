from typing import Optional, Union, TYPE_CHECKING

from .flags import GatewayCacheFlags

if TYPE_CHECKING:
    from ..client import Client
    from ..guild import PartialGuild, Guild

__all__ = (
    "Cache",
)


class Cache:
    # This is subject to change, and should not be relied on
    def __init__(
        self,
        *,
        client: "Client"
    ):
        self.client = client
        self.cache_flags = client._gateway_cache

        self.__guilds: dict[int, Union["PartialGuild", "Guild"]] = {}

    @property
    def guilds(self) -> list[Union["PartialGuild", "Guild"]]:
        return list(self.__guilds.values())

    def get_guild(self, guild_id: int) -> Optional[Union["PartialGuild", "Guild"]]:
        return self.__guilds.get(guild_id, None)

    def add_guild(self, guild_id: int, guild: Union["PartialGuild", "Guild"]) -> None:
        if self.cache_flags is None:
            return None

        if GatewayCacheFlags.guild in self.cache_flags:
            self.__guilds[guild_id] = guild
        elif GatewayCacheFlags.partial_guild in self.cache_flags:
            self.__guilds[guild_id] = self.client.get_partial_guild(guild_id)

    def remove_guild(self, guild_id: int) -> Optional[Union["PartialGuild", "Guild"]]:
        if self.cache_flags is None:
            return None

        return self.__guilds.pop(guild_id, None)
