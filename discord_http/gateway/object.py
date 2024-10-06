from datetime import datetime
from typing import TYPE_CHECKING

from .. import utils
from ..colour import Colour
from ..emoji import EmojiParser
from ..enums import ReactionType
from ..message import PartialMessage

if TYPE_CHECKING:
    from ..channel import BaseChannel, PartialChannel
    from ..guild import Guild, PartialGuild
    from ..http import DiscordAPI
    from ..member import Member, PartialMember
    from ..user import User, PartialUser

__all__ = (
    "ChannelPinsUpdate",
    "TypingStartEvent",
    "BulkDeletePayload",
    "Reaction",
)


class ChannelPinsUpdate:
    """Represents a channel pins update event.

    Attributes
    ----------
    channel: `BaseChannel` | `PartialChannel`
        The channel the pins were updated in.
    last_pin_timestamp: `datetime` | `None`
        The last time a pin was updated in the channel.
    guild: `PartialGuild` | `Guild` | `None`
        The guild the channel is in. If the channel is a DM channel, this will be `None`.
    """
    def __init__(
        self,
        channel: "BaseChannel | PartialChannel",
        last_pin_timestamp: "datetime | None",
        guild: "PartialGuild | Guild | None",
    ) -> None:
        self.channel: "BaseChannel | PartialChannel" = channel
        self.guild: "PartialGuild | Guild | None" = guild
        self.last_pin_timestamp: "datetime | None" = last_pin_timestamp


class TypingStartEvent:
    """Represents a typing start event.

    Attributes
    ----------
    guild: `PartialGuild` | `Guild` | `None`
        The guild the typing event was triggered in. If the channel is a DM channel, this will be `None`.
    channel: `BaseChannel` | `PartialChannel` | `None`
        The channel the typing event was triggered in.
    user: `PartialUser` | `User` | `Member` | `PartialMember`
        The user that started typing.
    timestamp: `datetime`
        The time the user started typing.
    """
    def __init__(
        self,
        *,
        guild: "PartialGuild | Guild | None",
        channel: "BaseChannel | PartialChannel",
        user: "PartialUser | User | Member | PartialMember",
        timestamp: "datetime",
    ) -> None:
        self.guild: "PartialGuild | Guild | None" = guild
        self.channel: "BaseChannel | PartialChannel" = channel
        self.user: "PartialUser | User | Member | PartialMember" = user
        self.timestamp: "datetime" = timestamp


class Reaction:
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self._state = state

        self.user_id: int = int(data["user_id"])
        self.channel_id: int = int(data["channel_id"])
        self.message_id: int = int(data["message_id"])

        self.guild_id: int | None = utils.get_int(data, "guild_id")
        self.message_author_id: int | None = utils.get_int(data, "message_author_id")
        self.member: "Member | None" = None

        self.emoji: EmojiParser = EmojiParser.from_dict(data["emoji"])

        self.burst: bool = data["burst"]
        self.burst_colour: Colour | None = None

        self.type: ReactionType = ReactionType(data["type"])

        self._from_data(data)

    def __repr__(self) -> str:
        return (
            f"<Reaction channel_id={self.channel_id} "
            f"message_id={self.message_id} emoji={self.emoji}>"
        )

    def _from_data(self, data: dict) -> None:
        if data.get("burst_colour", None):
            self.burst_colour = Colour.from_hex(data["burst_colour"])

        if data.get("member", None):
            from ..member import Member
            self.member = Member(
                state=self._state,
                guild=self.guild,  # type: ignore
                data=data["member"]
            )

    @property
    def guild(self) -> "PartialGuild | None":
        """ `PartialGuild` | `None`: The guild the message was sent in """
        if not self.guild_id:
            return None

        from ..guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "PartialChannel | None":
        """ `PartialChannel` | `None`: Returns the channel the message was sent in """
        if not self.channel_id:
            return None

        from ..channel import PartialChannel
        return PartialChannel(state=self._state, id=self.channel_id)

    @property
    def message(self) -> "PartialMessage | None":
        """ `PartialMessage` | `None`: Returns the message if a message_id is available """
        if not self.channel_id or not self.message_id:
            return None

        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            id=self.message_id
        )


class BulkDeletePayload:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild"
    ):
        self._state = state

        self.messages: list[PartialMessage] = [
            PartialMessage(
                state=self._state,
                id=int(g),
                channel_id=int(data["channel_id"]),
            )
            for g in data["ids"]
        ]

        self.guild: "PartialGuild" = guild
