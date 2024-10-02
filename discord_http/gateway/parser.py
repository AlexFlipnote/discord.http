from datetime import datetime
from typing import TYPE_CHECKING

from .object import (
    ChannelPinsUpdate, TypingStartEvent,
    Reaction, BulkDeletePayload
)

from .. import utils
from ..audit import AuditLogEntry
from ..channel import BaseChannel, PartialChannel
from ..emoji import Emoji
from ..enums import ChannelType
from ..guild import Guild, PartialGuild
from ..invite import Invite, PartialInvite
from ..member import Member, PartialMember
from ..message import Message, PartialMessage
from ..role import Role, PartialRole
from ..sticker import Sticker
from ..user import User, PartialUser
from ..voice import VoiceState

if TYPE_CHECKING:
    from ..client import Client

__all__ = (
    "Parser",
)


class Parser:
    def __init__(self, bot: "Client"):
        self.bot = bot

    def _get_guild_or_partial(self, guild_id: int | None) -> "PartialGuild | Guild | None":
        if not guild_id:
            return None

        return (
            self.bot.cache.get_guild(guild_id) or
            PartialGuild(state=self.bot.state, id=guild_id)
        )

    def _get_channel_or_partial(self, channel_id: int, guild_id: int | None) -> "BaseChannel | PartialChannel":
        if not guild_id:
            return PartialChannel(state=self.bot.state, id=channel_id)

        guild = self._get_guild_or_partial(guild_id)
        return guild.get_channel(channel_id) or PartialChannel(state=self.bot.state, id=channel_id, guild_id=guild_id)

    def _get_user_or_partial(self, user_id: int, guild_id: int | None) -> "PartialUser | User | Member | PartialMember":
        state = self.bot.state
        if not guild_id:
            return PartialUser(state=state, id=user_id)

        guild = self._get_guild_or_partial(guild_id)
        return guild.get_member(user_id) or PartialMember(state=state, id=user_id, guild_id=guild_id)

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

    def guild_delete(self, data: dict) -> tuple[PartialGuild]:
        return (self.bot.get_partial_guild(data["id"]),)

    def guild_member_add(self, data: dict) -> tuple[PartialGuild, Member]:
        _guild = self.bot.get_partial_guild(int(data["guild_id"]))
        return (
            _guild,
            Member(state=self.bot.state, guild=_guild, data=data)
        )

    def guild_member_update(self, data: dict) -> tuple[PartialGuild, Member]:
        _guild = self.bot.get_partial_guild(int(data["guild_id"]))
        return (
            _guild,
            Member(state=self.bot.state, guild=_guild, data=data)
        )

    def guild_member_remove(self, data: dict) -> tuple[PartialGuild, User]:
        return (
            self.bot.get_partial_guild(int(data["guild_id"])),
            User(
                state=self.bot.state,
                data=data["user"]
            )
        )

    def guild_ban_add(self, data: dict) -> tuple[PartialGuild, User]:
        return (
            self.bot.get_partial_guild(int(data["guild_id"])),
            User(
                state=self.bot.state,
                data=data["user"]
            )
        )

    def guild_ban_remove(self, data: dict) -> tuple[PartialGuild, User]:
        return (
            self.bot.get_partial_guild(int(data["guild_id"])),
            User(
                state=self.bot.state,
                data=data["user"]
            )
        )

    def guild_emojis_update(self, data: dict) -> tuple[PartialGuild, list[Emoji]]:
        _guild = self.bot.get_partial_guild(int(data["guild_id"]))
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

    def guild_stickers_update(self, data: dict) -> tuple[PartialGuild, list[Sticker]]:
        _guild = self.bot.get_partial_guild(int(data["guild_id"]))
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

    def guild_audit_log_entry_create(self, data: dict) -> tuple[AuditLogEntry]:
        _guild = self.bot.get_partial_guild(int(data["guild_id"]))
        return (
            AuditLogEntry(
                state=self.bot.state,
                data=data,
                guild=_guild
            ),
        )

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

    def channel_delete(self, data: dict) -> tuple[PartialChannel]:
        channel = self._partial_channel(data)
        self.bot.cache.remove_channel(channel)
        return (channel,)

    def channel_pins_update(self, data: dict) -> tuple[ChannelPinsUpdate]:
        guild_id: int | None = data.get("guild_id", None)
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

    def message_create(self, data: dict) -> tuple[Message]:
        return (self._message(data),)

    def message_update(self, data: dict) -> tuple[Message]:
        return (self._message(data),)

    def message_delete(self, data: dict) -> tuple[PartialMessage]:
        return (
            self.bot.get_partial_message(
                message_id=int(data["id"]),
                channel_id=int(data["channel_id"]),
            ),
        )

    def message_delete_bulk(self, data: dict) -> tuple[BulkDeletePayload]:
        _guild = self._get_guild_or_partial(data.get("guild_id", None))

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

    def guild_role_create(self, data: dict) -> tuple[Role]:
        _guild = self.bot.get_partial_guild(int(data["guild_id"]))
        _role = Role(
            state=self.bot.state,
            guild=_guild,
            data=data["role"]
        )

        self.bot.cache.add_role(_role)
        return (_role,)

    def guild_role_update(self, data: dict) -> tuple[Role]:
        _role = Role(
            state=self.bot.state,
            guild=self.bot.get_partial_guild(int(data["guild_id"])),
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
                guild_id=(
                    int(data["guild_id"])
                    if data.get("guild_id", None) else None
                )
            ),
        )

    def voice_state_update(self, data: dict) -> tuple[VoiceState]:
        vs = VoiceState(state=self.bot.state, data=data)

        self.bot.cache.update_voice_state(vs)
        return (vs,)

    def typing_start(self, data: dict) -> tuple[TypingStartEvent]:
        guild_id: int | None = data.get("guild_id", None)
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
