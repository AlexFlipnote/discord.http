import logging

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from . import utils
from .asset import Asset
from .embeds import Embed
from .file import File
from .flags import Permissions, UserFlags, GuildMemberFlags, MessageFlags
from .guild import Guild, PartialGuild
from .mentions import AllowedMentions
from .object import PartialBase, Snowflake
from .response import ResponseType
from .role import PartialRole, Role
from .user import User, PartialUser, PrimaryGuild, AvatarDecoration, Nameplate
from .view import View

_log = logging.getLogger(__name__)
MISSING = utils.MISSING

if TYPE_CHECKING:
    from .gateway.object import Presence
    from .http import DiscordAPI
    from .message import Message
    from .channel import DMChannel, PartialChannel, Thread

__all__ = (
    "Member",
    "PartialMember",
    "ThreadMember",
)


class PartialMember(PartialBase):
    """
    Represents a partial member object.

    Attributes
    ----------
    guild_id: int
        The ID of the guild the member belongs to.
    presence: Presence | None
        The presence of the member, if available.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
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
        The guild of the member.

        If you are using gateway cache, it can return full object too
        """
        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def default_avatar(self) -> Asset:
        """ Alias for `User.default_avatar`. """
        return self._user.default_avatar

    async def fetch(self) -> "Member":
        """ Fetches the member from the API. """
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
        content: str | None = MISSING,
        *,
        channel_id: int | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        view: View | None = MISSING,
        tts: bool | None = False,
        type: ResponseType | int = 4,  # noqa: A002
        flags: MessageFlags | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        delete_after: float | None = None
    ) -> "Message":
        """
        Send a message to the user.

        Parameters
        ----------
        content:
            Content of the message
        channel_id:
            Channel ID of the user, leave empty to create a DM
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        file:
            File of the message
        files:
            Files of the message
        view:
            Components to add to the message
        tts:
            Whether the message should be sent as TTS
        type:
            Type of the message
        flags:
            Flags of the message
        allowed_mentions:
            Allowed mentions of the message
        delete_after:
            How long to wait before deleting the message

        Returns
        -------
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
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            ),
            delete_after=delete_after
        )

    async def create_dm(self) -> "DMChannel":
        """ Create a DM channel with the user. """
        return await self._user.create_dm()

    async def ban(
        self,
        *,
        reason: str | None = None,
        delete_message_days: int | None = 0,
        delete_message_seconds: int | None = 0,
    ) -> None:
        """
        Ban the user.

        Parameters
        ----------
        reason:
            The reason for banning the user
        delete_message_days:
            How many days of messages to delete
        delete_message_seconds:
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
        reason: str | None = None
    ) -> None:
        """
        Unban the user.

        Parameters
        ----------
        reason:
            The reason for unbanning the user
        """
        await self.guild.unban(self.id, reason=reason)

    async def kick(
        self,
        *,
        reason: str | None = None
    ) -> None:
        """
        Kick the user.

        Parameters
        ----------
        reason:
            The reason for kicking the user
        """
        await self.guild.kick(self.id, reason=reason)

    async def edit(
        self,
        *,
        nick: str | None = MISSING,
        roles: list[PartialRole | int] | None = MISSING,
        mute: bool | None = MISSING,
        deaf: bool | None = MISSING,
        communication_disabled_until: timedelta | datetime | int | None = MISSING,
        channel_id: int | None = MISSING,
        banner: File | bytes | None = MISSING,
        avatar: File | bytes | None = MISSING,
        bio: str | None = MISSING,
        reason: str | None = None
    ) -> "Member":
        """
        Edit the member.

        Parameters
        ----------
        nick:
            The new nickname of the member
        roles:
            Roles to make the member have
        mute:
            Whether to mute the member
        deaf:
            Whether to deafen the member
        communication_disabled_until:
            How long to disable communication for (timeout)
        channel_id:
            The channel ID to move the member to
        reason:
            The reason for editing the member
        banner:
            The new guild banner for the bot (Application only).
        avatar:
            The new avatar for the bot (Application only).
        bio:
            The new bio for the bot (Application only).

        Returns
        -------
            The edited member

        Raises
        ------
        `TypeError`
            - If communication_disabled_until is not timedelta, datetime, or int
        """
        payload = {}
        self_payload = {}
        me = self._state.bot.user.id == self.id

        if nick is not MISSING:
            if me:
                self_payload["nick"] = nick
            else:
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
                parse_ts = utils.add_to_datetime(
                    communication_disabled_until
                )
                payload["communication_disabled_until"] = parse_ts.isoformat()

        if banner is not MISSING:
            self_payload["banner"] = (
                utils.bytes_to_base64(banner)
                if banner else None
            )
        if avatar is not MISSING:
            self_payload["avatar"] = (
                utils.bytes_to_base64(avatar)
                if avatar else None
            )
        if bio is not MISSING:
            self_payload["bio"] = bio

        if payload:
            if self_payload:
                self_parms_used = ", ".join(self_payload.keys())
                _log.warning(
                    f"Self parameters ({self_parms_used}) cannot be used combined "
                    "with guild parameters, skipping self ones"
                )
            r = await self._state.query(
                "PATCH",
                f"/guilds/{self.guild_id}/members/{self.id}",
                json=payload,
                reason=reason
            )
        elif self_payload:
            r = await self._state.query(
                "PATCH",
                f"/guilds/{self.guild_id}/members/@me",
                json=self_payload,
                reason=reason
            )
        else:
            raise ValueError("No parameters to edit were provided.")

        return Member(
            state=self._state,
            guild=self.guild,
            data=r.response
        )

    async def add_roles(
        self,
        *roles: PartialRole | int,
        reason: str | None = None
    ) -> None:
        """
        Add roles to someone.

        Parameters
        ----------
        *roles:
            Roles to add to the member
        reason:
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
        *roles: PartialRole | int,
        reason: str | None = None
    ) -> None:
        """
        Remove roles from someone.

        Parameters
        ----------
        *roles:
            Roles to remove from the member
        reason:
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
        """ The mention of the member. """
        return f"<@!{self.id}>"


class Member(PartialMember):
    """
    Represents a member of a guild.

    Attributes
    ----------
    avatar: Asset | None
        The avatar of the member, if available.
    banner: Asset | None
        The banner of the member, if available.
    flags: GuildMemberFlags
        The flags of the member.
    pending: bool
        Whether the member is pending or not.
    nick: str | None
        The nickname of the member, if available.
    joined_at: datetime
        The time the member joined the guild.
    communication_disabled_until: datetime | None
        The time until the member is communication disabled (timeout).
    premium_since: datetime | None
        The time the member started boosting the guild, if available.
    avatar_decoration: AvatarDecoration | None
        The avatar decoration of the member, if available.
    nameplate: Nameplate | None
        The nameplate of the member, if available.
    primary_guild: PrimaryGuild | None
        The primary guild of the member, if available.
    """
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

        self.avatar: Asset | None = None
        self.banner: Asset | None = None

        self.flags: GuildMemberFlags = GuildMemberFlags(data["flags"])
        self.pending: bool = data.get("pending", False)
        self._raw_permissions: int | None = utils.get_int(data, "permissions")
        self.nick: str | None = data.get("nick")
        self.joined_at: datetime = utils.parse_time(data["joined_at"])
        self.communication_disabled_until: datetime | None = None
        self.premium_since: datetime | None = None
        self._roles: list[PartialRole] = [
            PartialRole(state=state, id=int(r), guild_id=self.guild.id)
            for r in data["roles"]
        ]

        self.avatar_decoration: AvatarDecoration | None = None
        self.nameplate: Nameplate | None = self._user.nameplate
        self.primary_guild: PrimaryGuild | None = self._user.primary_guild

        self._from_data(data)

    def __repr__(self) -> str:
        return (
            f"<Member id={self.id} name='{self.name}' "
            f"global_name='{self._user.global_name}'>"
        )

    def __str__(self) -> str:
        return str(self._user)

    def _from_data(self, data: dict) -> None:
        if data.get("avatar"):
            self.avatar = Asset._from_guild_avatar(
                self._state, self.guild.id, self.id, data["avatar"]
            )

        if data.get("banner"):
            self.banner = Asset._from_guild_banner(
                self._state, self.guild.id, self.id, data["banner"]
            )

        if data.get("avatar_decoration_data"):
            self.avatar_decoration = AvatarDecoration(
                self._state, data["avatar_decoration_data"]
            )

        if data.get("communication_disabled_until"):
            self.communication_disabled_until = utils.parse_time(
                data["communication_disabled_until"]
            )

        if data.get("premium_since"):
            self.premium_since = utils.parse_time(
                data["premium_since"]
            )

    @property
    def roles(self) -> list[Role | PartialRole]:
        """ Returns the roles of the member. """
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
        role: Snowflake | int
    ) -> PartialRole | None:
        """
        Get a role from the member.

        Parameters
        ----------
        role:
            The role to get. Can either be a role object or the Role ID

        Returns
        -------
            The role if found, else None
        """
        return next((
            r for r in self.roles
            if r.id == int(role)
        ), None)

    def is_timed_out(self) -> bool:
        """ Returns whether the member is timed out or not. """
        if self.communication_disabled_until is None:
            return False
        return utils.utcnow() < self.communication_disabled_until

    @property
    def guild_permissions(self) -> Permissions:
        """
        Returns the guild permissions of the member.

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
            timeout_perm = (
                Permissions.view_channel |
                Permissions.read_message_history
            )

            if Permissions.view_channel not in base:
                timeout_perm &= ~Permissions.view_channel
            if Permissions.read_message_history not in base:
                timeout_perm &= ~Permissions.read_message_history

            base = timeout_perm

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
        Check if a member has a permission.

        Will be False if used in `Member.fetch()` every time

        Parameters
        ----------
        *args:
            Permissions to check

        Returns
        -------
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
        """ Returns the username of the member. """
        return self._user.name

    @property
    def bot(self) -> bool:
        """ Returns whether the member is a bot. """
        return self._user.bot

    @property
    def system(self) -> bool:
        """ Returns whether the member is a system user. """
        return self._user.system

    @property
    def discriminator(self) -> str | None:
        """
        Gives the discriminator of the member if available.

        Returns
        -------
            Discriminator of a user who has yet to convert or a bot account.
            If the user has converted to the new username, this will return None
        """
        return self._user.discriminator

    @property
    def public_flags(self) -> UserFlags:
        """ Returns the public flags of the member. """
        return self._user.public_flags or UserFlags(0)

    @property
    def display_avatar_decoration(self) -> AvatarDecoration | None:
        """ Returns the display avatar decoration of the member. """
        return self.avatar_decoration or self._user.avatar_decoration

    @property
    def global_avatar_decoration(self) -> AvatarDecoration | None:
        """ Shortcut for `User.avatar_decoration`. """
        return self._user.avatar_decoration

    @property
    def global_name(self) -> str | None:
        """ Gives the global display name of a member if available. """
        return self._user.global_name

    @property
    def global_avatar(self) -> Asset | None:
        """ Shortcut for `User.avatar`. """
        return self._user.avatar

    @property
    def global_banner(self) -> Asset | None:
        """ Shortcut for `User.banner`. """
        return self._user.banner

    @property
    def display_name(self) -> str:
        """ Returns the display name of the member. """
        return self.nick or self.global_name or self.name

    @property
    def display_banner(self) -> Asset | None:
        """ Returns the display banner of the member. """
        return (
            self.banner or
            self.global_banner
        )

    @property
    def display_avatar(self) -> Asset:
        """ Returns the display avatar of the member. """
        return (
            self.avatar or
            self.global_avatar or
            self.default_avatar
        )

    @property
    def top_role(self) -> PartialRole | Role | None:
        """
        Returns the top role of the member.

        Only usable if you are using gateway and caching
        """
        if not isinstance(self.guild, Guild):
            return None
        return self.guild.get_member_top_role(self)


class PartialThreadMember(PartialMember):
    """
    Represents a partial thread member object.

    Attributes
    ----------
    thread_id: int
        The ID of the thread the member is in.
    join_timestamp: datetime
        The time the member joined the thread.
    flags: int
        The flags of the member in the thread.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
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
        """ The thread the member is in. """
        return (
            self.guild.get_channel(self.thread_id) or
            self.guild.get_partial_channel(self.thread_id)
        )


class ThreadMember(Member):
    """
    Represents a member of a thread.

    Attributes
    ----------
    thread_id: int
        The ID of the thread the member is in.
    join_timestamp: datetime
        The time the member joined the thread.
    flags: int
        The flags of the member in the thread.
    """
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
        """ The thread the member is in. """
        return (
            self.guild.get_channel(self.thread_id) or
            self.guild.get_partial_channel(self.thread_id)
        )
