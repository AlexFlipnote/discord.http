from datetime import datetime, timedelta
from typing import Union, TYPE_CHECKING, Optional

from . import utils
from .asset import Asset
from .embeds import Embed
from .file import File
from .flags import Permissions, PublicFlags, GuildMemberFlags, MessageFlags
from .guild import Guild, PartialGuild
from .mentions import AllowedMentions
from .object import PartialBase, Snowflake
from .response import ResponseType
from .role import PartialRole, Role
from .user import User, PartialUser
from .view import View


MISSING = utils.MISSING

if TYPE_CHECKING:
    from .gateway.object import Presence
    from .types.guilds import (
        ThreadMember as ThreadMemberPayload
    )
    from .http import DiscordAPI
    from .message import Message
    from .channel import DMChannel, PartialChannel, Thread

__all__ = (
    "PartialMember",
    "Member",
    "ThreadMember",
)


class PartialMember(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        guild_id: int,
    ):
        super().__init__(id=int(id))
        self._state = state

        self._user = PartialUser(state=state, id=self.id)

        self.guild_id: int = int(guild_id)
        self.presence: "Presence | None" = None

    def __repr__(self) -> str:
        return f"<PartialMember id={self.id} guild_id={self.guild_id}>"

    def _update_presence(self, obj: "Presence | None") -> None:
        self.presence = obj

    @property
    def guild(self) -> Guild | PartialGuild:
        """
        `PartialGuild | Guild`: The guild of the member
        If you are using gateway cache, it can return full object too
        """
        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def default_avatar(self) -> Asset:
        """ `Asset`: Alias for `User.default_avatar` """
        return self._user.default_avatar

    async def fetch(self) -> "Member":
        """ `Fetch`: Fetches the member from the API """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.guild_id}/members/{self.id}"
        )

        return Member(
            state=self._state,
            guild=self.guild,
            data=r.response
        )

    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        channel_id: Optional[int] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        type: Union[ResponseType, int] = 4,
        flags: Optional[MessageFlags] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        delete_after: Optional[float] = None
    ) -> "Message":
        """
        Send a message to the user

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        channel_id: `Optional[int]`
            Channel ID of the user, leave empty to create a DM
        embed: `Optional[Embed]`
            Embed of the message
        embeds: `Optional[list[Embed]]`
            Embeds of the message
        file: `Optional[File]`
            File of the message
        files: `Optional[Union[list[File], File]]`
            Files of the message
        view: `Optional[View]`
            Components to add to the message
        tts: `Optional[bool]`
            Whether the message should be sent as TTS
        type: `Optional[ResponseType]`
            Type of the message
        flags: `Optional[MessageFlags]`
            Flags of the message
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions of the message
        delete_after: `Optional[float]`
            How long to wait before deleting the message

        Returns
        -------
        `Message`
            The message sent
        """
        return await self._user.send(
            content,
            channel_id=channel_id,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            view=view,
            tts=tts,
            type=type,
            flags=flags,
            allowed_mentions=allowed_mentions,
            delete_after=delete_after
        )

    async def create_dm(self) -> "DMChannel":
        """ `DMChannel`: Create a DM channel with the user """
        return await self._user.create_dm()

    async def ban(
        self,
        *,
        reason: Optional[str] = None,
        delete_message_days: Optional[int] = 0,
        delete_message_seconds: Optional[int] = 0,
    ) -> None:
        """
        Ban the user

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for banning the user
        delete_message_days: `Optional[int]`
            How many days of messages to delete
        delete_message_seconds: `Optional[int]`
            How many seconds of messages to delete

        Raises
        ------
        `ValueError`
            - If delete_message_days and delete_message_seconds are both specified
            - If delete_message_days is not between 0 and 7
            - If delete_message_seconds is not between 0 and 604,800
        """
        await self.guild.ban(
            self.id,
            reason=reason,
            delete_message_days=delete_message_days,
            delete_message_seconds=delete_message_seconds
        )

    async def unban(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Unban the user

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for unbanning the user
        """
        await self.guild.unban(self.id, reason=reason)

    async def kick(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Kick the user

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for kicking the user
        """
        await self.guild.kick(self.id, reason=reason)

    async def edit(
        self,
        *,
        nick: Optional[str] = MISSING,
        roles: Union[list[Union[PartialRole, int]], None] = MISSING,
        mute: Optional[bool] = MISSING,
        deaf: Optional[bool] = MISSING,
        communication_disabled_until: Union[timedelta, datetime, int, None] = MISSING,
        channel_id: Optional[int] = MISSING,
        reason: Optional[str] = None
    ) -> "Member":
        """
        Edit the member

        Parameters
        ----------
        nick: `Optional[str]`
            The new nickname of the member
        roles: `Optional[list[Union[PartialRole, int]]]`
            Roles to make the member have
        mute: `Optional[bool]`
            Whether to mute the member
        deaf: `Optional[bool]`
            Whether to deafen the member
        communication_disabled_until: `Optional[Union[timedelta, datetime, int]]`
            How long to disable communication for (timeout)
        channel_id: `Optional[int]`
            The channel ID to move the member to
        reason: `Optional[str]`
            The reason for editing the member

        Returns
        -------
        `Member`
            The edited member

        Raises
        ------
        `TypeError`
            - If communication_disabled_until is not timedelta, datetime, or int
        """
        payload = {}

        if nick is not MISSING:
            payload["nick"] = nick
        if isinstance(roles, list) and roles is not MISSING:
            payload["roles"] = [str(int(role)) for role in roles]
        if mute is not MISSING:
            payload["mute"] = mute
        if deaf is not MISSING:
            payload["deaf"] = deaf
        if channel_id is not MISSING:
            payload["channel_id"] = channel_id
        if communication_disabled_until is not MISSING:
            if communication_disabled_until is None:
                payload["communication_disabled_until"] = None
            else:
                _parse_ts = utils.add_to_datetime(
                    communication_disabled_until
                )
                payload["communication_disabled_until"] = _parse_ts.isoformat()

        r = await self._state.query(
            "PATCH",
            f"/guilds/{self.guild_id}/members/{self.id}",
            json=payload,
            reason=reason
        )

        return Member(
            state=self._state,
            guild=self.guild,
            data=r.response
        )

    async def add_roles(
        self,
        *roles: Union[PartialRole, int],
        reason: Optional[str] = None
    ) -> None:
        """
        Add roles to someone

        Parameters
        ----------
        *roles: `Union[PartialRole, int]`
            Roles to add to the member
        reason: `Optional[str]`
            The reason for adding the roles

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for adding the roles
        """
        for role in roles:
            if isinstance(role, PartialRole):
                role = role.id

            await self._state.query(
                "PUT",
                f"/guilds/{self.guild_id}/members/{self.id}/roles/{int(role)}",
                reason=reason
            )

    async def remove_roles(
        self,
        *roles: Union[PartialRole, int],
        reason: Optional[str] = None
    ) -> None:
        """
        Remove roles from someone

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for removing the roles
        """
        for role in roles:
            if isinstance(role, PartialRole):
                role = role.id

            await self._state.query(
                "DELETE",
                f"/guilds/{self.guild_id}/members/{self.id}/roles/{int(role)}",
                reason=reason
            )

    @property
    def mention(self) -> str:
        """ `str`: The mention of the member """
        return f"<@!{self.id}>"


class Member(PartialMember):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: Guild | PartialGuild,
        data: dict
    ):
        super().__init__(
            state=state,
            id=int(data["user"]["id"]),
            guild_id=guild.id,
        )

        self._user = User(state=state, data=data["user"])

        self.avatar: Optional[Asset] = None

        self.flags: GuildMemberFlags = GuildMemberFlags(data["flags"])
        self.pending: bool = data.get("pending", False)
        self._raw_permissions: Optional[int] = utils.get_int(data, "permissions")
        self.nick: Optional[str] = data.get("nick", None)
        self.joined_at: datetime = utils.parse_time(data["joined_at"])
        self.communication_disabled_until: datetime | None = None
        self.premium_since: datetime | None = None
        self._roles: list[PartialRole] = [
            PartialRole(state=state, id=int(r), guild_id=self.guild.id)
            for r in data["roles"]
        ]

        self._from_data(data)

    def __repr__(self) -> str:
        return (
            f"<Member id={self.id} name='{self.name}' "
            f"global_name='{self._user.global_name}'>"
        )

    def __str__(self) -> str:
        return str(self._user)

    def _from_data(self, data: dict) -> None:
        has_avatar = data.get("avatar", None)
        if has_avatar:
            self.avatar = Asset._from_guild_avatar(
                self._state, self.guild.id, self.id, has_avatar
            )

        if data.get("communication_disabled_until", None):
            self.communication_disabled_until = utils.parse_time(
                data["communication_disabled_until"]
            )

        if data.get("premium_since", None):
            self.premium_since = utils.parse_time(
                data["premium_since"]
            )

    @property
    def roles(self) -> list[Role | PartialRole]:
        """ `list[Role | PartialRole]`: Returns the roles of the member """
        if self.guild.roles:
            # If there is a guild cache, we could potentially return full Role object
            g_roles = [r.id for r in self._roles]
            return [
                g for g in self.guild.roles
                if g.id in g_roles
            ]

        return self._roles

    def get_role(
        self,
        role: Union[Snowflake, int]
    ) -> Optional[PartialRole]:
        """
        Get a role from the member

        Parameters
        ----------
        role: `Union[Snowflake, int]`
            The role to get. Can either be a role object or the Role ID

        Returns
        -------
        `Optional[PartialRole]`
            The role if found, else None
        """
        return next((
            r for r in self.roles
            if r.id == int(role)
        ), None)

    def is_timed_out(self) -> bool:
        """ `bool`: Returns whether the member is timed out or not """
        if self.communication_disabled_until is None:
            return False
        return utils.utcnow() < self.communication_disabled_until

    @property
    def guild_permissions(self) -> Permissions:
        """
        `Permissions`: Returns the guild permissions of the member.
        This is only available if you are using gateway with guild cache.
        """
        if getattr(self.guild, "owner_id", None) == self.id:
            return Permissions.all()

        base = Permissions.none()

        for r in self.roles:
            g_role = self.guild.get_role(r.id)
            if isinstance(g_role, Role):
                base |= g_role.permissions

        if Permissions.administrator in base:
            return Permissions.all()

        if self.is_timed_out():
            _timeout_perm = (
                Permissions.view_channel |
                Permissions.read_message_history
            )

            if Permissions.view_channel not in base:
                _timeout_perm &= ~Permissions.view_channel
            if Permissions.read_message_history not in base:
                _timeout_perm &= ~Permissions.read_message_history

            base = _timeout_perm

        return base

    @property
    def resolved_permissions(self) -> Permissions:
        """
        `Permissions` Returns permissions from an interaction.

        Will always be `Permissions.none()` if used in `Member.fetch()`
        """
        if self._raw_permissions is None:
            return Permissions(0)
        return Permissions(self._raw_permissions)

    def has_permissions(self, *args: str) -> bool:
        """
        Check if a member has a permission

        Will be False if used in `Member.fetch()` every time

        Parameters
        ----------
        *args: `str`
            Permissions to check

        Returns
        -------
        `bool`
            Whether the member has the permission(s)
        """
        if (
            Permissions.from_names("administrator") in
            self.resolved_permissions
        ):
            return True

        return (
            Permissions.from_names(*args) in
            self.resolved_permissions
        )

    @property
    def name(self) -> str:
        """ `str`: Returns the username of the member """
        return self._user.name

    @property
    def bot(self) -> bool:
        """ `bool`: Returns whether the member is a bot """
        return self._user.bot

    @property
    def system(self) -> bool:
        """ `bool`: Returns whether the member is a system user """
        return self._user.system

    @property
    def discriminator(self) -> Optional[str]:
        """
        Gives the discriminator of the member if available

        Returns
        -------
        `Optional[str]`
            Discriminator of a user who has yet to convert or a bot account.
            If the user has converted to the new username, this will return None
        """
        return self._user.discriminator

    @property
    def public_flags(self) -> PublicFlags:
        """ `int`: Returns the public flags of the member """
        return self._user.public_flags or PublicFlags(0)

    @property
    def banner(self) -> Optional[Asset]:
        """ `Optional[Asset]`: Returns the banner of the member if available """
        return self._user.banner

    @property
    def avatar_decoration(self) -> Optional[Asset]:
        """ `Optional[Asset]`: Returns the avatar decoration of the member """
        return self._user.avatar_decoration

    @property
    def global_name(self) -> Optional[str]:
        """
        `Optional[str]`: Gives the global display name of a member if available
        """
        return self._user.global_name

    @property
    def global_avatar(self) -> Optional[Asset]:
        """ `Optional[Asset]`: Shortcut for `User.avatar` """
        return self._user.avatar

    @property
    def global_banner(self) -> Optional[Asset]:
        """ `Optional[Asset]`: Shortcut for `User.banner` """
        return self._user.banner

    @property
    def display_name(self) -> str:
        """ `str`: Returns the display name of the member """
        return self.nick or self.global_name or self.name

    @property
    def display_avatar(self) -> Optional[Asset]:
        """ `Optional[Asset]`: Returns the display avatar of the member """
        return (
            self.avatar or
            self.global_avatar or
            self.default_avatar
        )

    @property
    def top_role(self) -> PartialRole | Role | None:
        """
        `Optional[PartialRole | Role]`: Returns the top role of the member.
        Only usable if you are using gateway and caching
        """
        if not isinstance(self.guild, Guild):
            return None
        return self.guild.get_member_top_role(self)


class PartialThreadMember(PartialMember):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: "ThreadMemberPayload",
        guild_id: int,
    ) -> None:
        super().__init__(
            state=state,
            id=int(data["user_id"]),
            guild_id=guild_id,
        )
        self.thread_id: int = int(data["id"])
        self.join_timestamp: datetime = utils.parse_time(data["join_timestamp"])
        self.flags: int = data["flags"]

    @property
    def thread(self) -> "PartialChannel | Thread":
        """ `PartialChannel | Thread"`: The thread the member is in """
        return (
            self.guild.get_channel(self.thread_id) or
            self.guild.get_partial_channel(self.thread_id)
        )


class ThreadMember(Member):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: "PartialGuild",
        data: dict
    ) -> None:
        super().__init__(
            state=state,
            guild=guild,
            data=data["member"]
        )

        self.thread_id: int = int(data["id"])
        self.join_timestamp: datetime = utils.parse_time(data["join_timestamp"])
        self.flags: int = data["flags"]

    @property
    def thread(self) -> "PartialChannel | Thread":
        """ `PartialChannel | Thread"`: The thread the member is in """
        return (
            self.guild.get_channel(self.thread_id) or
            self.guild.get_partial_channel(self.thread_id)
        )
