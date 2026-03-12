import time

from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING

from .. import utils
from ..automod import AutoModRuleAction, PartialAutoModRule
from ..colour import Colour
from ..emoji import EmojiParser
from ..enums import ReactionType, AutoModRuleTriggerType
from ..message import PartialMessage

from .activity import Activity
from .enums import StatusType, PollVoteActionType, ActivityType

if TYPE_CHECKING:
    from ..channel import BaseChannel, PartialChannel, Thread
    from ..guild import Guild, PartialGuild
    from ..http import DiscordAPI
    from ..member import Member, PartialMember, PartialThreadMember, ThreadMember
    from ..user import User, PartialUser

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
    """ Represents the playing status of the bot. """
    __slots__ = (
        "name",
        "since",
        "status",
        "type",
        "url",
    )

    def __init__(
        self,
        *,
        name: str | None = None,
        status: StatusType | str | int | None = None,
        type: ActivityType | str | int | None = None,  # noqa: A002
        url: str | None = None,
    ):
        self.since: int | None = None
        """ The timestamp of when the activity started, if applicable. """

        self.name = name
        """ The name of the activity, if any. """

        self.status: StatusType | str | int | None = status
        """ The status of the activity, if any. """

        self.type: ActivityType | str | int | None = type
        """ The type of the activity, if any. """

        if isinstance(self.status, str):
            self.status = StatusType[self.status]
        elif isinstance(self.status, int):
            self.status = StatusType(self.status)

        if isinstance(self.type, str):
            self.type = ActivityType[self.type]
        elif isinstance(self.type, int):
            self.type = ActivityType(self.type)

        self.url = None
        """ The url of the activity, if any. Only applicable for streaming activities. """

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

            if self.type is ActivityType.custom:
                payload["activities"][0]["state"] = self.name

            elif self.type is None:
                # Fallback to playing if no type is provided but name is
                payload["activities"][0]["type"] = int(ActivityType.playing)

        return payload


class GuildJoinRequest:
    """ Represents a guild join request event. """

    __slots__ = (
        "_state",
        "guild",
        "last_seen",
        "rejection_reason",
        "status",
        "user",
        "user_id",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: "Guild | PartialGuild",
        data: dict
    ):
        self._state = state

        self.status: str = data["status"]
        """ The status of the join request. Can be "pending", "accepted", or "rejected". """

        self.rejection_reason: str | None = None
        """ The reason the join request was rejected, if applicable. """

        self.user: User | None = None
        """ The user that made the join request, or `None` if the user is not available. """

        self.user_id: int | None = None
        """ The ID of the user that made the join request, if available. """

        self.guild: "Guild | PartialGuild" = guild
        """ The guild the join request was made to. """

        self.last_seen: datetime | None = None
        """ The last time the user was seen in the guild, if applicable. """

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


class ChannelPinsUpdate:
    """ Represents a channel pins update event. """

    __slots__ = (
        "channel",
        "guild",
        "last_pin_timestamp",
    )

    def __init__(
        self,
        channel: "BaseChannel | PartialChannel",
        last_pin_timestamp: "datetime | None",
        guild: "PartialGuild | Guild | None",
    ):
        self.channel: "BaseChannel | PartialChannel" = channel
        """ The channel the pins were updated in. """

        self.guild: "PartialGuild | Guild | None" = guild
        """ The guild the channel is in. If the channel is a DM channel, this will be `None`. """

        self.last_pin_timestamp: "datetime | None" = last_pin_timestamp
        """ The last time a pin was updated in the channel. """


class Presence:
    """ Represents a presence update event. """

    __slots__ = (
        "_state",
        "activities",
        "desktop",
        "guild",
        "mobile",
        "status",
        "type",
        "user",
        "web",
    )

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
        """ The user the presence update is for. """

        self.guild = guild
        """ The guild the presence update is for. """

        self.status: StatusType = StatusType[data["status"]]
        """ The status of the presence update. """

        self.activities: list[Activity] = [
            Activity(state=self._state, data=g)
            for g in data.get("activities", [])
        ]
        """ The activities of the presence update. """

        self.desktop: StatusType | None = None
        """ The desktop status of the presence update, if applicable. """

        self.mobile: StatusType | None = None
        """ The mobile status of the presence update, if applicable. """

        self.web: StatusType | None = None
        """ The web status of the presence update, if applicable. """

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


class TypingStartEvent:
    """ Represents a typing start event. """

    __slots__ = (
        "channel",
        "guild",
        "timestamp",
        "user",
    )

    def __init__(
        self,
        *,
        guild: "PartialGuild | Guild | None",
        channel: "BaseChannel | PartialChannel",
        user: "PartialUser | User | Member | PartialMember",
        timestamp: "datetime",
    ):
        self.guild: "PartialGuild | Guild | None" = guild
        """ The guild the typing event was triggered in. If the channel is a DM channel, this will be `None`. """

        self.channel: "BaseChannel | PartialChannel" = channel
        """ The channel the typing event was triggered in. """

        self.user: "PartialUser | User | Member | PartialMember" = user
        """ The user that started typing. """

        self.timestamp: "datetime" = timestamp
        """ The time the user started typing. """


class AutomodExecution:
    """ Represents an automod execution event. """

    __slots__ = (
        "_state",
        "action",
        "alert_system_message_id",
        "channel",
        "content",
        "guild",
        "matched_content",
        "matched_keyword",
        "message_id",
        "rejection_reason",
        "rule_id",
        "rule_trigger_type",
        "user",
    )

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
        """ The action that was taken by the automod rule. """

        self.rule_id: int = int(data["rule_id"])
        """ The ID of the automod rule that was triggered. """

        self.rule_trigger_type: AutoModRuleTriggerType = AutoModRuleTriggerType(data["rule_trigger_type"])
        """ The trigger type of the automod rule that was triggered. """

        self.guild: "Guild | PartialGuild" = guild
        """ The guild the automod execution was triggered in. """

        self.channel: "PartialChannel | None" = channel
        """ The channel the automod execution was triggered in, if applicable. """

        self.user: "Member | PartialMember" = user
        """ The user that triggered the automod execution. """

        self.message_id: int | None = utils.get_int(data, "message_id")
        """ The ID of the message that triggered the automod execution, if applicable. """

        self.alert_system_message_id: int | None = utils.get_int(data, "alert_system_message_id")
        """ The ID of the system message that was sent as an alert for the automod execution, if applicable. """

        self.content: str | None = data.get("content")
        """ The content that triggered the automod execution, if applicable. """

        self.matched_keyword: str | None = data.get("matched_keyword")
        """ The keyword that triggered the automod execution, if applicable. """

        self.matched_content: str | None = data.get("matched_content")
        """ The content that matched the keyword and triggered the automod execution, if applicable. """

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
    """ Represents a poll vote event. """

    __slots__ = (
        "_state",
        "answer_id",
        "channel",
        "guild",
        "message",
        "type",
        "user",
    )

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
        """ The user that made the vote. """

        self.guild: "PartialGuild | None" = guild
        """ The guild the poll is in. If the poll is in a DM channel, this will be `None`. """

        self.channel: "PartialChannel" = channel
        """ The channel the poll is in. """

        self.message: PartialMessage = PartialMessage(
            state=self._state,
            id=int(data["message_id"]),
            channel_id=self.channel.id,
            guild_id=self.guild.id if self.guild else None
        )
        """ The message the poll is in. """

        self.type: PollVoteActionType = type
        """ The type of the poll vote action, either "vote" or "unvote". """

        self.answer_id: int = int(data["answer_id"])
        """ The ID of the answer that was voted or unvoted. """

    def __repr__(self) -> str:
        return (
            f"<PollVoteEvent user={self.user} "
            f"answer={self.answer_id} type={self.type}>"
        )


class Reaction:
    """ Represents a reaction event. """

    __slots__ = (
        "_state",
        "burst",
        "burst_colour",
        "channel_id",
        "emoji",
        "guild_id",
        "id",
        "member",
        "message_author_id",
        "message_id",
        "type",
        "user_id",
    )

    def __init__(self, *, state: "DiscordAPI", data: dict):
        self._state = state

        self.user_id: int = int(data["user_id"])
        """ The ID of the user that made the reaction. """

        self.channel_id: int = int(data["channel_id"])
        """ The ID of the channel the reaction was made in. """

        self.message_id: int = int(data["message_id"])
        """ The ID of the message the reaction was made to. """

        self.guild_id: int | None = utils.get_int(data, "guild_id")
        """ The ID of the guild the reaction was made in, or `None` if the reaction was made in a DM channel. """

        self.message_author_id: int | None = utils.get_int(data, "message_author_id")
        """ The ID of the user that authored the message the reaction was made to, or `None` if the message author is not available. """

        self.member: "Member | None" = None
        """ The member that made the reaction, or `None` if the member is not available. """

        self.emoji: EmojiParser = EmojiParser.from_dict(data["emoji"])
        """ The emoji that was reacted with. """

        self.burst: bool = data["burst"]
        """ Whether the reaction is a burst reaction. """

        self.burst_colour: Colour | None = None
        """ The colour of the burst reaction, if applicable. """

        self.type: ReactionType = ReactionType(data["type"])
        """ The type of the reaction. """

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
    """ Represents a bulk delete event. """

    __slots__ = (
        "_state",
        "channel",
        "guild",
        "messages",
    )

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
        """ The guild the messages were deleted in. """

        self.channel: "BaseChannel | PartialChannel" = channel
        """ The channel the messages were deleted in. """

        self.messages: list[PartialMessage] = [
            PartialMessage(
                state=self._state,
                id=int(g),
                guild_id=guild.id,
                channel_id=channel.id,
            )
            for g in data["ids"]
        ]
        """ The messages that were deleted. """


class ThreadListSyncPayload:
    """ Represents a thread list sync payload. """

    __slots__ = (
        "_members",
        "_state",
        "_threads",
        "channel_ids",
        "guild_id",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ):
        self._state = state

        self.guild_id: int = int(data["guild_id"])
        """ The guild ID the thread list sync is for. """

        self.channel_ids: list[int] = [int(c) for c in data.get("channel_ids", [])]
        """
        The parent channel IDs whose threads are being synced.
        If this is empty, it means all threads in the guild are being synced.
        This may contains ids of channels that have no active threads.
        """

        self._threads: list[dict] = data["threads"]
        self._members: list[dict] = data["members"]

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
    """ Represents a thread members update's payload. """

    __slots__ = (
        "_added_members",
        "_state",
        "guild_id",
        "id",
        "member_count",
        "removed_member_ids",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ):
        self._state = state

        self.id: int = int(data["id"])
        """ The ID of the thread. """

        self.guild_id: int = int(data["guild_id"])
        """ The guild ID the thread is in. """

        self.member_count: int = data["member_count"]
        """ The total number of members in the thread, capped at 50. """

        self.removed_member_ids: list[int] = data.get("removed_member_ids", [])
        """ The IDs of the members that were removed from the thread. """

        self._added_members: list[dict] = data.get("added_members", [])

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
                data=m,
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
