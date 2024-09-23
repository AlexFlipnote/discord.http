from typing import Optional

from .. import PartialGuild

# TODO
# - Add an optional cache for multiple data types
# - Be able to dynamically update the cache

__all__ = (
    "Cache",
)


class Cache:
    # This is subject to change, and should not be relied on
    def __init__(self):
        self.guilds: dict[int, PartialGuild] = {}

    def get_guild(self, guild_id: int) -> Optional[PartialGuild]:
        return self.guilds.get(guild_id, None)

    def add_guild(self, guild_id: int, guild: PartialGuild) -> None:
        self.guilds[guild_id] = guild

    def remove_guild(self, guild_id: int) -> Optional[PartialGuild]:
        return self.guilds.pop(guild_id, None)
