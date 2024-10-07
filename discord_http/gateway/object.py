from typing import TYPE_CHECKING, Iterator
from datetime import datetime

from .activity import Activity
from .enums import StatusType

from .. import utils
from ..colour import Colour
from ..emoji import EmojiParser
from ..enums import ReactionType
from ..message import PartialMessage

if TYPE_CHECKING:
    from ..types.channels import (
        ThreadListSync,
        ThreadMembersUpdate
    )
    from ..types.guilds import (
        ThreadMember as ThreadMemberPayload,
        ThreadMemberWithMember as ThreadMemberWithMember
    )

    from ..guild import Guild, PartialGuild
    from ..http import DiscordAPI
    from ..member import Member, PartialMember, PartialThreadMember, ThreadMember
    from ..user import User, PartialUser
    from ..channel import BaseChannel, PartialChannel, Thread

__all__ = (
    "ChannelPinsUpdate",
    "TypingStartEvent",
    "BulkDeletePayload",
    "Reaction",
    "ThreadListSyncPayload",
    "Presence",
    "ThreadMembersUpdatePayload",
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
    ):
        self.channel: "BaseChannel | PartialChannel" = channel
        self.guild: "PartialGuild | Guild | None" = guild
        self.last_pin_timestamp: "datetime | None" = last_pin_timestamp


class Presence:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        user: "Member | PartialMember",
        guild: "PartialGuild | Guild",
        data: dict
    ):
        self._state = state

        self.user = user
        self.guild = guild
        self.status: StatusType = StatusType[data["status"]]
        self.activities: list[Activity] = [
            Activity(state=self._state, data=g)
            for g in data.get("activities", [])
        ]

        self.desktop: StatusType | None = None
        self.mobile: StatusType | None = None
        self.web: StatusType | None = None

        self._from_data(data)

    def __repr__(self) -> str:
        return (
            f"<Presence user={self.user} "
            f"guild={self.guild} activities={len(self.activities)}>"
        )

    def _from_data(self, data: dict) -> None:
        _client_status = data.get("client_status", {})
        if _client_status.get("desktop", None):
            self.desktop = StatusType[_client_status["desktop"]]

        if _client_status.get("mobile", None):
            self.mobile = StatusType[_client_status["mobile"]]

        if _client_status.get("web", None):
            self.web = StatusType[_client_status["web"]]


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
    ):
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


class ThreadListSyncPayload:
    """Represents a thread list sync payload.

    Attributes
    ----------
    guild_id: `int`
        The guild ID the threads are in.
    channel_ids: `list`[`int`]
        The parent channel IDs whose threads are being synced.
        If this is empty, it means all threads in the guild are being synced.

        This may contains ids of channels that have no active threads.
    """
    __slots__ = (
        "_state",
        "guild_id",
        "channel_ids",
        "_threads",
        "_members",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: "ThreadListSync",
    ):
        self._state = state

        self.guild_id: int = int(data["guild_id"])
        self.channel_ids: list[int] = [int(c) for c in data.get("channel_ids", [])]
        self._threads: list[dict] = data["threads"]
        self._members: list[ThreadMemberPayload] = data["members"]

    @property
    def guild(self) -> "PartialGuild":
        bot = self._state.bot
        return bot.cache.get_guild(self.guild_id) or bot.get_partial_guild(self.guild_id)

    @property
    def threads(self) -> list["Thread"]:
        if not self._threads:
            return []

        from ..channel import Thread

        state = self._state
        return [Thread(state=state, data=t) for t in self._threads]

    @property
    def members(self) -> list["PartialThreadMember"]:
        if not self._members:
            return []

        from ..member import PartialThreadMember

        guild = self.guild
        state = self._state
        return [
            PartialThreadMember(
                state=state,
                data=m,
                guild_id=guild.id,
            )
            for m in self._members
        ]

    @property
    def channels(self) -> list["PartialChannel"]:
        if not self.channel_ids:
            return []

        return [
            self.guild.get_channel(c) or self.guild.get_partial_channel(c)
            for c in self.channel_ids
        ]

    def __repr__(self) -> str:
        return f"<ThreadListSyncPayload guild_id={self.guild_id}>"

    def combined(self) -> Iterator[
        tuple["PartialChannel", tuple["Thread", list["PartialThreadMember"]]]
    ]:
        channels = self.channels
        threads = self.threads
        members = self.members

        channels_per_id = {c.id: c for c in channels}

        for thread in threads:
            parent_id = thread.parent_id
            if not parent_id:
                continue

            parent_channel = channels_per_id.get(parent_id)
            if not parent_channel:
                continue

            thread_members = []
            for member in members:
                if member.id == thread.id:
                    thread_members.append(member)

            yield (parent_channel, (thread, thread_members))


class ThreadMembersUpdatePayload:
    """Represents a thread members update's payload.

    Attributes
    ----------
    id: `int`
        The ID of the thread.
    guild_id: `int`
        The guild ID the thread is in.
    member_count: `int`
        The total number of members in the thread, capped at 50.
    removed_member_ids: `list[int]`
        The IDs of the members that were removed from the thread.
    """
    __slots__ = (
        "_state",
        "id",
        "guild_id",
        "member_count",
        "_added_members",
        "removed_member_ids",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: "ThreadMembersUpdate",
    ):
        self._state = state

        self.id: int = int(data["id"])
        self.guild_id: int = int(data["guild_id"])
        self.member_count: int = data["member_count"]
        self.removed_member_ids: list[int] = data.get("removed_member_ids", [])

        self._added_members: list[ThreadMemberWithMember] = data.get("added_members", [])

    @property
    def guild(self) -> "PartialGuild":
        """ `PartialGuild`: The guild the thread is in """
        bot = self._state.bot
        return bot.cache.get_guild(self.guild_id) or bot.get_partial_guild(self.guild_id)

    @property
    def thread(self) -> "PartialChannel | Thread":
        """ `PartialChannel` | `Thread`: The thread the members were updated in """
        return self.guild.get_channel(self.id) or self.guild.get_partial_channel(self.id)

    @property
    def added_members(self) -> list["ThreadMember"]:
        """ list[PartialThreadMember]: The members that were added to the thread """
        if not self._added_members:
            return []

        guild = self.guild
        state = self._state

        from ..member import ThreadMember

        return [
            ThreadMember(
                state=state,
                guild=guild,
                data=m,  # type: ignore
            )
            for m in self._added_members
        ]

    @property
    def removed_members(self) -> list["PartialMember"]:
        """ list[PartialMember]: The members that were removed from the thread """
        if not self.removed_member_ids:
            return []

        return [
            self.guild.get_member(m) or self.guild.get_partial_member(m)
            for m in self.removed_member_ids
        ]

    def __repr__(self) -> str:
        return f"<ThreadMembersUpdatePayload id={self.id} guild_id={self.guild_id}>"
