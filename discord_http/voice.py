from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import utils
from .object import PartialBase
from .user import PartialUser

MISSING = utils.MISSING

if TYPE_CHECKING:
    from .channel import BaseChannel, PartialChannel
    from .guild import PartialGuild
    from .http import DiscordAPI
    from .member import Member

__all__ = (
    "PartialVoiceState",
    "VoiceState",
)


class PartialVoiceState(PartialBase):
    """ Represents a partial voice state object. """

    __slots__ = (
        "_state",
        "channel_id",
        "guild_id",
    )

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
        """ The ID of the user this voice state belongs to. """

        self.channel_id: int | None = channel_id
        """ The ID of the voice channel this user is in, if any. """

        self.guild_id: int | None = guild_id
        """ The ID of the guild this voice state is in, if any. """

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
    """ Represents a voice state object. """

    __slots__ = (
        "channel",
        "deaf",
        "guild",
        "member",
        "mute",
        "request_to_speak_timestamp",
        "self_deaf",
        "self_mute",
        "self_stream",
        "self_video",
        "session_id",
        "suppress",
        "user",
    )

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
        """ The session ID of the voice state. """

        self.user: PartialUser = PartialUser(state=state, id=int(data["user_id"]))
        """ The user this voice state belongs to. """

        self.member: "Member | None" = None
        """ The member this voice state belongs to, if any. """

        self.channel: "BaseChannel | PartialChannel | None" = channel
        """ The voice channel this user is in, if any. """

        self.guild: "PartialGuild | None" = guild
        """ The guild this voice state is in, if any. """

        self.deaf: bool = data["deaf"]
        """ Whether the user is deafened by the server. """

        self.mute: bool = data["mute"]
        """ Whether the user is muted by the server. """

        self.self_deaf: bool = data["self_deaf"]
        """ Whether the user is deafened by themselves. """

        self.self_mute: bool = data["self_mute"]
        """ Whether the user is muted by themselves. """

        self.self_stream: bool = data.get("self_stream", False)
        """ Whether the user is streaming. """

        self.self_video: bool = data["self_video"]
        """ Whether the user is using video. """

        self.suppress: bool = data["suppress"]
        """ Whether the user is suppressed by the server. """

        self.request_to_speak_timestamp: datetime | None = None
        """ The timestamp when the user requested to speak, if any. """

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
