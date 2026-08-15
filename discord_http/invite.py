from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple

from . import utils
from .channel import PartialChannel
from .enums import InviteType, InviteTargetType, InviteTargetUsersJobStatusType
from .flags import GuildInviteFlags
from .guild import PartialGuild, Guild
from .object import Snowflake
from .role import Role
from .user import User, PartialUser

if TYPE_CHECKING:
    from .http import DiscordAPI

__all__ = (
    "Invite",
    "InviteTargetUsersJobStatus",
    "PartialInvite",
)


class InviteTargetUsersJobStatus(NamedTuple):
    """ Represents the status of an invite's target users file processing job. """
    status: InviteTargetUsersJobStatusType
    total_users: int
    processed_users: int
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None


class PartialInvite:
    """ Represents a partial invite object. """

    __slots__ = (
        "_state",
        "channel_id",
        "code",
        "guild",
        "guild_id",
    )

    BASE: str = "https://discord.gg"

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        code: str,
        channel_id: int | None = None,
        guild_id: int | None = None
    ):
        self._state = state

        self.code = code
        """ The invite code. """

        self.channel_id: int | None = channel_id
        """ The ID of the channel the invite is in, if applicable. """

        self.guild_id: int | None = guild_id
        """ The ID of the guild the invite is in, if applicable. """

        self.guild: "Guild | PartialGuild | None" = self._get_guild
        """ The guild associated with the invite, if applicable. """

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        return f"<PartialInvite code='{self.code}'>"

    @property
    def _get_guild(self) -> Guild | PartialGuild | None:
        """ Used to create the guild object for `Invite.guild`. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "PartialChannel | None":
        """ The channel the invite is in. """
        if not self.channel_id:
            return None

        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    async def fetch(self) -> "Invite":
        """
        Fetches the invite details.

        Returns
        -------
            The invite object
        """
        r = await self._state.query(
            "GET",
            f"/invites/{self.code}"
        )

        return Invite(
            state=self._state,
            data=r.response
        )

    async def fetch_target_users(self) -> list[PartialUser]:
        """
        Fetch the list of users allowed to use this invite.

        Returns
        -------
            The users from the target users file
        """
        r = await self._state.query(
            "GET",
            f"/invites/{self.code}/target-users",
            res_method="text"
        )

        lines = [g.strip() for g in r.response.splitlines() if g.strip()]
        if lines and lines[0].lower() == "user_id":
            lines = lines[1:]

        return [PartialUser(state=self._state, id=int(g)) for g in lines]

    async def edit_target_users(self, user_ids: list[Snowflake | int]) -> None:
        """
        Update the list of users allowed to use this invite.

        Parameters
        ----------
        user_ids:
            The user IDs to allow to use this invite
        """
        multidata = utils.MultipartData()

        csv_content = "\n".join(str(int(g)) for g in user_ids)
        multidata.attach(
            "target_users_file",
            f"{csv_content}\n",
            filename="target_users_file.csv",
            content_type="text/csv"
        )

        await self._state.query(
            "PUT",
            f"/invites/{self.code}/target-users",
            headers={"Content-Type": multidata.content_type},
            data=multidata.finish(),
            res_method="text"
        )

    async def fetch_target_users_job_status(self) -> "InviteTargetUsersJobStatus":
        """
        Fetch the status of the target users file processing job.

        Returns
        -------
            The status of the target users file processing job
        """
        r = await self._state.query(
            "GET",
            f"/invites/{self.code}/target-users/job-status"
        )

        return InviteTargetUsersJobStatus(
            status=InviteTargetUsersJobStatusType(r.response["status"]),
            total_users=r.response["total_users"],
            processed_users=r.response["processed_users"],
            created_at=utils.parse_time(r.response["created_at"]),
            completed_at=(
                utils.parse_time(r.response["completed_at"])
                if r.response.get("completed_at") else None
            ),
            error_message=r.response.get("error_message"),
        )

    async def delete(
        self,
        *,
        reason: str | None = None
    ) -> "Invite":
        """
        Deletes the invite.

        Parameters
        ----------
        reason: `str`
            The reason for deleting the invite

        Returns
        -------
            The invite object
        """
        data = await self._state.query(
            "DELETE",
            f"/invites/{self.code}",
            reason=reason
        )

        return Invite(
            state=self._state,
            data=data.response
        )

    @property
    def url(self) -> str:
        """ The URL of the invite. """
        return f"{self.BASE}/{self.code}"


class Invite(PartialInvite):
    """ Represents an invite object. """

    __slots__ = (
        "_account",
        "_raw_type",
        "approximate_member_count",
        "approximate_presence_count",
        "created_at",
        "expires_at",
        "flags",
        "inviter",
        "max_uses",
        "roles",
        "target_type",
        "target_user",
        "temporary",
        "uses",
    )

    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, code=data["code"])

        self._raw_type: int = data["type"]

        self.uses: int = data.get("uses", 0)
        """ The number of times the invite has been used. """

        self.max_uses: int = data.get("max_uses", 0)
        """ The maximum number of times the invite can be used. """

        self.temporary: bool = data.get("temporary", False)
        """ Whether the invite grants temporary membership. """

        self.created_at: datetime | None = None
        """ The time the invite was created. """

        self.expires_at: datetime | None = None
        """ The time the invite expires, if applicable. """

        self.inviter: User | None = None
        """ The user who created the invite, if applicable. """

        self.guild_id: int | None = (
            utils.get_int(data, "guild_id") or
            utils.get_int(data.get("guild", {}), "id")
        )
        """ The ID of the guild the invite is in, if applicable. """

        self.approximate_presence_count: int | None = data.get("approximate_presence_count")
        """ The approximate number of online members, if applicable. """

        self.approximate_member_count: int | None = data.get("approximate_member_count")
        """ The approximate number of total members, if applicable. """

        self.roles: list[Role] = []
        """ The roles a user gets when joining via this invite. """

        self.flags: GuildInviteFlags = GuildInviteFlags.none()
        """ The flags associated with the invite. """

        self.target_type: InviteTargetType | None = None
        """ The target type of the invite, if applicable. """

        self.target_user: User | None = None
        """ The user of the invite whose stream to display for this invite. """

        self.channel_id: int | None = (
            utils.get_int(data, "channel_id") or
            utils.get_int(data.get("channel", {}), "id")
        )
        """ The ID of the channel the invite is in, if applicable. """

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Invite code='{self.code}' uses='{self.uses}'>"

    def _from_data(self, data: dict) -> None:
        if expires_at := data.get("expires_at"):
            self.expires_at = utils.parse_time(expires_at)

        if created_at := data.get("created_at"):
            self.created_at = utils.parse_time(created_at)

        if inviter := data.get("inviter"):
            self.inviter = User(state=self._state, data=inviter)

        if guild := data.get("guild"):
            try:
                self.guild = Guild(state=self._state, data=guild)
            except KeyError:
                pass

        if (target_type := data.get("target_type")) is not None:
            self.target_type = InviteTargetType(target_type)

        if target_user := data.get("target_user"):
            self.target_user = User(state=self._state, data=target_user)

        if flags := data.get("flags"):
            self.flags = GuildInviteFlags(flags)

        if (roles := data.get("roles")) and self.guild:
            self.roles = [
                Role(state=self._state, guild=self.guild, data=role_data)
                for role_data in roles
            ]

    @property
    def type(self) -> InviteType:
        """ The type of the invite. """
        return InviteType(self._raw_type)

    def is_vanity(self) -> bool:
        """ Whether the invite is a vanity invite. """
        if not self.guild:
            return False
        if not isinstance(self.guild, Guild):
            return False
        return self.guild.vanity_url_code == self.code
