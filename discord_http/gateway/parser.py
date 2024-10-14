from datetime import datetime
from typing import TYPE_CHECKING, overload

from .enums import PollVoteActionType
from .object import (
    ChannelPinsUpdate, TypingStartEvent,
    Reaction, BulkDeletePayload, ThreadListSyncPayload,
    ThreadMembersUpdatePayload, Presence, AutomodExecution,
    PollVoteEvent, GuildJoinRequest
)

from .. import utils
from ..audit import AuditLogEntry
from ..automod import AutoModRule
from ..channel import BaseChannel, PartialChannel, StageInstance
from ..emoji import Emoji
from ..enums import ChannelType
from ..guild import Guild, PartialGuild, ScheduledEvent, PartialScheduledEvent
from ..invite import Invite, PartialInvite
from ..member import Member, PartialMember, PartialThreadMember
from ..message import Message, PartialMessage
from ..role import Role, PartialRole
from ..soundboard import PartialSoundboardSound, SoundboardSound
from ..sticker import Sticker
from ..user import User, PartialUser
from ..voice import VoiceState
from ..integrations import Integration, PartialIntegration

if TYPE_CHECKING:
    from ..types import channels
    from ..client import Client

__all__ = (
    "Parser",
)


class Parser:
    def __init__(self, bot: "Client"):
        self.bot = bot

    @overload
    def _get_guild_or_partial(self, guild_id: None) -> None:
        ...

    @overload
    def _get_guild_or_partial(self, guild_id: int) -> "PartialGuild | Guild":
        ...

    def _get_guild_or_partial(self, guild_id: int | None) -> "PartialGuild | Guild | None":
        if not guild_id:
            return None

        return (
            self.bot.cache.get_guild(guild_id) or
            PartialGuild(state=self.bot.state, id=guild_id)
        )

    def _get_channel_or_partial(
        self,
        channel_id: int,
        guild_id: int | None = None
    ) -> "BaseChannel | PartialChannel":
        if not guild_id:
            return PartialChannel(state=self.bot.state, id=channel_id)

        guild = self._get_guild_or_partial(guild_id)
        return guild.get_channel(channel_id) or PartialChannel(
            state=self.bot.state,
            id=channel_id,
            guild_id=guild_id
        )

    @overload
    def _get_user_or_partial(
        self,
        user_id: int,
        guild_id: None
    ) -> "PartialUser | User":
        ...

    @overload
    def _get_user_or_partial(
        self,
        user_id: int,
        guild_id: int
    ) -> "Member | PartialMember":
        ...

    def _get_user_or_partial(
        self,
        user_id: int,
        guild_id: int | None
    ) -> "PartialUser | User | Member | PartialMember":
        state = self.bot.state
        if not guild_id:
            return PartialUser(state=state, id=user_id)

        guild = self._get_guild_or_partial(int(guild_id))
        return guild.get_member(user_id) or PartialMember(
            state=state, id=user_id, guild_id=guild.id
        )

    def _guild(self, data: dict) -> Guild:
        return Guild(
            state=self.bot.state,
            data=data
        )

    def guild_create(self, data: dict) -> tuple[Guild]:
        guild = self._guild(data)
        self.bot.cache.add_guild(guild.id, guild, data)

        for channel in guild.channels:
            self.bot.cache.add_channel(channel)
        for role in guild.roles:
            self.bot.cache.add_role(role)

        return (guild,)

    def guild_update(self, data: dict) -> tuple[Guild]:
        guild = self._guild(data)
        self.bot.cache.update_guild(guild.id, data)
        return (guild,)

    def guild_delete(self, data: dict) -> tuple[Guild | PartialGuild]:
        guild = self._get_guild_or_partial(int(data["id"]))
        self.bot.cache.remove_guild(guild.id)
        return (guild,)

    def guild_available(self, data: dict) -> tuple[Guild | PartialGuild]:
        _guild = self._get_guild_or_partial(int(data["id"]))

        return (_guild,)

    def guild_unavailable(self, data: dict) -> tuple[Guild | PartialGuild]:
        _guild = self._get_guild_or_partial(int(data["id"]))

        return (_guild,)

    def guild_member_add(self, data: dict) -> tuple[Guild | PartialGuild, Member]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            Member(state=self.bot.state, guild=_guild, data=data)
        )

    def guild_member_update(self, data: dict) -> tuple[Guild | PartialGuild, Member]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            Member(state=self.bot.state, guild=_guild, data=data)
        )

    def guild_member_remove(self, data: dict) -> tuple[Guild | PartialGuild, User]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))
        return (
            _guild,
            User(
                state=self.bot.state,
                data=data["user"]
            )
        )

    def guild_ban_add(self, data: dict) -> tuple[Guild | PartialGuild, User]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            User(
                state=self.bot.state,
                data=data["user"]
            )
        )

    def guild_ban_remove(self, data: dict) -> tuple[Guild | PartialGuild, User]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            User(
                state=self.bot.state,
                data=data["user"]
            )
        )

    def guild_emojis_update(self, data: dict) -> tuple[Guild | PartialGuild, list[Emoji]]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            [
                Emoji(
                    state=self.bot.state,
                    guild=_guild,
                    data=e
                )
                for e in data["emojis"]
            ]
        )

    def guild_stickers_update(self, data: dict) -> tuple[Guild | PartialGuild, list[Sticker]]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            [
                Sticker(
                    state=self.bot.state,
                    guild=_guild,
                    data=e
                )
                for e in data["stickers"]
            ]
        )

    def guild_soundboard_sound_create(self, data: dict) -> tuple[SoundboardSound]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            SoundboardSound(
                state=self.bot.state,
                guild=_guild,
                data=data
            ),
        )

    def guild_soundboard_sound_update(self, data: dict) -> tuple[SoundboardSound]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            SoundboardSound(
                state=self.bot.state,
                guild=_guild,
                data=data
            ),
        )

    def guild_soundboard_sound_delete(self, data: dict) -> tuple[PartialSoundboardSound]:
        return (
            PartialSoundboardSound(
                state=self.bot.state,
                id=int(data["sound_id"]),
                guild_id=int(data["guild_id"])
            ),
        )

    def guild_soundboard_sounds_update(self, data: dict) -> tuple[PartialGuild, list[SoundboardSound]]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            _guild,
            [
                SoundboardSound(
                    state=self.bot.state,
                    guild=_guild,
                    data=e
                )
                for e in data["soundboard_sounds"]
            ]
        )

    def guild_audit_log_entry_create(self, data: dict) -> tuple[AuditLogEntry]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            AuditLogEntry(
                state=self.bot.state,
                data=data,
                guild=_guild
            ),
        )

    # NOTE: These are not documented in Discord API......
    # Need to play around and figure them out, UPDATE is what I got so far
    def guild_join_request_create(self, data: dict) -> tuple[None]:
        # print(("CREATE", data))
        return (None,)

    def guild_join_request_update(self, data: dict) -> tuple[GuildJoinRequest]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        return (
            GuildJoinRequest(
                state=self.bot.state,
                data=data,
                guild=_guild
            ),
        )

    def guild_join_request_delete(self, data: dict) -> tuple[None]:
        # print(("DELETE", data))
        return (None,)

    def _channel(self, data: dict) -> BaseChannel:
        return BaseChannel.from_dict(
            state=self.bot.state,
            data=data,
        )

    def _partial_channel(self, data: dict) -> PartialChannel:
        channel = PartialChannel.from_dict(
            state=self.bot.state,
            data=data,
        )

        if data.get("parent_id", None):
            channel.parent_id = int(data["parent_id"])
        if data.get("type", None):
            channel._raw_type = ChannelType(int(data["type"]))

        return channel

    def channel_create(self, data: dict) -> tuple[BaseChannel]:
        channel = self._channel(data)
        self.bot.cache.add_channel(channel)
        return (channel,)

    def channel_update(self, data: dict) -> tuple[BaseChannel]:
        channel = self._channel(data)
        self.bot.cache.add_channel(channel)
        return (channel,)

    def channel_delete(self, data: dict) -> tuple[BaseChannel]:
        channel = self._channel(data)
        self.bot.cache.remove_channel(channel)
        return (channel,)

    def channel_pins_update(self, data: dict) -> tuple[ChannelPinsUpdate]:
        guild_id: int | None = utils.get_int(data, "guild_id")
        channel_id: int = int(data["channel_id"])
        last_pin_timestamp: datetime | None = (
            utils.parse_time(_last_pin_timestamp)
            if (_last_pin_timestamp := data.get("last_pin_timestamp", None)) else None
        )

        return (
            ChannelPinsUpdate(
                channel=self._get_channel_or_partial(channel_id, guild_id),
                last_pin_timestamp=last_pin_timestamp,
                guild=self._get_guild_or_partial(guild_id)
            ),
        )

    def thread_create(self, data: dict) -> tuple[BaseChannel]:
        channel = self._channel(data)
        self.bot.cache.add_channel(channel)
        return (channel,)

    def thread_update(self, data: dict) -> tuple[BaseChannel]:
        channel = self._channel(data)
        self.bot.cache.add_channel(channel)
        return (channel,)

    def thread_delete(self, data: dict) -> tuple[PartialChannel]:
        thread = self._partial_channel(data)
        self.bot.cache.remove_channel(thread)
        return (thread,)

    def thread_list_sync(self, data: "channels.ThreadListSync") -> tuple[ThreadListSyncPayload]:
        return (ThreadListSyncPayload(state=self.bot.state, data=data),)

    def thread_member_update(self, data: "channels.ThreadMemberUpdate") -> tuple[PartialThreadMember]:
        return (
            PartialThreadMember(
                state=self.bot.state,
                data=data,
                guild_id=int(data["guild_id"])
            ),
        )

    def thread_members_update(self, data: "channels.ThreadMembersUpdate") -> tuple[ThreadMembersUpdatePayload]:
        return (ThreadMembersUpdatePayload(state=self.bot.state, data=data),)

    def _message(self, data: dict) -> Message:
        guild_id = utils.get_int(data, "guild_id")

        return Message(
            state=self.bot.state,
            data=data,
            guild=(
                self._get_guild_or_partial(guild_id)
                if guild_id else None
            )
        )

    def message_create(self, data: dict) -> tuple[Message]:
        return (self._message(data),)

    def message_update(self, data: dict) -> tuple[Message]:
        return (self._message(data),)

    def message_delete(self, data: dict) -> tuple[PartialMessage]:
        return (
            self.bot.get_partial_message(
                message_id=int(data["id"]),
                channel_id=int(data["channel_id"]),
                guild_id=utils.get_int(data, "guild_id"),
            ),
        )

    def message_delete_bulk(self, data: dict) -> tuple[BulkDeletePayload]:
        _guild = self._get_guild_or_partial(utils.get_int(data, "guild_id"))

        if _guild is None:
            raise ValueError("guild_id somehow was not provided by Discord")

        return (
            BulkDeletePayload(
                state=self.bot.state,
                data=data,
                guild=_guild
            ),
        )

    def message_reaction_add(self, data: dict) -> tuple[Reaction]:
        return (
            Reaction(
                state=self.bot.state,
                data=data
            ),
        )

    def message_reaction_remove(self, data: dict) -> tuple[Reaction]:
        return (
            Reaction(
                state=self.bot.state,
                data=data
            ),
        )

    def message_reaction_remove_all(self, data: dict) -> tuple[PartialMessage]:
        return (
            PartialMessage(
                state=self.bot.state,
                id=int(data["message_id"]),
                channel_id=int(data["channel_id"]),
                guild_id=utils.get_int(data, "guild_id")
            ),
        )

    def message_reaction_remove_emoji(self, data: dict) -> tuple[PartialMessage, Emoji]:
        _message = PartialMessage(
            state=self.bot.state,
            id=int(data["message_id"]),
            channel_id=int(data["channel_id"]),
            guild_id=utils.get_int(data, "guild_id")
        )

        return (
            _message,
            Emoji(state=self.bot.state, data=data["emoji"],)
        )

    def guild_role_create(self, data: dict) -> tuple[Role]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        _role = Role(
            state=self.bot.state,
            guild=_guild,
            data=data["role"]
        )

        self.bot.cache.add_role(_role)
        return (_role,)

    def guild_role_update(self, data: dict) -> tuple[Role]:
        _guild = self._get_guild_or_partial(int(data["guild_id"]))

        _role = Role(
            state=self.bot.state,
            guild=_guild,
            data=data["role"]
        )

        self.bot.cache.add_role(_role)
        return (_role,)

    def guild_role_delete(self, data: dict) -> tuple[PartialRole]:
        _role = self.bot.get_partial_role(
            role_id=int(data["role_id"]),
            guild_id=int(data["guild_id"])
        )

        self.bot.cache.remove_role(_role)
        return (_role,)

    def invite_create(self, data: dict) -> tuple[Invite]:
        return (Invite(state=self.bot.state, data=data),)

    def invite_delete(self, data: dict) -> tuple[PartialInvite]:
        return (
            self.bot.get_partial_invite(
                data["code"],
                channel_id=int(data["channel_id"]),
                guild_id=utils.get_int(data, "guild_id")
            ),
        )

    """
    This is just a placeholder for now.
    I am unsure if I ever will handle voice communication with discord.http/gateway
    Let this be a reminder for myself in later time

    - AlexFlipnote, 9. October 2024

    def voice_channel_effect_send(self, data: dict) -> tuple[None]:
        return (None,)
    """

    def voice_state_update(self, data: dict) -> tuple[VoiceState]:
        vs = VoiceState(state=self.bot.state, data=data)

        self.bot.cache.update_voice_state(vs)
        return (vs,)

    def typing_start(self, data: dict) -> tuple[TypingStartEvent]:
        guild_id: int | None = utils.get_int(data, "guild_id")
        channel_id: int = int(data["channel_id"])
        user_id: int = int(data["user_id"])
        timestamp: datetime = utils.parse_time(data["timestamp"])

        return (
            TypingStartEvent(
                guild=self._get_guild_or_partial(guild_id),
                channel=self._get_channel_or_partial(channel_id, guild_id),
                user=self._get_user_or_partial(user_id, guild_id),
                timestamp=timestamp
            ),
        )

    def stage_instance_create(self, data: "channels.StageInstance") -> tuple[StageInstance]:
        guild = self.bot.cache.get_guild(int(data["guild_id"]))
        stage_instance = StageInstance(
            state=self.bot.state,
            data=data,
            guild=guild
        )

        if guild and (channel := guild.get_channel(int(data["channel_id"]))):
            channel._stage_instance = stage_instance  # type: ignore # should be fine?

        return (stage_instance,)

    def stage_instance_update(self, data: "channels.StageInstance") -> tuple[StageInstance]:
        guild = self.bot.cache.get_guild(int(data["guild_id"]))

        # try updating the existing stage instance from cache if it exists
        if guild and (channel := guild.get_channel(int(data["channel_id"]))):
            channel._stage_instance._from_data(data)  # type: ignore # should be fine?
            return (channel._stage_instance,)  # type: ignore # should be fine?
        else:
            return (
                StageInstance(
                    state=self.bot.state,
                    data=data,
                    guild=guild
                ),
            )

    def stage_instance_delete(self, data: "channels.StageInstance") -> tuple[StageInstance]:
        guild = self.bot.cache.get_guild(int(data["guild_id"]))
        stage_instance = StageInstance(
            state=self.bot.state,
            data=data,
            guild=guild
        )

        if guild and (channel := guild.get_channel(int(data["channel_id"]))):
            channel._stage_instance = None  # type: ignore # should be fine?

        return (stage_instance,)

    def integration_create(self, data: dict) -> tuple[Integration]:
        _guild = self._get_guild_or_partial(int(data.pop("guild_id")))
        if _guild is None:
            raise ValueError("guild_id somehow was not provided by Discord")

        return (
            Integration(
                state=self.bot.state,
                data=data,
                guild=_guild
            ),
        )

    def integration_update(self, data: dict) -> tuple[Integration]:
        return self.integration_create(data)

    def integration_delete(self, data: dict) -> tuple[PartialIntegration]:
        guild_id = utils.get_int(data, "guild_id")
        if guild_id is None:
            raise ValueError("guild_id somehow was not provided by Discord")

        return (
            PartialIntegration(
                state=self.bot.state,
                id=int(data["id"]),
                guild_id=guild_id,
                application_id=utils.get_int(data, "application_id")
            ),
        )

    def webhooks_update(self, data: dict) -> tuple["PartialChannel"]:
        return (
            self._get_channel_or_partial(
                int(data["channel_id"]),
                int(data["guild_id"])
            ),
        )

    def presence_update(self, data: dict) -> tuple[Presence]:
        p = Presence(
            state=self.bot.state,
            user=self._get_user_or_partial(
                int(data["user"]["id"]),
                int(data["guild_id"])
            ),
            guild=self._get_guild_or_partial(int(data["guild_id"])),
            data=data
        )

        self.bot.cache.update_presence(p)

        return (p,)

    def guild_integrations_update(self, data: dict) -> tuple["PartialGuild | Guild"]:
        return (
            # guild_id is always provided
            self._get_guild_or_partial(
                int(data["guild_id"])
            ),
        )

    def guild_scheduled_event_create(self, data: dict) -> tuple[ScheduledEvent]:
        return (
            ScheduledEvent(
                state=self.bot.state,
                data=data
            ),
        )

    def guild_scheduled_event_update(self, data: dict) -> tuple[ScheduledEvent]:
        return (
            ScheduledEvent(
                state=self.bot.state,
                data=data
            ),
        )

    def guild_scheduled_event_delete(self, data: dict) -> tuple[ScheduledEvent]:
        return (
            ScheduledEvent(
                state=self.bot.state,
                data=data
            ),
        )

    def guild_scheduled_event_user_add(self, data: dict) -> tuple[
        PartialScheduledEvent,
        Member | PartialMember
    ]:
        _user = self._get_user_or_partial(
            int(data["user_id"]),
            int(data["guild_id"])
        )

        return (
            PartialScheduledEvent(
                state=self.bot.state,
                id=int(data["guild_scheduled_event_id"]),
                guild_id=int(data["guild_id"])
            ),
            _user
        )

    def guild_scheduled_event_user_remove(self, data: dict) -> tuple[
        PartialScheduledEvent,
        Member | PartialMember
    ]:
        _user = self._get_user_or_partial(
            int(data["user_id"]),
            int(data["guild_id"])
        )

        return (
            PartialScheduledEvent(
                state=self.bot.state,
                id=int(data["guild_scheduled_event_id"]),
                guild_id=int(data["guild_id"])
            ),
            _user
        )

    def auto_moderation_rule_create(self, data: dict) -> tuple[AutoModRule]:
        return (
            AutoModRule(
                state=self.bot.state,
                data=data
            ),
        )

    def auto_moderation_rule_update(self, data: dict) -> tuple[AutoModRule]:
        return (
            AutoModRule(
                state=self.bot.state,
                data=data
            ),
        )

    def auto_moderation_rule_delete(self, data: dict) -> tuple[AutoModRule]:
        return (
            AutoModRule(
                state=self.bot.state,
                data=data
            ),
        )

    def auto_moderation_action_execution(self, data: dict) -> tuple[AutomodExecution]:
        _channel = None

        _guild = self._get_guild_or_partial(
            int(data["guild_id"])
        )

        _user = self._get_user_or_partial(
            int(data["user_id"]),
            int(data["guild_id"])
        )

        if data.get("channel_id", None) is not None:
            _channel = self._get_channel_or_partial(
                int(data["channel_id"]),
                int(data["guild_id"])
            )
        return (
            AutomodExecution(
                state=self.bot.state,
                guild=_guild,
                channel=_channel,
                user=_user,
                data=data
            ),
        )

    def _message_poll_vote(self, data: dict, type: PollVoteActionType) -> PollVoteEvent:
        _guild = None
        _user = PartialUser(
            state=self.bot.state,
            id=int(data["user_id"])
        )

        if data.get("guild_id", None) is not None:
            _guild = self._get_guild_or_partial(
                int(data["guild_id"])
            )

            _user = self._get_user_or_partial(
                int(data["user_id"]),
                int(data["guild_id"])
            )

        _channel = self._get_channel_or_partial(
            int(data["channel_id"]),
            utils.get_int(data, "guild_id")
        )

        return PollVoteEvent(
            state=self.bot.state,
            user=_user,
            channel=_channel,
            guild=_guild,
            type=type,
            data=data
        )

    def message_poll_vote_add(self, data: dict) -> tuple[PollVoteEvent]:
        return (
            self._message_poll_vote(
                data=data,
                type=PollVoteActionType.add,
            ),
        )

    def message_poll_vote_remove(self, data: dict) -> tuple[PollVoteEvent]:
        return (
            self._message_poll_vote(
                data=data,
                type=PollVoteActionType.remove,
            ),
        )
