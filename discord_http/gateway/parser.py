from .. import Client, Message, PartialMessage

__all__ = (
    "Parser",
)


class Parser:
    def __init__(self, bot: Client):
        self.bot = bot

    def message_create(self, data: dict) -> Message:
        guild_id = data.get("guild_id", None)

        return Message(
            state=self.bot.state,
            data=data,
            guild=(
                self.bot.get_partial_guild(guild_id)
                if guild_id else None
            )
        )

    def message_delete(self, data: dict) -> PartialMessage:
        return self.bot.get_partial_message(
            message_id=int(data["id"]),
            channel_id=int(data["channel_id"]),
        )
