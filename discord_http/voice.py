from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

from . import utils
from .object import PartialBase
from .user import PartialUser

MISSING = utils.MISSING

if TYPE_CHECKING:
    from .member import Member
    from .channel import PartialChannel
    from .guild import PartialGuild
    from .http import DiscordAPI

__all__ = (
    "PartialVoiceState",
    "VoiceState",
)


class PartialVoiceState(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        channel_id: Optional[int] = None,
        guild_id: Optional[int] = None,
    ):
        self._state = state
        self.id: int = int(id)
        self.channel_id: Optional[int] = channel_id
        self.guild_id: Optional[int] = guild_id

    def __repr__(self) -> str:
        return f"<PartialVoiceState id={self.id} guild_id={self.guild_id}>"

    async def fetch(self) -> "VoiceState":
        """
        Fetches the voice state of the member

        Returns
        -------
        `VoiceState`
            The voice state of the member

        Raises
        ------
        `NotFound`
            - If the member is not in the guild
            - If the member is not in a voice channel
        """
        if not self.guild_id:
            raise ValueError("Cannot fetch voice state without guild_id")

        r = await self._state.query(
            "GET",
            f"/guilds/{self.guild_id}/voice-states/{self.id}"
        )

        return VoiceState(
            state=self._state,
            data=r.response
        )

    async def edit(
        self,
        *,
        suppress: bool = MISSING,
    ) -> None:
        """
        Updates the voice state of the member

        Parameters
        ----------
        suppress: `bool`
            Whether to suppress the user
        """
        if not self.guild_id:
            raise ValueError("Cannot update voice state without guild_id")

        data: dict[str, Any] = {}

        if suppress is not MISSING:
            data["suppress"] = bool(suppress)

        await self._state.query(
            "PATCH",
            f"/guilds/{self.guild_id}/voice-states/{int(self.id)}",
            json=data,
            res_method="text"
        )


class VoiceState(PartialVoiceState):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(
            state=state,
            id=int(data["user_id"]),
            guild_id=int(data["guild_id"])
        )

        self.session_id: str = data["session_id"]

        self.channel_id: Optional[int] = utils.get_int(data, "channel_id")
        self.guild_id: Optional[int] = utils.get_int(data, "guild_id")

        self.user: PartialUser = PartialUser(state=state, id=int(data["user_id"]))
        self.member: Optional["Member"] = None

        self.deaf: bool = data["deaf"]
        self.mute: bool = data["mute"]
        self.self_deaf: bool = data["self_deaf"]
        self.self_mute: bool = data["self_mute"]
        self.self_stream: bool = data.get("self_stream", False)
        self.self_video: bool = data["self_video"]
        self.suppress: bool = data["suppress"]
        self.request_to_speak_timestamp: Optional[datetime] = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<VoiceState id={self.user} session_id='{self.session_id}'>"

    def _from_data(self, data: dict) -> None:
        if data.get("member", None) and self.guild:
            from .member import Member
            self.member = Member(
                state=self._state,
                guild=self.guild,
                data=data["member"]
            )

        if data.get("request_to_speak_timestamp", None):
            self.request_to_speak_timestamp = utils.parse_time(
                data["request_to_speak_timestamp"]
            )

    @property
    def guild(self) -> Optional["PartialGuild"]:
        """ `PartialGuild`: Returns the guild the member is in """
        if not self.guild_id:
            return None

        from .guild import PartialGuild
        return PartialGuild(
            state=self._state,
            id=self.guild_id
        )

    @property
    def channel(self) -> Optional["PartialChannel"]:
        """ `PartialChannel`: Returns the channel the member is in """
        if not self.channel_id:
            return None

        from .channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id
        )
