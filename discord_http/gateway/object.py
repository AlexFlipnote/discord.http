from datetime import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..guild import Guild, PartialGuild
    from ..channel import BaseChannel, PartialChannel
    from ..member import Member, PartialMember
    from ..user import User, PartialUser


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
