from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import utils
from .object import PartialBase, Snowflake
from .user import PartialUser

MISSING = utils.MISSING

if TYPE_CHECKING:
    from .channel import BaseChannel, PartialChannel
    from .guild import PartialGuild
    from .http import DiscordAPI
    from .member import Member, PartialMember

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

    @property
    def member_id(self) -> int:
        """ The ID of the member (alias of `id`). """
        return self.id

    @property
    def guild(self) -> "PartialGuild | None":
        """ The partial guild of the voice state, if available. """
        if not self.guild_id:
            return None

        return self._state.bot.get_partial_guild(self.guild_id)

    @property
    def member(self) -> "PartialMember | PartialUser":
        """ The partial user/member of the state. """
        if self.guild:
            return self.guild.get_partial_member(self.member_id)

        return self._state.bot.get_partial_user(self.member_id)

    @property
    def channel(self) -> "PartialChannel | None":
        """ The partial channel of the state, if available """
        if not self.channel_id:
            return None

        return self._state.bot.get_partial_channel(self.channel_id)

    @property
    def _route_id(self) -> str:
        if self.id == self._state.bot.user.id:
            return "@me"

        return str(self.id)

    async def fetch(self) -> "VoiceState":
        """
        Fetches the voice state of the member.

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
            f"/guilds/{self.guild_id}/voice-states/{self._route_id}"
        )

        return VoiceState(
            state=self._state,
            data=r.response,
            guild_id=self.guild_id
        )

    async def edit(
        self,
        *,
        channel_id: Snowflake | int = MISSING,
        suppress: bool = MISSING,
        request_to_speak_timestamp: datetime | None = MISSING,
    ) -> None:
        """
        Updates the voice state of the member.

        If the voice state belongs to the bot, it will update its own voice state.

        Parameters
        ----------
        channel_id
            The ID of the stage channel the user is currently in
        suppress
            Whether to suppress the user
        request_to_speak_timestamp
            When the user requested to speak, or `None` to clear it.
            Only usable on the bot's own voice state.

        Raises
        ------
        ValueError
            - If the voice state has no guild_id
            - If `request_to_speak_timestamp` is used on another user's voice state
        """
        if not self.guild_id:
            raise ValueError("Cannot update voice state without guild_id")

        route_id = self._route_id
        data: dict[str, Any] = {}

        if channel_id is not MISSING:
            data["channel_id"] = str(utils.normalize_entity_id(channel_id))

        if suppress is not MISSING:
            data["suppress"] = bool(suppress)

        if request_to_speak_timestamp is not MISSING:
            if route_id != "@me":
                raise ValueError("request_to_speak_timestamp can only be used on the bot's own voice state")

            data["request_to_speak_timestamp"] = (
                request_to_speak_timestamp.isoformat()
                if request_to_speak_timestamp else None
            )

        await self._state.query(
            "PATCH",
            f"/guilds/{self.guild_id}/voice-states/{route_id}",
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

        self._member_data: "Member | None" = None

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

    @property
    def user(self) -> "PartialUser":
        """ The user this voice state belongs to. Resolved live from cache. """
        if (
            (cache := self._state.cache) is not None and
            (cached := cache.get_user(self.id)) is not None
        ):
            return cached

        return self._state.bot.get_partial_user(self.id)

    def _from_data(self, data: dict) -> None:
        if rts_timestamp := data.get("request_to_speak_timestamp"):
            self.request_to_speak_timestamp = utils.parse_time(
                rts_timestamp
            )

        if (member_data := data.get("member")) and (guild := self.guild) is not None:
            from .member import Member  # Circular import

            if not isinstance(guild.get_member(self.id), Member):
                self._member_data = self._state.bot.create_member_from_data(
                    member_data, guild=guild
                )

    @property
    def guild(self) -> "PartialGuild | None":
        """ The guild this voice state is in, if any. Resolved live from cache. """
        if self.guild_id is None:
            return None

        if cache := self._state.cache.get_guild(self.guild_id):
            return cache

        return self._state.bot.get_partial_guild(self.guild_id)

    @property
    def channel(self) -> "BaseChannel | PartialChannel | None":
        """ The voice channel this user is in, if any. Resolved live from cache. """
        if self.channel_id is None:
            return None

        if self.guild_id is not None and (cache := self._state.cache.get_channel(self.guild_id, self.channel_id)):
            return cache

        return self._state.bot.get_partial_channel(self.channel_id, guild_id=self.guild_id)

    @property
    def member(self) -> "Member | None":
        """
        The member this voice state belongs to, if any.

        Prefers an already-cached `Member` for this guild, falling back to
        the one built from the voice state payload if not cached.
        """
        if (guild := self.guild) is None:
            return None

        from .member import Member  # Circular import

        cached_member = guild.get_member(self.id)
        if isinstance(cached_member, Member):
            self._member_data = None
            return cached_member

        return self._member_data
