from datetime import datetime
from typing import TYPE_CHECKING

from . import utils
from .channel import PartialChannel
from .enums import InviteType
from .guild import PartialGuild, Guild
from .user import User

if TYPE_CHECKING:
    from .http import DiscordAPI

__all__ = (
    "Invite",
    "PartialInvite",
)


class PartialInvite:
    """
    Represents a partial invite object.

    Attributes
    ----------
    code: str
        The invite code.
    channel_id: int | None
        The ID of the channel the invite is in, if applicable.
    guild_id: int | None
        The ID of the guild the invite is in, if applicable.
    guild: Guild | PartialGuild | None
        The guild associated with the invite, if applicable.
    """
    BASE = "https://discord.gg"

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

        self.channel_id = channel_id
        self.guild_id = guild_id

        self.guild: "Guild | PartialGuild | None" = self._get_guild

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
    """
    Represents an invite object.

    Attributes
    ----------
    code: str
        The invite code.
    uses: int
        The number of times the invite has been used.
    max_uses: int
        The maximum number of times the invite can be used.
    temporary: bool
        Whether the invite grants temporary membership.
    created_at: datetime | None
        The time the invite was created.
    expires_at: datetime | None
        The time the invite expires, if applicable.
    inviter: User | None
        The user who created the invite, if applicable.
    guild_id: int | None
        The ID of the guild the invite is in, if applicable.
    channel_id: int | None
        The ID of the channel the invite is in, if applicable.
    type: InviteType
        The type of the invite.
    """
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, code=data["code"])

        self.type: InviteType = InviteType(int(data["type"]))

        self.uses: int = data.get("uses", 0)
        self.max_uses: int = data.get("max_uses", 0)
        self.temporary: bool = data.get("temporary", False)

        self.created_at: datetime | None = None
        self.expires_at: datetime | None = None

        self.inviter: "User | None" = None

        self.guild_id: int | None = (
            utils.get_int(data, "guild_id") or
            utils.get_int(data.get("guild", {}), "id")
        )

        self.channel_id: int | None = (
            utils.get_int(data, "channel_id") or
            utils.get_int(data.get("channel", {}), "id")
        )

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Invite code='{self.code}' uses='{self.uses}'>"

    def _from_data(self, data: dict) -> None:
        if data.get("expires_at"):
            self.expires_at = utils.parse_time(data["expires_at"])

        if data.get("created_at"):
            self.created_at = utils.parse_time(data["created_at"])

        if data.get("inviter"):
            self.inviter = User(state=self._state, data=data["inviter"])

        if data.get("guild"):
            try:
                self.guild = Guild(state=self._state, data=data["guild"])
            except KeyError:
                pass

    def is_vanity(self) -> bool:
        """ Whether the invite is a vanity invite. """
        if not self.guild:
            return False
        if not isinstance(self.guild, Guild):
            return False
        return self.guild.vanity_url_code == self.code
