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
        id: int,  # ruff: ignore[builtin-argument-shadowing]
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

    def __str__(self) -> str:
        return "PartialVoiceState"

    async def fetch(self) -> "VoiceState":
        """
        Fetches the voice state of the member.

        Returns
        -------
            The voice state of the member

        Raises
        ------
        NotFound
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
            data=r.response,
            guild_id=self.guild_id
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
        suppress
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
        "_member_data",
        "deaf",
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
        guild_id: int | None = None,
    ):
        super().__init__(
            state=state,
            id=int(data["user_id"]),
            guild_id=utils.get_int(data, "guild_id") or guild_id,
            channel_id=utils.get_int(data, "channel_id")
        )

        self.session_id: str = data["session_id"]
        """ The session ID of the voice state. """

        self.user: PartialUser = PartialUser(state=state, id=int(data["user_id"]))
        """ The user this voice state belongs to. """

        self._member_data: dict | None = data.get("member")

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
        if rts_timestamp := data.get("request_to_speak_timestamp"):
            self.request_to_speak_timestamp = utils.parse_time(
                rts_timestamp
            )

    @property
    def guild(self) -> "PartialGuild | None":
        """ The guild this voice state is in, if any. Resolved live from cache. """
        if self.guild_id is None:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "BaseChannel | PartialChannel | None":
        """ The voice channel this user is in, if any. Resolved live from cache. """
        if self.channel_id is None:
            return None

        if self.guild_id is not None:
            cache = self._state.cache.get_channel(self.guild_id, self.channel_id)
            if cache:
                return cache

        from .channel import PartialChannel
        return PartialChannel(state=self._state, id=self.channel_id, guild_id=self.guild_id)

    @property
    def member(self) -> "Member | None":
        """
        The member this voice state belongs to, if any.

        Prefers an already-cached `Member` for this guild (so this doesn't
        hold its own separate copy of member/user data), falling back to
        building one from the voice state payload if not cached.
        """
        guild = self.guild
        if guild is None:
            return None

        from .member import Member

        cached_member = guild.get_member(self.id)
        if isinstance(cached_member, Member):
            return cached_member

        if self._member_data is None:
            return None

        built = Member(
            state=self._state,
            guild=guild,
            data=self._member_data
        )

        cache = self._state.cache
        if cache is not None and cache._user_dedup_enabled:
            cache._dedupe_user(built)

        return built
