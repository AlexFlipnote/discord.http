from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import utils
from .object import PartialBase
from .user import PartialUser

MISSING = utils.MISSING

if TYPE_CHECKING:
    from .member import Member
    from .channel import BaseChannel, PartialChannel
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
        id: int,  # noqa: A002
        channel_id: int | None = None,
        guild_id: int | None = None,
    ):
        self._state = state
        self.id: int = int(id)
        self.channel_id: int | None = channel_id
        self.guild_id: int | None = guild_id

    def __repr__(self) -> str:
        return f"<PartialVoiceState id={self.id} guild_id={self.guild_id}>"

    async def fetch(self) -> "VoiceState":
        """
        Fetches the voice state of the member.

        Returns
        -------
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

        guild = self._state.cache.get_guild(self.guild_id)
        channel = None
        if self.channel_id is not None:
            channel = self._state.cache.get_channel(self.guild_id, self.channel_id)

        return VoiceState(
            state=self._state,
            data=r.response,
            guild=guild,
            channel=channel
        )

    async def edit(
        self,
        *,
        suppress: bool = MISSING,
    ) -> None:
        """
        Updates the voice state of the member.

        Parameters
        ----------
        suppress:
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
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | None",
        channel: "BaseChannel | PartialChannel | None"
    ):
        super().__init__(
            state=state,
            id=int(data["user_id"]),
            guild_id=utils.get_int(data, "guild_id"),
            channel_id=utils.get_int(data, "channel_id")
        )

        self.session_id: str = data["session_id"]

        self.user: PartialUser = PartialUser(state=state, id=int(data["user_id"]))
        self.member: "Member | None" = None

        self.channel: "BaseChannel | PartialChannel | None" = channel
        self.guild: "PartialGuild | None" = guild

        self.deaf: bool = data["deaf"]
        self.mute: bool = data["mute"]
        self.self_deaf: bool = data["self_deaf"]
        self.self_mute: bool = data["self_mute"]
        self.self_stream: bool = data.get("self_stream", False)
        self.self_video: bool = data["self_video"]
        self.suppress: bool = data["suppress"]
        self.request_to_speak_timestamp: datetime | None = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<VoiceState id={self.user} session_id='{self.session_id}'>"

    def _from_data(self, data: dict) -> None:
        if data.get("member") and self.guild:
            from .member import Member
            self.member = Member(
                state=self._state,
                guild=self.guild,
                data=data["member"]
            )

        if data.get("request_to_speak_timestamp"):
            self.request_to_speak_timestamp = utils.parse_time(
                data["request_to_speak_timestamp"]
            )
