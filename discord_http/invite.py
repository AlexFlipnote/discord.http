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

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        return f"<PartialInvite code='{self.code}'>"

    @property
    def guild(self) -> PartialGuild | None:
        """ `Optional[PartialGuild]`: The guild the invite is in """
        if not self.guild_id:
            return None

        return PartialGuild(
            state=self._state,
            id=self.guild_id
        )

    @property
    def channel(self) -> "PartialChannel | None":
        """ `Optional[PartialChannel]`: The channel the invite is in """
        if not self.channel_id:
            return None

        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    async def fetch(self) -> "Invite":
        """
        Fetches the invite details

        Returns
        -------
        `Invite`
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
        Deletes the invite

        Parameters
        ----------
        reason: `str`
            The reason for deleting the invite

        Returns
        -------
        `Invite`
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
        """ `str`: The URL of the invite """
        return f"{self.BASE}/{self.code}"


class Invite(PartialInvite):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, code=data["code"])

        self.type: InviteType = InviteType(int(data["type"]))

        self.uses: int = int(data["uses"])
        self.max_uses: int = int(data["max_uses"])
        self.temporary: bool = data.get("temporary", False)
        self.created_at: datetime = utils.parse_time(data["created_at"])

        self.inviter: "User | None" = None
        self.expires_at: datetime | None = None
        self.guild: Guild | PartialGuild | None = None
        self.channel: "PartialChannel | None" = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Invite code='{self.code}' uses='{self.uses}'>"

    def _from_data(self, data: dict) -> None:
        if data["expires_at"]:
            self.expires_at = utils.parse_time(data["expires_at"])

        if data.get("guild", None):
            self.guild = Guild(state=self._state, data=data["guild"])
        elif data.get("guild_id", None):
            self.guild = PartialGuild(
                state=self._state,
                id=int(data["guild_id"])
            )

        guild_id = data.get("guild", {}).get("id", None)
        if data.get("channel", None):
            self.channel = PartialChannel(
                state=self._state,
                id=int(data["channel"]["id"]),
                guild_id=int(guild_id) if guild_id else None,
            )
        elif data.get("channel_id", None):
            self.channel = PartialChannel(
                state=self._state,
                id=int(data["channel_id"]),
                guild_id=int(guild_id) if guild_id else None,
            )

        if data.get("inviter", None):
            self.inviter = User(state=self._state, data=data["inviter"])

    def is_vanity(self) -> bool:
        """ `bool`: Whether the invite is a vanity invite """
        if not self.guild:
            return False
        if not isinstance(self.guild, Guild):
            return False
        return self.guild.vanity_url_code == self.code
