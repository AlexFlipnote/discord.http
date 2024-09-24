from typing import TYPE_CHECKING

from ..message import Message, PartialMessage
from ..guild import Guild, PartialGuild

if TYPE_CHECKING:
    from ..client import Client

__all__ = (
    "Parser",
)


class Parser:
    def __init__(self, bot: "Client"):
        self.bot = bot

    def _guild(self, data: dict) -> Guild:
        return Guild(
            state=self.bot.state,
            data=data
        )

    def guild_create(self, data: dict) -> Guild:
        g = self._guild(data)
        self.bot.cache.add_guild(g.id, g)
        return g

    def guild_update(self, data: dict) -> Guild:
        g = self._guild(data)
        self.bot.cache.add_guild(g.id, g)
        return g

    def guild_delete(self, data: dict) -> PartialGuild:
        return self.bot.get_partial_guild(data["id"])

    def _message(self, data: dict) -> Message:
        guild_id = data.get("guild_id", None)

        return Message(
            state=self.bot.state,
            data=data,
            guild=(
                self.bot.get_partial_guild(guild_id)
                if guild_id else None
            )
        )

    def message_create(self, data: dict) -> Message:
        return self._message(data)

    def message_update(self, data: dict) -> Message:
        return self._message(data)

    def message_delete(self, data: dict) -> PartialMessage:
        return self.bot.get_partial_message(
            message_id=int(data["id"]),
            channel_id=int(data["channel_id"]),
        )
