import time

from typing import TYPE_CHECKING
from collections.abc import Iterator
from datetime import datetime

from .activity import Activity
from .enums import StatusType, PollVoteActionType, ActivityType

from .. import utils
from ..automod import AutoModRuleAction, PartialAutoModRule
from ..colour import Colour
from ..emoji import EmojiParser
from ..enums import ReactionType, AutoModRuleTriggerType
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
    "AutomodExecution",
    "BulkDeletePayload",
    "ChannelPinsUpdate",
    "GuildJoinRequest",
    "PlayingStatus",
    "PollVoteEvent",
    "Presence",
    "Reaction",
    "ThreadListSyncPayload",
    "ThreadMembersUpdatePayload",
    "TypingStartEvent",
)


class PlayingStatus:
    def __init__(
        self,
        *,
        name: str | None = None,
        status: StatusType | str | int | None = None,
        type: ActivityType | str | int | None = None,  # noqa: A002
        url: str | None = None,
        state: str | None = None,
    ):
        self.since: int | None = None
        self.name = name
        self.status: StatusType | str | int | None = status
        self.type: ActivityType | str | int | None = type
        self.state = state

        if isinstance(self.status, str):
            self.status = StatusType[self.status]
        elif isinstance(self.status, int):
            self.status = StatusType(self.status)

        if isinstance(self.type, str):
            self.type = ActivityType[self.type]
        elif isinstance(self.type, int):
            self.type = ActivityType(self.type)

        self.url = None
        if self.type == ActivityType.streaming:
            self.url = str(url)

        if self.status == StatusType.idle:
            self.since = int(time.time() * 1_000)

    def __repr__(self) -> str:
        return (
            f"<PlayingStatus name={self.name} "
            f"status={self.status} type={self.type}>"
        )

    def to_dict(self) -> dict:
        """ The playing status as a dictionary. """
        payload = {
            "afk": False,
            "since": self.since,
            "status": str(self.status),
            "activities": [{}]
        }

        if self.url:
            payload["activities"][0]["url"] = self.url

        if self.type is not None:
            payload["activities"][0]["type"] = int(self.type)

        if self.name is not None:
            payload["activities"][0]["name"] = self.name

            if self.type is None:
                # Fallback to playing if no type is provided but name is
                payload["activities"][0]["type"] = int(ActivityType.playing)

        if self.type == ActivityType.custom:
            payload["activities"][0]["name"] = "Custom Status"

            if self.state is not None:
                payload["activities"][0]["state"] = self.state
            elif self.name is not None:
                payload["activities"][0]["state"] = self.name

        return payload


class GuildJoinRequest:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: "Guild | PartialGuild",
        data: dict
    ):
        self._state = state

        self.status: str = data["status"]
        self.rejection_reason: str | None = None

        self.user: User | None = None
        self.user_id: int | None = None

        self.guild: "Guild | PartialGuild" = guild
        self.last_seen: datetime | None = None

        self._from_data(data)

    def _from_data(self, data: dict) -> None:
        request = data.get("request", {})
        if request:
            self.user_id = utils.get_int(request, "user_id")

            if request.get("user", None):
                from ..user import User
                self.user = User(
                    state=self._state,
                    data=request["user"]
                )

            self.rejection_reason = request.get("rejection_reason", None)


class ChannelPinsUpdate:  # noqa: B903
    """
    Represents a channel pins update event.

    Attributes
    ----------
    channel:
        The channel the pins were updated in.
    last_pin_timestamp:
        The last time a pin was updated in the channel.
    guild:
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
        client_status = data.get("client_status", {})
        if client_status.get("desktop", None):
            self.desktop = StatusType[client_status["desktop"]]

        if client_status.get("mobile", None):
            self.mobile = StatusType[client_status["mobile"]]

        if client_status.get("web", None):
            self.web = StatusType[client_status["web"]]


class TypingStartEvent:  # noqa: B903
    """
    Represents a typing start event.

    Attributes
    ----------
    guild:
        The guild the typing event was triggered in. If the channel is a DM channel, this will be `None`.
    channel:
        The channel the typing event was triggered in.
    user:
        The user that started typing.
    timestamp:
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


class AutomodExecution:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: "PartialGuild | Guild",
        channel: "PartialChannel | None",
        user: "Member | PartialMember",
        data: dict
    ):
        self._state = state

        self.action: AutoModRuleAction = AutoModRuleAction.from_dict(data["action"])
        self.rule_id: int = int(data["rule_id"])
        self.rule_trigger_type: AutoModRuleTriggerType = AutoModRuleTriggerType(data["rule_trigger_type"])

        self.guild: "Guild | PartialGuild" = guild
        self.channel: "PartialChannel | None" = channel
        self.user: "Member | PartialMember" = user

        self.message_id: int | None = utils.get_int(data, "message_id")
        self.alert_system_message_id: int | None = utils.get_int(data, "alert_system_message_id")
        self.content: str | None = data.get("content")

        self.matched_keyword: str | None = data.get("matched_keyword")
        self.matched_content: str | None = data.get("matched_content")

    def __repr__(self) -> str:
        return (
            f"<AutomodExecution guild={self.guild} "
            f"user={self.user} action={self.action}>"
        )

    @property
    def rule(self) -> PartialAutoModRule:
        """ Returns a partial object of automod rule. """
        return PartialAutoModRule(
            state=self._state,
            id=self.rule_id,
            guild_id=self.guild.id
        )


class PollVoteEvent:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        user: "Member | PartialMember | PartialUser",
        channel: "PartialChannel",
        guild: "PartialGuild | None",
        type: PollVoteActionType,  # noqa: A002
        data: dict
    ):
        self._state = state

        self.user: "Member | PartialMember | PartialUser" = user
        self.guild: "PartialGuild | None" = guild
        self.channel: "PartialChannel" = channel
        self.message: PartialMessage = PartialMessage(
            state=self._state,
            id=int(data["message_id"]),
            channel_id=self.channel.id,
            guild_id=self.guild.id if self.guild else None
        )

        self.type: PollVoteActionType = type
        self.answer_id: int = int(data["answer_id"])

    def __repr__(self) -> str:
        return (
            f"<PollVoteEvent user={self.user} "
            f"answer={self.answer_id} type={self.type}>"
        )


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
        if data.get("burst_colour"):
            self.burst_colour = Colour.from_hex(data["burst_colour"])

        if data.get("member"):
            from ..member import Member
            self.member = Member(
                state=self._state,
                guild=self.guild,  # type: ignore
                data=data["member"]
            )

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ The guild the message was sent in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from ..guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "PartialChannel | None":
        """
        Returns the channel the message was sent in.

        If guild and channel cache is enabled, it can also return full channel object.
        """
        if not self.channel_id:
            return None

        if self.guild_id:
            cache = self._state.cache.get_channel_thread(
                guild_id=self.guild_id,
                channel_id=self.channel_id
            )

            if cache:
                return cache

        from ..channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    @property
    def message(self) -> "PartialMessage | None":
        """ Returns the message if a message_id is available. """
        if not self.channel_id or not self.message_id:
            return None

        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            guild_id=self.guild_id,
            id=self.message_id
        )


class BulkDeletePayload:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild",
        channel: "BaseChannel | PartialChannel"
    ):
        self._state = state
        self.guild: "Guild | PartialGuild" = guild
        self.channel: "BaseChannel | PartialChannel" = channel

        self.messages: list[PartialMessage] = [
            PartialMessage(
                state=self._state,
                id=int(g),
                guild_id=guild.id,
                channel_id=channel.id,
            )
            for g in data["ids"]
        ]


class ThreadListSyncPayload:
    """
    Represents a thread list sync payload.

    Attributes
    ----------
    guild_id:
        The guild ID the threads are in.
    channel_ids: ]
        The parent channel IDs whose threads are being synced.
        If this is empty, it means all threads in the guild are being synced.

        This may contains ids of channels that have no active threads.
    """
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
        """ The guild the thread is in. """
        bot = self._state.bot
        return bot.cache.get_guild(self.guild_id) or bot.get_partial_guild(self.guild_id)

    @property
    def threads(self) -> list["Thread"]:
        """ The threads in the thread list. """
        if not self._threads:
            return []

        from ..channel import Thread

        state = self._state
        return [Thread(state=state, data=t) for t in self._threads]

    @property
    def members(self) -> list["PartialThreadMember"]:
        """ The members in the thread list. """
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
        """ The channels in the thread list. """
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
        """ Returns a combined iterator of channels and threads. """
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
    """
    Represents a thread members update's payload.

    Attributes
    ----------
    id:
        The ID of the thread.
    guild_id:
        The guild ID the thread is in.
    member_count:
        The total number of members in the thread, capped at 50.
    removed_member_ids:
        The IDs of the members that were removed from the thread.
    """
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
        """ The guild the thread is in. """
        bot = self._state.bot
        return bot.cache.get_guild(self.guild_id) or bot.get_partial_guild(self.guild_id)

    @property
    def thread(self) -> "PartialChannel | Thread":
        """ The thread the members were updated in. """
        return self.guild.get_channel(self.id) or self.guild.get_partial_channel(self.id)

    @property
    def added_members(self) -> list["ThreadMember"]:
        """ list[PartialThreadMember]: The members that were added to the thread. """
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
        """ list[PartialMember]: The members that were removed from the thread. """
        if not self.removed_member_ids:
            return []

        return [
            self.guild.get_member(m) or self.guild.get_partial_member(m)
            for m in self.removed_member_ids
        ]

    def __repr__(self) -> str:
        return f"<ThreadMembersUpdatePayload id={self.id} guild_id={self.guild_id}>"
