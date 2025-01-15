from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import (
    TYPE_CHECKING, Union, Optional, AsyncIterator, Callable,
    NamedTuple
)

from . import utils
from .asset import Asset
from .automod import (
    AutoModRule, PartialAutoModRule,
    AutoModRuleAction, AutoModRuleTriggers
)
from .colour import Colour, Color
from .enums import (
    ChannelType, VerificationLevel,
    DefaultNotificationLevel, ContentFilterLevel,
    ScheduledEventEntityType, PrivacyLevelType,
    ScheduledEventStatusType, VideoQualityType, AuditLogType,
    AutoModRuleEventType, AutoModRuleTriggerType, AutoModRulePresetType
)
from .emoji import Emoji, PartialEmoji
from .file import File
from .flags import Permissions, SystemChannelFlags, PermissionOverwrite
from .multipart import MultipartData
from .object import PartialBase, Snowflake
from .role import Role, PartialRole
from .soundboard import SoundboardSound, PartialSoundboardSound
from .sticker import Sticker, PartialSticker
from .voice import VoiceState, PartialVoiceState

if TYPE_CHECKING:
    from .channel import (
        TextChannel, VoiceChannel,
        PartialChannel, BaseChannel,
        CategoryChannel, PublicThread,
        VoiceRegion, StageChannel, PrivateThread
    )
    from .audit import AuditLogEntry
    from .http import DiscordAPI
    from .invite import Invite
    from .member import PartialMember, Member
    from .user import User
    from .integrations import Integration

MISSING = utils.MISSING

__all__ = (
    "Guild",
    "PartialGuild",
    "PartialScheduledEvent",
    "ScheduledEvent",
    "BanEntry",
)


@dataclass
class _GuildLimits:
    bitrate: int
    emojis: int
    filesize: int
    soundboards: int
    stickers: int


class BanEntry(NamedTuple):
    user: "User"
    reason: str | None


class PartialScheduledEvent(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        guild_id: int
    ):
        super().__init__(id=int(id))
        self._state = state

        self.guild_id: int = guild_id

    def __repr__(self) -> str:
        return f"<PartialScheduledEvent id={self.id}>"

    @property
    def guild(self) -> "Guild | PartialGuild":
        """ `PartialGuild`: The guild object this event is in """
        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def url(self) -> str:
        return f"https://discord.com/events/{self.guild_id}/{self.id}"

    async def fetch(self) -> "ScheduledEvent":
        """ `ScheduledEvent`: Fetches more information about the event """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.guild_id}/scheduled-events/{self.id}"
        )

        return ScheduledEvent(
            state=self._state,
            data=r.response
        )

    async def delete(self, *, reason: str | None = None) -> None:
        """ Delete the event (the bot must own the event) """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild_id}/scheduled-events/{self.id}",
            res_method="text",
            reason=reason
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        channel: Optional[Union["PartialChannel", int]] = MISSING,
        external_location: Optional[str] = MISSING,
        privacy_level: Optional[PrivacyLevelType] = MISSING,
        entity_type: Optional[ScheduledEventEntityType] = MISSING,
        status: Optional[ScheduledEventStatusType] = MISSING,
        start_time: Optional[Union[datetime, timedelta, int]] = MISSING,
        end_time: Optional[Union[datetime, timedelta, int]] = MISSING,
        image: Optional[Union[File, bytes]] = MISSING,
        reason: Optional[str] = None
    ) -> "ScheduledEvent":
        """
        Edit the event

        Parameters
        ----------
        name: `Optional[str]`
            New name of the event
        description: `Optional[str]`
            New description of the event
        channel: `Optional[Union[&quot;PartialChannel&quot;, int]]`
            New channel of the event
        privacy_level: `Optional[PrivacyLevelType]`
            New privacy level of the event
        entity_type: `Optional[ScheduledEventEntityType]`
            New entity type of the event
        status: `Optional[ScheduledEventStatusType]`
            New status of the event
        start_time: `Optional[Union[datetime, timedelta, int]]`
            New start time of the event
        end_time: `Optional[Union[datetime, timedelta, int]]`
            New end time of the event (only for external events)
        image: `Optional[Union[File, bytes]]`
            New image of the event
        reason: `Optional[str]`
            The reason for editing the event

        Returns
        -------
        `ScheduledEvent`
            The edited event

        Raises
        ------
        `ValueError`
            If the start_time is None
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = name

        if description is not MISSING:
            payload["description"] = description

        if channel is not MISSING:
            payload["channel_id"] = str(int(channel)) if channel else None

        if external_location is not MISSING:
            if external_location is None:
                payload["entity_metadata"] = None
            else:
                payload["entity_metadata"] = {
                    "location": external_location
                }

        if privacy_level is not MISSING:
            payload["privacy_level"] = int(
                privacy_level or
                PrivacyLevelType.guild_only
            )

        if entity_type is not MISSING:
            payload["entity_type"] = int(
                entity_type or
                ScheduledEventEntityType.voice
            )

        if status is not MISSING:
            payload["status"] = int(
                status or
                ScheduledEventStatusType.scheduled
            )

        if start_time is not MISSING:
            if start_time is None:
                raise ValueError("start_time cannot be None")
            payload["scheduled_start_time"] = utils.add_to_datetime(start_time).isoformat()

        if end_time is not MISSING:
            if end_time is None:
                payload["scheduled_end_time"] = None
            else:
                payload["scheduled_end_time"] = utils.add_to_datetime(end_time).isoformat()

        if image is not MISSING:
            if image is None:
                payload["image"] = None
            else:
                payload["image"] = utils.bytes_to_base64(image)

        r = await self._state.query(
            "PATCH",
            f"/guilds/{self.guild_id}/scheduled-events/{self.id}",
            json=payload,
            reason=reason
        )

        return ScheduledEvent(
            state=self._state,
            data=r.response,
        )


class ScheduledEvent(PartialScheduledEvent):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(
            state=state,
            id=int(data["id"]),
            guild_id=int(data["guild_id"])
        )

        self.name: str = data["name"]
        self.description: Optional[str] = data.get("description", None)
        self.user_count: Optional[int] = utils.get_int(data, "user_count")

        self.privacy_level: PrivacyLevelType = PrivacyLevelType(data["privacy_level"])
        self.status: ScheduledEventStatusType = ScheduledEventStatusType(data["status"])
        self.entity_type: ScheduledEventEntityType = ScheduledEventEntityType(data["entity_type"])

        self.channel: Optional[PartialChannel] = None
        self.creator: Optional["User"] = None

        self.start_time: datetime = utils.parse_time(data["scheduled_start_time"])
        self.end_time: Optional[datetime] = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ScheduledEvent id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def _from_data(self, data: dict):
        if data.get("creator", None):
            from .user import User
            self.creator = User(
                state=self._state,
                data=data["creator"]
            )

        if data.get("scheduled_end_time", None):
            self.end_time = utils.parse_time(data["scheduled_end_time"])

        if data.get("entity_id", None) in [
            ScheduledEventEntityType.stage_instance,
            ScheduledEventEntityType.voice
        ]:
            from .channel import PartialChannel
            self.channel = PartialChannel(
                state=self._state,
                id=int(data["entity_id"]),
                guild_id=self.guild_id
            )


class PartialGuild(PartialBase):
    def __init__(self, *, state: "DiscordAPI", id: int):
        super().__init__(id=int(id))
        self._state = state

        self.unavailable: bool = False

        self._cache_members: dict[int, Union["Member", "PartialMember"]] = {}
        self._cache_channels: dict[int, Union["BaseChannel", "PartialChannel"]] = {}
        self._cache_threads: dict[int, Union["PublicThread", "PrivateThread", "PartialChannel"]] = {}
        self._cache_roles: dict[int, Union["Role", "PartialRole"]] = {}
        self._cache_emojis: dict[int, Union["Emoji", "PartialEmoji"]] = {}
        self._cache_soundboard_sounds: dict[int, Union["SoundboardSound", "PartialSoundboardSound"]] = {}
        self._cache_stickers: dict[int, Union["Sticker", "PartialSticker"]] = {}
        self._cache_voice_states: dict[int, Union["VoiceState", "PartialVoiceState"]] = {}

        self.member_count: int | None = None
        self._large: bool | None = (
            None if self.member_count is None
            else self.member_count >= 250
        )

    def __repr__(self) -> str:
        return f"<PartialGuild id={self.id}>"

    @property
    def large(self) -> bool:
        """ `bool`: Whether the guild is considered large """
        if self._large is None:
            if self.member_count is not None:
                return self.member_count >= 250
            return len(self.members) >= 250
        return self.large

    @property
    def chunked(self) -> bool:
        """ `bool`: Whether the guild is chunked or not """
        count = self.member_count
        if count is None:
            return False
        return count == len(self._cache_members)

    def get_member(self, member_id: int) -> Optional[Union["Member", "PartialMember"]]:
        """
        Returns the member from cache if it exists.

        Parameters
        ----------
        member_id: `int`
            The ID of the member to get.

        Returns
        -------
        `Optional[Union["Member", "PartialMember"]`
            The member with the given ID, if it exists.
        """
        return self._cache_members.get(member_id, None)

    def get_channel(self, channel_id: int) -> Optional[Union["BaseChannel", "PartialChannel"]]:
        """
        Returns the channel from cache if it exists.

        Parameters
        ----------
        channel_id: `int`
            The ID of the channel to get.

        Returns
        -------
        `Optional[Union["BaseChannel", "PartialChannel"]`
            The channel with the given ID, if it exists.
        """
        return self._cache_channels.get(channel_id, None)

    def get_thread(self, thread_id: int) -> "BaseChannel | PartialChannel | None":
        """
        Returns the thread from cache if it exists.

        Parameters
        ----------
        thread_id: `int`
            The ID of the thread to get.

        Returns
        -------
        `Optional[Union["PartialThread", "PartialChannel"]`
            The thread with the given ID, if it exists.
        """
        return self._cache_threads.get(thread_id, None)

    def get_voice_states(self) -> list[Union["VoiceState", "PartialVoiceState"]]:
        """
        `Optional[Union[VoiceState, PartialVoiceState]]`:
        Returns the voice state of the guild
        """
        return list(self._cache_voice_states.values())

    def get_channel_voice_states(
        self,
        channel_id: int
    ) -> list[Union["VoiceState", "PartialVoiceState"]]:
        return [
            state
            for state in self._cache_voice_states.values()
            if state.channel_id == channel_id
        ]

    def get_member_voice_state(
        self,
        member_id: int
    ) -> Optional[Union["VoiceState", "PartialVoiceState"]]:
        """
        Returns the voice state of a member from cache if it exists.

        Parameters
        ----------
        member_id: `int`
            The ID of the member to get the voice state of.

        Returns
        -------
        `Optional[Union["VoiceState", "PartialVoiceState"]`
            The voice state of the member, if it exists.
        """
        return self._cache_voice_states.get(member_id, None)

    def get_role(self, role_id: int) -> Optional[Union["Role", "PartialRole"]]:
        """
        Returns the role from cache if it exists.

        Parameters
        ----------
        role_id: `int`
            The ID of the role to get.

        Returns
        -------
        `Optional[Union["Role", "PartialRole"]`
            The role with the given ID, if it exists.
        """
        return self._cache_roles.get(role_id, None)

    def get_soundboard_sound(self, sound_id: int) -> Optional[Union["SoundboardSound", "PartialSoundboardSound"]]:
        """
        Returns the soundboard sound from cache if it exists.

        Parameters
        ----------
        sound_id: `int`
            The ID of the soundboard sound to get.

        Returns
        -------
        `Optional[Union["SoundboardSound", "PartialSoundboardSound"]`
            The soundboard sound with the given ID, if it exists.
        """
        return self._cache_soundboard_sounds.get(sound_id, None)

    @property
    def members(self) -> list[Union["Member", "PartialMember"]]:
        """
        `list[Union[Member, PartialMember]]`:
        Returns a list of all the members in the guild if they are cached.
        """
        return list(self._cache_members.values())

    @property
    def channels(self) -> list[Union["BaseChannel", "PartialChannel"]]:
        """
        `list[Union[BaseChannel, PartialChannel]]`:
        Returns a list of all the channels in the guild if they are cached.
        """
        return list(self._cache_channels.values())

    @property
    def threads(self) -> list[Union["BaseChannel", "PartialChannel"]]:
        """
        `list[Union[BaseChannel, PartialChannel]]`:
        Returns a list of all the threads in the guild if they are cached.
        """
        return list(self._cache_threads.values())

    @property
    def roles(self) -> list[Union["Role", "PartialRole"]]:
        """
        `list[Union[Role, PartialRole]]`:
        Returns a list of all the roles in the guild if they are cached or
        if the guild was fetched
        """
        return list(self._cache_roles.values())

    @property
    def emojis(self) -> list[Union["Emoji", "PartialEmoji"]]:
        """
        `list[Union[Emoji, PartialEmoji]]`:
        Returns a list of all the emojis in the guild if they are cached.
        """
        return list(self._cache_emojis.values())

    @property
    def soundboard_sounds(self) -> list[Union["SoundboardSound", "PartialSoundboardSound"]]:
        """
        `list[Union[SoundboardSound, PartialSoundboardSound]]`:
        Returns a list of all the soundboard sounds in the guild if they are cached.
        """
        return list(self._cache_soundboard_sounds.values())

    @property
    def stickers(self) -> list[Union["Sticker", "PartialSticker"]]:
        """
        `list[Union[Sticker, PartialSticker]]`:
        Returns a list of all the stickers in the guild if they are cached.
        """
        return list(self._cache_stickers.values())

    @property
    def text_channels(self) -> list["TextChannel"]:
        """
        `list[TextChannel]`:
        Returns a list of all the text channels in the guild if they are cached.
        """
        return [
            channel  # type: ignore
            for channel in self.channels
            if channel.type == ChannelType.guild_text or
            channel.type == ChannelType.guild_news
        ]

    @property
    def voice_channels(self) -> list["VoiceChannel"]:
        """
        `list[VoiceChannel]`:
        Returns a list of all the voice channels in the guild if they are cached.
        """
        return [
            channel  # type: ignore
            for channel in self.channels
            if channel.type == ChannelType.guild_voice
        ]

    @property
    def categories(self) -> list["CategoryChannel"]:
        """
        `list[CategoryChannel]`:
        Returns a list of all the category channels in the guild if they are cached.
        """
        return [
            channel  # type: ignore
            for channel in self.channels
            if channel.type == ChannelType.guild_category
        ]

    @property
    def default_role(self) -> PartialRole:
        """ `Role`: Returns the default role, but as a partial role object """
        return PartialRole(
            state=self._state,
            id=self.id,
            guild_id=self.id
        )

    async def leave(self) -> None:
        """ Leave the guild """
        await self._state.query(
            "DELETE",
            f"/users/@me/guilds/{self.id}",
            res_method="text"
        )

    async def fetch(self) -> "Guild":
        """ `Guild`: Fetches more information about the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}"
        )

        return Guild(
            state=self._state,
            data=r.response
        )

    def get_partial_automod_rule(self, automod_id: int) -> PartialAutoModRule:
        """ `PartialAutoModRule`: Returns a partial automod rule object """
        return PartialAutoModRule(
            state=self._state,
            id=automod_id,
            guild_id=self.id
        )

    async def fetch_automod_rule(self, automod_id: int) -> AutoModRule:
        """ `AutoModRule`: Fetches a automod rule from the guild """
        automod = self.get_partial_automod_rule(automod_id)
        return await automod.fetch()

    async def fetch_automod_rules(self) -> list[AutoModRule]:
        """ `list[AutoModRule]` Fetches all the automod rules in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/auto-moderation/rules"
        )

        return [
            AutoModRule(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    async def create_automod_rule(
        self,
        name: str,
        *,
        event_type: AutoModRuleEventType | int,
        trigger_type: AutoModRuleTriggerType | int,
        keyword_filter: list[str] | None = None,
        regex_patterns: list[str] | None = None,
        presets: list[AutoModRulePresetType] | None = None,
        allow_list: list[str] | None = None,
        mention_total_limit: int | None = None,
        mention_raid_protection_enabled: bool = False,
        alert_channel: Snowflake | int | None = None,
        timeout_seconds: int | None = None,
        message: str | None = None,
        enabled: bool = True,
        exempt_roles: list[Snowflake | int] | None = None,
        exempt_channels: list[Snowflake | int] | None = None,
        reason: str | None = None,
    ) -> AutoModRule:
        """
        Create an automod rule

        Parameters
        ----------
        name: `str`
            Name of the automod
        event_type: `AutoModRuleEventType | int`
            What type of event
        trigger_type: `AutoModRuleTriggerType | int`
            What should make it get triggered
        keyword_filter: `list[str] | None`
            Keywords to filter
        regex_patterns: `list[str] | None`
            Keywords in regex pattern to filter
        presets: `list[AutoModRulePresetType] | None`
            Automod presets to include
        allow_list: `list[str] | None`
            List of keywords that are allowed
        mention_total_limit: `int | None`
            How many unique mentions allowed before trigger
        mention_raid_protection_enabled: `bool`
            If this should apply for raids
        alert_channel: `Snowflake | int | None`
            Where the action should be logged
        timeout_seconds: `int | None`
            How many seconds the user in question should be timed out
        message: `str | None`
            What message the user gets when action is taken
        enabled: `bool`
            If the automod should be enabled or not
        exempt_roles: `list[Snowflake  |  int] | None`
            Which roles are allowed to bypass
        exempt_channels: `list[Snowflake  |  int] | None`
            Which channels are allowed to bypass
        reason: `str | None`
            Reason for creating the automod

        Returns
        -------
        `AutoModRule`
            The automod that was just created
        """
        payload = {
            "name": str(name),
            "event_type": int(event_type),
            "trigger_type": int(trigger_type),
            "enabled": bool(enabled),
            "actions": []
        }

        if alert_channel is not None:
            payload["actions"].append(
                AutoModRuleAction.create_alert_location(
                    int(alert_channel)
                ).to_dict()
            )

        if timeout_seconds is not None:
            payload["actions"].append(
                AutoModRuleAction.create_timeout(
                    int(timeout_seconds)
                ).to_dict()
            )

        if message is not None:
            payload["actions"].append(
                AutoModRuleAction.create_message(
                    str(message)
                ).to_dict()
            )

        if exempt_roles is not None:
            payload["exempt_roles"] = [str(int(g)) for g in exempt_roles]

        if exempt_channels is not None:
            payload["exempt_channels"] = [str(int(g)) for g in exempt_channels]

        if any([
            keyword_filter,
            regex_patterns,
            presets,
            allow_list,
            mention_total_limit,
            mention_raid_protection_enabled
        ]):
            payload["trigger_metadata"] = AutoModRuleTriggers(
                keyword_filter=keyword_filter,
                regex_patterns=regex_patterns,
                presets=presets,
                allow_list=allow_list,
                mention_total_limit=mention_total_limit,
                mention_raid_protection_enabled=mention_raid_protection_enabled
            ).to_dict()

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/auto-moderation/rules",
            json=payload,
            reason=reason
        )

        return AutoModRule(
            state=self._state,
            data=r.response
        )

    async def fetch_roles(self) -> list[Role]:
        """ `list[Role]`: Fetches all the roles in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/roles"
        )

        return [
            Role(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def fetch_stickers(self) -> list[Sticker]:
        """ `list[Sticker]`: Fetches all the stickers in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/stickers"
        )

        return [
            Sticker(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def fetch_scheduled_events_list(self) -> list[ScheduledEvent]:
        """ `list[ScheduledEvent]`: Fetches all the scheduled events in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/scheduled-events?with_user_count=true"
        )

        return [
            ScheduledEvent(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    async def fetch_emojis(self) -> list[Emoji]:
        """ `list[Emoji]`: Fetches all the emojis in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/emojis"
        )

        return [
            Emoji(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def fetch_soundboard_sounds(self) -> list[SoundboardSound]:
        """ `list[SoundboardSound]`: Fetches all the soundboard sounds in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/soundboard-sounds"
        )

        return [
            SoundboardSound(
                state=self._state,
                guild=self,
                data=data
            )
            for data in r.response
        ]

    async def fetch_ban(self, user: Snowflake | int) -> BanEntry:
        """
        Fetches a user's ban of the guild

        Parameters
        ----------
        user: Snowflake | int
            The user to fetch the ban of

        Returns
        -------
        `BanEntry`
            Ban entry that was found
        """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/bans/{int(user)}"
        )

        from .user import User
        return BanEntry(
            user=User(state=self._state, data=r.response["user"]),
            reason=r.response["reason"]
        )

    async def fetch_bans(
        self,
        *,
        before: Optional[Union[Snowflake, int]] = None,
        after: Optional[Union[Snowflake, int]] = None,
        limit: Optional[int] = 1000,
    ) -> AsyncIterator["BanEntry"]:
        """
        Fetch the bans of the guild

        Parameters
        ----------
        before: `Optional[Union[Snowflake, int]]`
            Consider only users before given user id
        after: `Optional[Union[Snowflake, int]]`
            Consider only users after given user id
        limit: `Optional[int]`
            The maximum amount of messages to fetch.
            `None` will fetch all users.

        Yields
        ------
        `Message`
            The message object
        """
        async def _get_history(limit: int, **kwargs):
            params = {"limit": limit}
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = utils.normalize_entity_id(value)

            return await self._state.query(
                "GET",
                f"/guilds/{self.id}/bans",
                params=params
            )

        async def _after_http(
            http_limit: int,
            after_id: Optional[int],
            limit: Optional[int]
        ):
            r = await _get_history(limit=http_limit, after=after_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                after_id = int(r.response[0]["user"]["id"])

            return r.response, after_id, limit

        async def _before_http(
            http_limit: int,
            before_id: Optional[int],
            limit: Optional[int]
        ):
            r = await _get_history(limit=http_limit, before=before_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                before_id = int(r.response[-1]["user"]["id"])

            return r.response, before_id, limit

        if after:
            strategy, state = _after_http, utils.normalize_entity_id(after)
        elif before:
            strategy, state = _before_http, utils.normalize_entity_id(before)
        else:
            strategy, state = _before_http, None

        from .user import User

        while True:
            http_limit: int = 1000 if limit is None else min(limit, 1000)
            if http_limit <= 0:
                break

            strategy: Callable
            bans, state, limit = await strategy(http_limit, state, limit)

            i = 0
            for i, b in enumerate(bans, start=1):
                yield BanEntry(
                    user=User(state=self._state, data=b["user"]),
                    reason=b["reason"]
                )

            if i < 1000:
                break

    async def create_role(
        self,
        name: str,
        *,
        permissions: Optional[Permissions] = None,
        color: Optional[Union[Colour, Color, int]] = None,
        colour: Optional[Union[Colour, Color, int]] = None,
        unicode_emoji: Optional[str] = None,
        icon: Optional[Union[File, bytes]] = None,
        hoist: bool = False,
        mentionable: bool = False,
        reason: Optional[str] = None
    ) -> Role:
        """
        Create a role

        Parameters
        ----------
        name: `str`
            The name of the role
        permissions: `Optional[Permissions]`
            The permissions of the role
        color: `Optional[Union[Colour, Color, int]]`
            The colour of the role
        colour: `Optional[Union[Colour, Color, int]]`
            The colour of the role
        hoist: `bool`
            Whether the role should be hoisted
        mentionable: `bool`
            Whether the role should be mentionable
        unicode_emoji: `Optional[str]`
            The unicode emoji of the role
        icon: `Optional[File]`
            The icon of the role
        reason: `Optional[str]`
            The reason for creating the role

        Returns
        -------
        `Role`
            The created role
        """
        payload = {
            "name": name,
            "hoist": hoist,
            "mentionable": mentionable
        }

        if colour is not None:
            payload["color"] = int(colour)
        if color is not None:
            payload["color"] = int(color)

        if unicode_emoji is not None:
            payload["unicode_emoji"] = unicode_emoji
        if icon is not None:
            payload["icon"] = utils.bytes_to_base64(icon)

        if unicode_emoji and icon:
            raise ValueError("Cannot set both unicode_emoji and icon")

        if permissions:
            payload["permissions"] = int(permissions)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/roles",
            json=payload,
            reason=reason
        )

        return Role(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def create_scheduled_event(
        self,
        name: str,
        *,
        start_time: Union[datetime, timedelta, int],
        end_time: Optional[Union[datetime, timedelta, int]] = None,
        channel: Optional[Union["PartialChannel", int]] = None,
        description: Optional[str] = None,
        privacy_level: Optional[PrivacyLevelType] = None,
        entity_type: Optional[ScheduledEventEntityType] = None,
        external_location: Optional[str] = None,
        image: Optional[Union[File, bytes]] = None,
        reason: Optional[str] = None
    ) -> "ScheduledEvent":
        """
        Create a scheduled event

        Parameters
        ----------
        name: `str`
            The name of the event
        start_time: `Union[datetime, timedelta, int]`
            The start time of the event
        end_time: `Optional[Union[datetime, timedelta, int]]`
            The end time of the event
        channel: `Optional[Union[PartialChannel, int]]`
            The channel of the event
        description: `Optional[str]`
            The description of the event
        privacy_level: `Optional[PrivacyLevelType]`
            The privacy level of the event (default is guild_only)
        entity_type: `Optional[ScheduledEventEntityType]`
            The entity type of the event (default is voice)
        external_location: `Optional[str]`
            The external location of the event
        image: `Optional[Union[File, bytes]]`
            The image of the event
        reason: `Optional[str]`
            The reason for creating the event

        Returns
        -------
        `ScheduledEvent`
            The created event
        """
        if entity_type is ScheduledEventEntityType.external:
            if end_time is None:
                raise ValueError("end_time cannot be None for external events")
            if not external_location:
                raise ValueError("external_location cannot be None for external events")
            if channel:
                raise ValueError("channel cannot be set for external events")

        payload = {
            "name": name,
            "privacy_level": int(
                privacy_level or
                PrivacyLevelType.guild_only
            ),
            "scheduled_start_time": utils.add_to_datetime(start_time).isoformat(),
            "channel_id": str(int(channel)) if channel else None,
            "entity_type": int(
                entity_type or
                ScheduledEventEntityType.voice
            )
        }

        if description is not None:
            payload["description"] = str(description)

        if end_time is not None:
            payload["scheduled_end_time"] = utils.add_to_datetime(end_time).isoformat()

        if external_location is not None:
            payload["entity_metadata"] = {
                "location": str(external_location)
            }

        if image is not None:
            payload["image"] = utils.bytes_to_base64(image)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/scheduled-events",
            json=payload,
            reason=reason
        )

        return ScheduledEvent(
            state=self._state,
            data=r.response
        )

    async def create_category(
        self,
        name: str,
        *,
        overwrites: Optional[list[PermissionOverwrite]] = None,
        position: Optional[int] = None,
        reason: Optional[str] = None
    ) -> "CategoryChannel":
        """
        Create a category channel

        Parameters
        ----------
        name: `str`
            The name of the category
        overwrites: `Optional[list[PermissionOverwrite]]`
            The permission overwrites of the category
        position: `Optional[int]`
            The position of the category
        reason: `Optional[str]`
            The reason for creating the category

        Returns
        -------
        `CategoryChannel`
            The created category
        """
        payload = {
            "name": name,
            "type": int(ChannelType.guild_category)
        }

        if overwrites:
            payload["permission_overwrites"] = [
                g.to_dict() for g in overwrites
                if isinstance(g, PermissionOverwrite)
            ]

        if position is not None:
            payload["position"] = int(position)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/channels",
            json=payload,
            reason=reason
        )

        from .channel import CategoryChannel
        return CategoryChannel(
            state=self._state,
            data=r.response
        )

    async def create_text_channel(
        self,
        name: str,
        *,
        topic: Optional[str] = None,
        position: Optional[int] = None,
        rate_limit_per_user: Optional[int] = None,
        overwrites: Optional[list[PermissionOverwrite]] = None,
        parent_id: Optional[Union[Snowflake, int]] = None,
        nsfw: Optional[bool] = None,
        reason: Optional[str] = None
    ) -> "TextChannel":
        """
        Create a text channel

        Parameters
        ----------
        name: `str`
            The name of the channel
        topic: `Optional[str]`
            The topic of the channel
        rate_limit_per_user: `Optional[int]`
            The rate limit per user of the channel
        overwrites: `Optional[list[PermissionOverwrite]]`
            The permission overwrites of the category
        parent_id: `Optional[Snowflake]`
            The Category ID where the channel will be placed
        nsfw: `Optional[bool]`
            Whether the channel is NSFW or not
        reason: `Optional[str]`
            The reason for creating the text channel

        Returns
        -------
        `TextChannel`
            The created channel
        """
        payload = {
            "name": name,
            "type": int(ChannelType.guild_text)
        }

        if topic is not None:
            payload["topic"] = topic
        if rate_limit_per_user is not None:
            payload["rate_limit_per_user"] = (
                int(rate_limit_per_user)
                if isinstance(rate_limit_per_user, int)
                else None
            )
        if overwrites:
            payload["permission_overwrites"] = [
                g.to_dict() for g in overwrites
                if isinstance(g, PermissionOverwrite)
            ]
        if parent_id is not None:
            payload["parent_id"] = str(int(parent_id))
        if nsfw is not None:
            payload["nsfw"] = bool(nsfw)
        if position is not None:
            payload["position"] = int(position)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/channels",
            json=payload,
            reason=reason
        )

        from .channel import TextChannel
        return TextChannel(
            state=self._state,
            data=r.response
        )

    async def create_voice_channel(
        self,
        name: str,
        *,
        bitrate: Optional[int] = None,
        user_limit: Optional[int] = None,
        rate_limit_per_user: Optional[int] = None,
        overwrites: Optional[list[PermissionOverwrite]] = None,
        position: Optional[int] = None,
        video_quality_mode: Optional[Union[VideoQualityType, int]] = None,
        parent_id: Union[Snowflake, int, None] = None,
        nsfw: Optional[bool] = None,
        reason: Optional[str] = None
    ) -> "VoiceChannel":
        """
        Create a voice channel

        Parameters
        ----------
        name: `str`
            The name of the channel
        bitrate: `Optional[int]`
            The bitrate of the channel
        user_limit: `Optional[int]`
            The user limit of the channel
        rate_limit_per_user: `Optional`
            The rate limit per user of the channel
        overwrites: `Optional[list[PermissionOverwrite]]`
            The permission overwrites of the category
        position: `Optional[int]`
            The position of the channel
        video_quality_mode: `Optional[Union[VideoQualityType, int]]`
            The video quality mode of the channel
        parent_id: `Optional[Snowflake]`
            The Category ID where the channel will be placed
        nsfw: `Optional[bool]`
            Whether the channel is NSFW or not
        reason: `Optional[str]`
            The reason for creating the voice channel

        Returns
        -------
        `VoiceChannel`
            The created channel
        """
        payload = {
            "name": name,
            "type": int(ChannelType.guild_voice)
        }

        if bitrate is not None:
            payload["bitrate"] = int(bitrate)
        if user_limit is not None:
            payload["user_limit"] = int(user_limit)
        if rate_limit_per_user is not None:
            payload["rate_limit_per_user"] = int(rate_limit_per_user)
        if overwrites:
            payload["permission_overwrites"] = [
                g.to_dict() for g in overwrites
                if isinstance(g, PermissionOverwrite)
            ]
        if video_quality_mode is not None:
            payload["video_quality_mode"] = int(video_quality_mode)
        if position is not None:
            payload["position"] = int(position)
        if parent_id is not None:
            payload["parent_id"] = str(int(parent_id))
        if nsfw is not None:
            payload["nsfw"] = bool(nsfw)

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/channels",
            json=payload,
            reason=reason
        )

        from .channel import VoiceChannel
        return VoiceChannel(
            state=self._state,
            data=r.response
        )

    async def create_stage_channel(
        self,
        name: str,
        *,
        bitrate: Optional[int] = None,
        user_limit: Optional[int] = None,
        overwrites: Optional[list[PermissionOverwrite]] = None,
        position: Optional[int] = None,
        parent_id: Optional[Union[Snowflake, int]] = None,
        video_quality_mode: Optional[Union[VideoQualityType, int]] = None,
        reason: Optional[str] = None
    ) -> "StageChannel":
        """
        Create a stage channel

        Parameters
        ----------
        name: `str`
            The name of the channel
        bitrate: `Optional[int]`
            The bitrate of the channel
        user_limit: `Optional[int]`
            The user limit of the channel
        overwrites: `Optional[list[PermissionOverwrite]]`
            The permission overwrites of the category
        position: `Optional[int]`
            The position of the channel
        video_quality_mode: `Optional[Union[VideoQualityType, int]]`
            The video quality mode of the channel
        parent_id: `Optional[Union[Snowflake, int]]`
            The Category ID where the channel will be placed
        reason: `Optional[str]`
            The reason for creating the stage channel

        Returns
        -------
        `StageChannel`
            The created channel
        """
        payload = {
            "name": name,
            "type": int(ChannelType.guild_stage_voice)
        }

        if bitrate is not None:
            payload["bitrate"] = int(bitrate)
        if user_limit is not None:
            payload["user_limit"] = int(user_limit)
        if overwrites:
            payload["permission_overwrites"] = [
                g.to_dict() for g in overwrites
                if isinstance(g, PermissionOverwrite)
            ]
        if position is not None:
            payload["position"] = int(position)
        if video_quality_mode is not None:
            payload["video_quality_mode"] = int(video_quality_mode)
        if parent_id is not None:
            payload["parent_id"] = str(int(parent_id))

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/channels",
            json=payload,
            reason=reason
        )

        from .channel import StageChannel
        return StageChannel(
            state=self._state,
            data=r.response
        )

    async def create_emoji(
        self,
        name: str,
        *,
        image: Union[File, bytes],
        reason: Optional[str] = None
    ) -> Emoji:
        """
        Create an emoji

        Parameters
        ----------
        name: `str`
            Name of the emoji
        image: `File`
            File object to create an emoji from
        reason: `Optional[str]`
            The reason for creating the emoji

        Returns
        -------
        `Emoji`
            The created emoji
        """
        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/emojis",
            reason=reason,
            json={
                "name": name,
                "image": utils.bytes_to_base64(image)
            }
        )

        return Emoji(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def create_soundboard_sound(
        self,
        name: str,
        *,
        sound: Union[File, bytes],
        volume: Optional[int] = None,
        emoji_id: Optional[str] = None,
        emoji_name: Optional[str] = None,
        reason: Optional[str] = None
    ) -> SoundboardSound:
        """
        Create a soundboard sound

        Parameters
        ----------
        name: `str`
            Name of the soundboard sound
        sound: `File`
            File object to create a soundboard sound from
        volume: `Optional[int]`
            The volume of the soundboard sound
        emoji_name: `Optional[str]`
            The unicode emoji of the soundboard sound
        emoji_id: `Optional[str]`
            The ID of the custom emoji of the soundboard sound
        reason: `Optional[str]`
            The reason for creating the soundboard sound

        Returns
        -------
        `SoundboardSound`
            The created soundboard sound

        Raises
        ------
        `ValueError`
            If both `emoji_name` and `emoji_id` are set
        """
        mime_type = None
        if isinstance(sound, File):
            mime_type = "audio/mpeg" if sound.filename.endswith(".mp3") else None
            sound = sound.data.read()

        if not mime_type:
            mime_type = utils.mime_type_audio(sound)

        payload: dict[str, Union[str, int]] = {
            "name": name,
            "sound": f"data:{mime_type};base64,{b64encode(sound).decode('ascii')}"
        }

        if volume is not None:
            payload["volume"] = volume
        if emoji_name is not None:
            payload["emoji_name"] = emoji_name
        if emoji_id is not None:
            payload["emoji_id"] = emoji_id

        if (
            emoji_name is not MISSING and
            emoji_id is not MISSING
        ):
            raise ValueError("Cannot set both emoji_name and emoji_id")

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/soundboard-sounds",
            reason=reason,
            json=payload
        )

        return SoundboardSound(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def create_sticker(
        self,
        name: str,
        *,
        description: str,
        emoji: str,
        file: File,
        reason: Optional[str] = None
    ) -> Sticker:
        """
        Create a sticker

        Parameters
        ----------
        name: `str`
            Name of the sticker
        description: `str`
            Description of the sticker
        emoji: `str`
            Emoji that represents the sticker
        file: `File`
            File object to create a sticker from
        reason: `Optional[str]`
            The reason for creating the sticker

        Returns
        -------
        `Sticker`
            The created sticker
        """
        _bytes = file.data.read(16)
        try:
            mime_type = utils.mime_type_image(_bytes)
        except ValueError:
            mime_type = "application/octet-stream"
        finally:
            file.reset()

        multidata = MultipartData()

        multidata.attach("name", str(name))
        multidata.attach("description", str(description))
        multidata.attach("tags", utils.unicode_name(emoji))

        multidata.attach(
            "file",
            file,
            filename=file.filename,
            content_type=mime_type
        )

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/stickers",
            headers={"Content-Type": multidata.content_type},
            data=multidata.finish(),
            reason=reason
        )

        return Sticker(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def fetch_guild_prune_count(
        self,
        *,
        days: Optional[int] = 7,
        include_roles: Optional[list[Union[Role, PartialRole, int]]] = None
    ) -> int:
        """
        Fetch the amount of members that would be pruned

        Parameters
        ----------
        days: `Optional[int]`
            How many days of inactivity to prune for
        include_roles: `Optional[list[Union[Role, PartialRole, int]]]`
            Which roles to include in the prune

        Returns
        -------
        `int`
            The amount of members that would be pruned
        """
        _roles = []

        for r in include_roles or []:
            if isinstance(r, int):
                _roles.append(str(r))
            else:
                _roles.append(str(r.id))

        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/prune",
            params={
                "days": days,
                "include_roles": ",".join(_roles)
            }
        )

        return int(r.response["pruned"])

    async def begin_guild_prune(
        self,
        *,
        days: Optional[int] = 7,
        compute_prune_count: bool = True,
        include_roles: Optional[list[Union[Role, PartialRole, int]]] = None,
        reason: Optional[str] = None
    ) -> Optional[int]:
        """
        Begin a guild prune

        Parameters
        ----------
        days: `Optional[int]`
            How many days of inactivity to prune for
        compute_prune_count: `bool`
            Whether to return the amount of members that would be pruned
        include_roles: `Optional[list[Union[Role, PartialRole, int]]]`
            Which roles to include in the prune
        reason: `Optional[str]`
            The reason for beginning the prune

        Returns
        -------
        `Optional[int]`
            The amount of members that were pruned
        """
        payload = {
            "days": days,
            "compute_prune_count": compute_prune_count
        }

        _roles = []

        for r in include_roles or []:
            if isinstance(r, int):
                _roles.append(str(r))
            else:
                _roles.append(str(r.id))

        payload["include_roles"] = _roles or None

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/prune",
            json=payload,
            reason=reason
        )

        try:
            return int(r.response["pruned"])
        except (KeyError, TypeError):
            return None

    def get_partial_scheduled_event(
        self,
        id: int
    ) -> PartialScheduledEvent:
        """
        Creates a partial scheduled event object.

        Parameters
        ----------
        id: `int`
            The ID of the scheduled event.

        Returns
        -------
        `PartialScheduledEvent`
            The partial scheduled event object.
        """
        return PartialScheduledEvent(
            state=self._state,
            id=id,
            guild_id=self.id
        )

    async def fetch_scheduled_event(
        self, id: int
    ) -> ScheduledEvent:
        """
        Fetches a scheduled event object.

        Parameters
        ----------
        id: `int`
            The ID of the scheduled event.

        Returns
        -------
        `ScheduledEvent`
            The scheduled event object.
        """
        event = self.get_partial_scheduled_event(id)
        return await event.fetch()

    def get_partial_role(self, role_id: int) -> PartialRole:
        """
        Get a partial role object

        Parameters
        ----------
        role_id: `int`
            The ID of the role

        Returns
        -------
        `PartialRole`
            The partial role object
        """
        return PartialRole(
            state=self._state,
            id=role_id,
            guild_id=self.id
        )

    def get_partial_channel(self, channel_id: int) -> "PartialChannel":
        """
        Get a partial channel object

        Parameters
        ----------
        channel_id: `int`
            The ID of the channel

        Returns
        -------
        `PartialChannel`
            The partial channel object
        """
        from .channel import PartialChannel

        return PartialChannel(
            state=self._state,
            id=channel_id,
            guild_id=self.id
        )

    async def fetch_channel(self, channel_id: int) -> "BaseChannel":
        """
        Fetch a channel from the guild

        Parameters
        ----------
        channel_id: `int`
            The ID of the channel

        Returns
        -------
        `BaseChannel`
            The channel object
        """
        channel = self.get_partial_channel(channel_id)
        return await channel.fetch()

    def get_partial_emoji(self, emoji_id: int) -> PartialEmoji:
        """
        Get a partial emoji object

        Parameters
        ----------
        emoji_id: `int`
            The ID of the emoji

        Returns
        -------
        `PartialEmoji`
            The partial emoji object
        """
        return PartialEmoji(
            state=self._state,
            id=emoji_id,
            guild_id=self.id
        )

    def get_partial_soundboard_sound(self, sound_id: int) -> PartialSoundboardSound:
        """
        Get a partial soundboard sound object

        Parameters
        ----------
        sound_id: `int`
            The ID of the sound

        Returns
        -------
        `PartialEmoji`
            The partial soundboard sound object
        """
        return PartialSoundboardSound(
            state=self._state,
            id=sound_id,
            guild_id=self.id
        )

    async def fetch_soundboard_sound(self, sound_id: int) -> SoundboardSound:
        """ `SoundboardSound`: Fetches a soundboard sound from the guild """
        sound = self.get_partial_soundboard_sound(sound_id)
        return await sound.fetch()

    async def fetch_emoji(self, emoji_id: int) -> Emoji:
        """ `Emoji`: Fetches an emoji from the guild """
        emoji = self.get_partial_emoji(emoji_id)
        return await emoji.fetch()

    def get_partial_sticker(self, sticker_id: int) -> PartialSticker:
        """
        Get a partial sticker object

        Parameters
        ----------
        sticker_id: `int`
            The ID of the sticker

        Returns
        -------
        `PartialSticker`
            The partial sticker object
        """
        return PartialSticker(
            state=self._state,
            id=sticker_id,
            guild_id=self.id
        )

    async def fetch_sticker(self, sticker_id: int) -> Sticker:
        """
        Fetch a sticker from the guild

        Parameters
        ----------
        sticker_id: `int`
            The ID of the sticker

        Returns
        -------
        `Sticker`
            The sticker object
        """
        sticker = self.get_partial_sticker(sticker_id)
        return await sticker.fetch()

    def get_partial_member(self, member_id: int) -> "PartialMember":
        """
        Get a partial member object

        Parameters
        ----------
        member_id: `int`
            The ID of the member

        Returns
        -------
        `PartialMember`
            The partial member object
        """
        from .member import PartialMember

        return PartialMember(
            state=self._state,
            id=member_id,
            guild_id=self.id
        )

    async def fetch_member(self, member_id: int) -> "Member":
        """
        Fetch a member from the guild

        Parameters
        ----------
        member_id: `int`
            The ID of the member

        Returns
        -------
        `Member`
            The member object
        """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/members/{member_id}"
        )

        from .member import Member

        return Member(
            state=self._state,
            guild=self,
            data=r.response
        )

    async def fetch_public_threads(self) -> list["PublicThread"]:
        """
        Fetches all the public threads in the guild

        Returns
        -------
        `list[PublicThread]`
            The public threads in the guild
        """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/threads/active"
        )

        from .channel import PublicThread
        return [
            PublicThread(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    async def fetch_members(
        self,
        *,
        limit: Optional[int] = 1000,
        after: Optional[Union[Snowflake, int]] = None
    ) -> AsyncIterator["Member"]:
        """
        Fetches all the members in the guild

        Parameters
        ----------
        limit: `Optional[int]`
            The maximum amount of members to return
        after: `Optional[Union[Snowflake, int]]`
            The member to start after

        Yields
        ------
        `Members`
            The members in the guild
        """
        from .member import Member

        while True:
            http_limit = 1000 if limit is None else min(limit, 1000)
            if http_limit <= 0:
                break

            after_id = after or 0
            if isinstance(after, Snowflake):
                after_id = after.id

            data = await self._state.query(
                "GET",
                f"/guilds/{self.id}/members?limit={http_limit}&after={after_id}",
            )

            if not data.response:
                return

            if len(data.response) < 1000:
                limit = 0

            after = int(data.response[-1]["user"]["id"])

            for member_data in data.response:
                yield Member(
                    state=self._state,
                    guild=self,
                    data=member_data
                )

    async def fetch_regions(self) -> list["VoiceRegion"]:
        """ `list[VoiceRegion]`: Fetches all the voice regions for the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/regions"
        )

        return [
            VoiceRegion(data=data)
            for data in r.response
        ]

    async def fetch_invites(self) -> list["Invite"]:
        """ `list[Invite]`: Fetches all the invites for the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/invites"
        )

        from .invite import Invite
        return [
            Invite(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    def _ban_delete_time_converter(
        self,
        delete_message_days: int | None = 0,
        delete_message_seconds: int | None = 0,
    ) -> int:
        _delete_seconds = 0

        if delete_message_days and delete_message_seconds:
            raise ValueError("Cannot specify both delete_message_days and delete_message_seconds")

        if delete_message_days:
            if delete_message_days not in range(0, 8):
                raise ValueError("delete_message_days must be between 0 and 7")
            _delete_seconds = int(timedelta(days=delete_message_days).total_seconds())

        if delete_message_seconds:
            if delete_message_seconds not in range(0, 604801):
                raise ValueError("delete_message_seconds must be between 0 and 604,800")
            _delete_seconds = delete_message_seconds

        return _delete_seconds

    async def bulk_ban(
        self,
        *members: "Member | PartialMember | int",
        delete_message_days: int | None = 0,
        delete_message_seconds: int | None = 0,
        reason: str | None = None,
    ) -> list["PartialMember"]:
        """
        Ban multiple members from the server

        Parameters
        ----------
        *members: `Union[Member, PartialMember, int]`
            The members to ban
        """
        payload: dict[str, list[str] | int] = {
            # To avoid duplicate IDs, we use set()
            "user_ids": list(set([str(int(g)) for g in members]))
        }

        if not payload["user_ids"]:
            raise ValueError("Cannot ban an empty list of members")

        if len(payload["user_ids"]) > 200:  # type: ignore
            raise ValueError("Cannot ban more than 200 members at once")

        if delete_message_days or delete_message_seconds:
            payload["delete_message_seconds"] = self._ban_delete_time_converter(
                delete_message_days=delete_message_days,
                delete_message_seconds=delete_message_seconds
            )

        r = await self._state.query(
            "POST",
            f"/guilds/{self.id}/bulk-ban",
            reason=reason,
            json=payload
        )

        banned_users = r.response.get("banned_users", [])
        if not banned_users:
            return []

        from .member import PartialMember
        return [
            PartialMember(
                state=self._state,
                id=int(g),
                guild_id=self.id
            )
            for g in banned_users
        ]

    async def ban(
        self,
        member: "Member | PartialMember | int",
        *,
        delete_message_days: int | None = 0,
        delete_message_seconds: int | None = 0,
        reason: str | None = None,
    ) -> None:
        """
        Ban a member from the server

        Parameters
        ----------
        member: `Union[Member, PartialMember, int]`
            The member to ban
        reason: `Optional[str]`
            The reason for banning the member
        delete_message_days: `Optional[int]`
            How many days of messages to delete
        delete_message_seconds: `Optional[int]`
            How many seconds of messages to delete
        """
        payload = {}
        if delete_message_days or delete_message_seconds:
            payload["delete_message_seconds"] = self._ban_delete_time_converter(
                delete_message_days=delete_message_days,
                delete_message_seconds=delete_message_seconds
            )

        await self._state.query(
            "PUT",
            f"/guilds/{self.id}/bans/{int(member)}",
            reason=reason,
            json=payload
        )

    async def unban(
        self,
        member: Union["Member", "PartialMember", int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Unban a member from the server

        Parameters
        ----------
        member: `Union[Member, PartialMember, int]`
            The member to unban
        reason: `Optional[str]`
            The reason for unbanning the member
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.id}/bans/{int(member)}",
            reason=reason,
            res_method="text"
        )

    async def kick(
        self,
        member: Union["Member", "PartialMember", int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Kick a member from the server

        Parameters
        ----------
        member: `Union[Member, PartialMember, int]`
            The member to kick
        reason: `Optional[str]`
            The reason for kicking the member
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.id}/members/{int(member)}",
            reason=reason,
            res_method="text"
        )

    async def fetch_channels(self) -> list[type["BaseChannel"]]:
        """ `list[BaseChannel]`: Fetches all the channels in the guild """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/channels"
        )

        from .channel import PartialChannel
        return [
            PartialChannel.from_dict(
                state=self._state,
                data=data  # type: ignore
            )
            for data in r.response
        ]

    async def fetch_audit_logs(
        self,
        *,
        before: Optional[Union[datetime, "AuditLogEntry", Snowflake, int]] = None,
        after: Optional[Union[datetime, "AuditLogEntry", Snowflake, int]] = None,
        user: Optional[Union[Snowflake, int]] = None,
        action: Optional[AuditLogType] = None,
        limit: Optional[int] = 100,
    ) -> AsyncIterator["AuditLogEntry"]:
        """
        Fetches the audit logs for the guild

        Parameters
        ----------
        before: `Optional[Union[datetime, AuditLogEntry, Snowflake, int]]`
            Consider only entries before given entry
        after: `Optional[Union[datetime, AuditLogEntry, Snowflake, int]]`
            Consider only entries after given entry
        user: `Optional[Union[Snowflake, int]]`
            Consider only entries made by given user
        action: `Optional[AuditLogType]`
            Consider only entries with given action
        limit: `Optional[int]`
            The maximum amount of messages to fetch.

        Returns
        -------
        `list[AuditLogEntry]`
            The audit logs for the guild
        """
        async def _get_history(limit: int, **kwargs):
            params = {"limit": limit}
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = utils.normalize_entity_id(value)

            return await self._state.query(
                "GET",
                f"/guilds/{self.id}/audit-logs",
                params=params
            )

        async def _after_http(
            http_limit: int,
            after_id: Optional[int],
            limit: Optional[int],
            **kwargs
        ):
            r = await _get_history(limit=http_limit, after=after_id, **kwargs)
            _data = r.response.get("audit_log_entries", [])

            if _data:
                if limit is not None:
                    limit -= len(_data)
                after_id = int(_data[0]["id"])

            return r.response, after_id, limit

        async def _before_http(
            http_limit: int,
            before_id: Optional[int],
            limit: Optional[int],
            **kwargs
        ):
            r = await _get_history(limit=http_limit, before=before_id, **kwargs)
            _data = r.response.get("audit_log_entries", [])

            if _data:
                if limit is not None:
                    limit -= len(_data)
                before_id = int(_data[-1]["id"])

            return r.response, before_id, limit

        if after:
            strategy, state = _after_http, utils.normalize_entity_id(after)
        elif before:
            strategy, state = _before_http, utils.normalize_entity_id(before)
        else:
            strategy, state = _before_http, None

        # Avoid circular import, fun times...
        from .audit import AuditLogEntry
        from .user import User

        search_kwargs = {}

        if user is not None:
            search_kwargs["user_id"] = utils.normalize_entity_id(user)
        if action is not None:
            search_kwargs["action_type"] = int(action)

        while True:
            http_limit: int = 100 if limit is None else min(limit, 100)
            if http_limit <= 0:
                break

            strategy: Callable
            data, state, limit = await strategy(http_limit, state, limit, **search_kwargs)

            _users = {
                int(g["id"]): User(
                    state=self._state,
                    data=g
                )
                for g in data.get("users", [])
            }

            i = 0
            for i, entry in enumerate(data["audit_log_entries"], start=1):
                yield AuditLogEntry(
                    state=self._state,
                    data=entry,
                    guild=self,
                    users=_users
                )

            if i < 100:
                break

    async def search_members(
        self,
        query: str,
        *,
        limit: Optional[int] = 100
    ) -> list["Member"]:
        """
        Search for members in the guild

        Parameters
        ----------
        query: `str`
            The query to search for
        limit: `Optional[int]`
            The maximum amount of members to return

        Returns
        -------
        `list[Member]`
            The members that matched the query

        Raises
        ------
        `ValueError`
            If the limit is not between 1 and 1000
        """
        if limit not in range(1, 1001):
            raise ValueError("Limit must be between 1 and 1000")

        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/members/search",
            params={
                "query": query,
                "limit": limit
            }
        )

        from .member import Member
        return [
            Member(
                state=self._state,
                guild=self,
                data=m
            )
            for m in r.response
        ]

    async def fetch_integrations(self) -> list["Integration"]:
        """Fetches the integrations for the guild.

        This requires the `MANAGE_GUILD` permission.

        Returns
        -------
        `list[Integration]`
            The integrations in the guild.
        """
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/integrations"
        )

        from .integrations import Integration
        return [
            Integration(
                state=self._state,
                data=data,
                guild=self
            )
            for data in r.response
        ]

    async def delete(self) -> None:
        """ Delete the guild (the bot must own the server) """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.id}",
            res_method="text"
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        verification_level: Optional[VerificationLevel] = MISSING,
        default_message_notifications: Optional[DefaultNotificationLevel] = MISSING,
        explicit_content_filter: Optional[ContentFilterLevel] = MISSING,
        afk_channel_id: Union["VoiceChannel", "PartialChannel", int, None] = MISSING,
        afk_timeout: Optional[int] = MISSING,
        icon: Optional[Union[File, bytes]] = MISSING,
        owner_id: Union["Member", "PartialMember", int, None] = MISSING,
        splash: Optional[Union[File, bytes]] = MISSING,
        discovery_splash: Optional[File] = MISSING,
        banner: Optional[Union[File, bytes]] = MISSING,
        system_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        system_channel_flags: Optional[SystemChannelFlags] = MISSING,
        rules_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        public_updates_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        preferred_locale: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        features: Optional[list[str]] = MISSING,
        premium_progress_bar_enabled: Optional[bool] = MISSING,
        safety_alerts_channel_id: Union["TextChannel", "PartialChannel", int, None] = MISSING,
        reason: Optional[str] = None
    ) -> "PartialGuild":
        """
        Edit the guild

        Parameters
        ----------
        name: `Optional[str]`
            New name of the guild
        verification_level: `Optional[VerificationLevel]`
            Verification level of the guild
        default_message_notifications: `Optional[DefaultNotificationLevel]`
            Default message notification level of the guild
        explicit_content_filter: `Optional[ContentFilterLevel]`
            Explicit content filter level of the guild
        afk_channel_id: `Optional[Union[VoiceChannel, PartialChannel, int]]`
            AFK channel of the guild
        afk_timeout: `Optional[int]`
            AFK timeout of the guild
        icon: `Optional[File]`
            Icon of the guild
        owner_id: `Optional[Union[Member, PartialMember, int]]`
            Owner of the guild
        splash: `Optional[File]`
            Splash of the guild
        discovery_splash: `Optional[File]`
            Discovery splash of the guild
        banner: `Optional[File]`
            Banner of the guild
        system_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            System channel of the guild
        system_channel_flags: `Optional[SystemChannelFlags]`
            System channel flags of the guild
        rules_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            Rules channel of the guild
        public_updates_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            Public updates channel of the guild
        preferred_locale: `Optional[str]`
            Preferred locale of the guild
        description: `Optional[str]`
            Description of the guild
        features: `Optional[list[str]]`
            Features of the guild
        premium_progress_bar_enabled: `Optional[bool]`
            Whether the premium progress bar is enabled
        safety_alerts_channel_id: `Optional[Union[TextChannel, PartialChannel, int]]`
            Safety alerts channel of the guild
        reason: `Optional[str]`
            The reason for editing the guild

        Returns
        -------
        `PartialGuild`
            The edited guild
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = name
        if verification_level is not MISSING:
            payload["verification_level"] = int(verification_level or 0)
        if default_message_notifications is not MISSING:
            payload["default_message_notifications"] = int(default_message_notifications or 0)
        if explicit_content_filter is not MISSING:
            payload["explicit_content_filter"] = int(explicit_content_filter or 0)
        if afk_channel_id is not MISSING:
            payload["afk_channel_id"] = str(int(afk_channel_id)) if afk_channel_id else None
        if afk_timeout is not MISSING:
            payload["afk_timeout"] = int(afk_timeout or 0)
        if icon is not MISSING:
            payload["icon"] = utils.bytes_to_base64(icon) if icon else None
        if owner_id is not MISSING:
            payload["owner_id"] = str(int(owner_id)) if owner_id else None
        if splash is not MISSING:
            payload["splash"] = (
                utils.bytes_to_base64(splash)
                if splash else None
            )
        if discovery_splash is not MISSING:
            payload["discovery_splash"] = (
                utils.bytes_to_base64(discovery_splash)
                if discovery_splash else None
            )
        if banner is not MISSING:
            payload["banner"] = (
                utils.bytes_to_base64(banner)
                if banner else None
            )
        if system_channel_id is not MISSING:
            payload["system_channel_id"] = (
                str(int(system_channel_id))
                if system_channel_id else None
            )
        if system_channel_flags is not MISSING:
            payload["system_channel_flags"] = (
                int(system_channel_flags)
                if system_channel_flags else None
            )
        if rules_channel_id is not MISSING:
            payload["rules_channel_id"] = (
                str(int(rules_channel_id))
                if rules_channel_id else None
            )
        if public_updates_channel_id is not MISSING:
            payload["public_updates_channel_id"] = (
                str(int(public_updates_channel_id))
                if public_updates_channel_id else None
            )
        if preferred_locale is not MISSING:
            payload["preferred_locale"] = str(preferred_locale)
        if description is not MISSING:
            payload["description"] = str(description)
        if features is not MISSING:
            payload["features"] = features
        if premium_progress_bar_enabled is not MISSING:
            payload["premium_progress_bar_enabled"] = bool(premium_progress_bar_enabled)
        if safety_alerts_channel_id is not MISSING:
            payload["safety_alerts_channel_id"] = (
                str(int(safety_alerts_channel_id))
                if safety_alerts_channel_id else None
            )

        r = await self._state.query(
            "PATCH",
            f"/guilds/{self.id}",
            json=payload,
            reason=reason
        )

        return Guild(
            state=self._state,
            data=r.response
        )


class Guild(PartialGuild):
    _GUILD_LIMITS: dict[int, _GuildLimits] = {
        0: _GuildLimits(emojis=50, stickers=5, bitrate=96_000, filesize=26_214_400, soundboards=8),
        1: _GuildLimits(emojis=100, stickers=15, bitrate=128_000, filesize=26_214_400, soundboards=24),
        2: _GuildLimits(emojis=150, stickers=30, bitrate=256_000, filesize=52_428_800, soundboards=36),
        3: _GuildLimits(emojis=250, stickers=60, bitrate=384_000, filesize=104_857_600, soundboards=48),
    }

    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, id=int(data["id"]))
        self.afk_channel_id: Optional[int] = utils.get_int(data, "afk_channel_id")
        self.afk_timeout: int = data.get("afk_timeout", 0)
        self.default_message_notifications: int = data.get("default_message_notifications", 0)
        self.description: Optional[str] = data.get("description", None)

        self._icon = data.get("icon", None)
        self._banner = data.get("banner", None)

        self.explicit_content_filter: int = data.get("explicit_content_filter", 0)
        self.features: list[str] = data.get("features", [])
        self.latest_onboarding_question_id: Optional[int] = utils.get_int(data, "latest_onboarding_question_id")
        self.max_members: int = data.get("max_members", 0)
        self.max_stage_video_channel_users: int = data.get("max_stage_video_channel_users", 0)
        self.max_video_channel_users: int = data.get("max_video_channel_users", 0)
        self.mfa_level: Optional[int] = utils.get_int(data, "mfa_level")
        self.name: str = data["name"]
        self.nsfw: bool = data.get("nsfw", False)
        self.nsfw_level: int = data.get("nsfw_level", 0)
        self.owner_id: Optional[int] = utils.get_int(data, "owner_id")
        self.preferred_locale: Optional[str] = data.get("preferred_locale", None)
        self.premium_progress_bar_enabled: bool = data.get("premium_progress_bar_enabled", False)
        self.premium_subscription_count: int = data.get("premium_subscription_count", 0)
        self.premium_tier: int = data.get("premium_tier", 0)
        self.public_updates_channel_id: Optional[int] = utils.get_int(data, "public_updates_channel_id")
        self.region: Optional[str] = data.get("region", None)
        self.safety_alerts_channel_id: Optional[int] = utils.get_int(data, "safety_alerts_channel_id")
        self.system_channel_flags: int = data.get("system_channel_flags", 0)
        self.system_channel_id: Optional[int] = utils.get_int(data, "system_channel_id")
        self.vanity_url_code: Optional[str] = data.get("vanity_url_code", None)
        self.verification_level: VerificationLevel = VerificationLevel(data.get("verification_level", 0))
        self.widget_channel_id: Optional[int] = utils.get_int(data, "widget_channel_id")
        self.widget_enabled: bool = data.get("widget_enabled", False)

        self._from_data(data)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Guild id={self.id} name='{self.name}'>"

    def _from_data(self, data: dict) -> None:
        self._cache_roles = {
            int(g["id"]): Role(
                state=self._state,
                guild=self,
                data=g
            )
            for g in data["roles"]
        }

        self._cache_emojis = {
            int(g["id"]): Emoji(
                state=self._state,
                guild=self,
                data=g
            )
            for g in data["emojis"]
        }

        self._cache_stickers = {
            int(g["id"]): Sticker(
                state=self._state,
                guild=self,
                data=g
            )
            for g in data["stickers"]
        }

        if data.get("member_count", None):
            self.member_count = data["member_count"]

    def _update(self, data: dict) -> None:
        """ Update the guild from the data """
        self.afk_channel_id: Optional[int] = utils.get_int(data, "afk_channel_id")
        self.afk_timeout: int = data.get("afk_timeout", 0)
        self.default_message_notifications: int = data.get("default_message_notifications", 0)
        self.description: Optional[str] = data.get("description", None)
        self.explicit_content_filter: int = data.get("explicit_content_filter", 0)
        self.features: list[str] = data.get("features", [])
        self.latest_onboarding_question_id: Optional[int] = utils.get_int(data, "latest_onboarding_question_id")
        self.max_members: int = data.get("max_members", 0)
        self.max_stage_video_channel_users: int = data.get("max_stage_video_channel_users", 0)
        self.max_video_channel_users: int = data.get("max_video_channel_users", 0)
        self.mfa_level: Optional[int] = utils.get_int(data, "mfa_level")
        self.name: str = data["name"]
        self.nsfw: bool = data.get("nsfw", False)
        self.nsfw_level: int = data.get("nsfw_level", 0)
        self.owner_id: Optional[int] = utils.get_int(data, "owner_id")
        self.preferred_locale: Optional[str] = data.get("preferred_locale", None)
        self.premium_progress_bar_enabled: bool = data.get("premium_progress_bar_enabled", False)
        self.premium_subscription_count: int = data.get("premium_subscription_count", 0)
        self.premium_tier: int = data.get("premium_tier", 0)
        self.public_updates_channel_id: Optional[int] = utils.get_int(data, "public_updates_channel_id")
        self.region: Optional[str] = data.get("region", None)
        self.safety_alerts_channel_id: Optional[int] = utils.get_int(data, "safety_alerts_channel_id")
        self.system_channel_flags: int = data.get("system_channel_flags", 0)
        self.system_channel_id: Optional[int] = utils.get_int(data, "system_channel_id")
        self.vanity_url_code: Optional[str] = data.get("vanity_url_code", None)
        self.verification_level: VerificationLevel = VerificationLevel(data.get("verification_level", 0))
        self.widget_channel_id: Optional[int] = utils.get_int(data, "widget_channel_id")
        self.widget_enabled: bool = data.get("widget_enabled", False)

    @property
    def emojis_limit(self) -> int:
        """ `int`: The maximum amount of emojis the guild can have """
        return max(
            200 if "MORE_EMOJI" in self.features else 50,
            self._GUILD_LIMITS[self.premium_tier].emojis
        )

    @property
    def stickers_limit(self) -> int:
        """ `int`: The maximum amount of stickers the guild can have """
        return max(
            60 if "MORE_STICKERS" in self.features else 0,
            self._GUILD_LIMITS[self.premium_tier].stickers
        )

    @property
    def bitrate_limit(self) -> int:
        """ `float`: The maximum bitrate the guild can have """
        return max(
            self._GUILD_LIMITS[1].bitrate if "VIP_REGIONS" in self.features else 96_000,
            self._GUILD_LIMITS[self.premium_tier].bitrate
        )

    @property
    def filesize_limit(self) -> int:
        """ `int`: The maximum filesize the guild can have """
        return self._GUILD_LIMITS[self.premium_tier].filesize

    @property
    def icon(self) -> Optional[Asset]:
        """ `Optional[Asset]`: The guild's icon """
        if self._icon is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._icon, path="icons")

    @property
    def banner(self) -> Optional[Asset]:
        """ `Optional[Asset]`: The guild's banner """
        if self._banner is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._banner, path="banners")

    @property
    def default_role(self) -> Role:
        """ `Role`: The guild's default role, which is always provided """
        role = self.get_role(self.id)
        if not role:
            raise ValueError("The default Guild role was somehow not found...?")
        return role

    @property
    def premium_subscriber_role(self) -> Optional[Role]:
        """ `Optional[Role]`: The guild's premium subscriber role if available """
        return next(
            (r for r in self.roles if isinstance(r, Role) and r.is_premium_subscriber()),
            None
        )

    @property
    def self_role(self) -> Optional[Role]:
        """ `Optional[Role]`: The guild's bot role if available """
        return next(
            (
                r for r in self.roles
                if isinstance(r, Role) and
                r.bot_id and
                r.bot_id == self._state.application_id
            ),
            None
        )

    def get_role(self, role_id: int) -> Optional[Role]:
        """
        Get a role from the guild

        This simply returns the role from the role list in this object if it exists

        Parameters
        ----------
        role_id: `int`
            The ID of the role to get

        Returns
        -------
        `Optional[Role]`
            The role if it exists, else `None`
        """
        return next((
            r for r in self.roles
            if isinstance(r, Role) and
            r.id == role_id
        ), None)

    def get_role_by_name(self, role_name: str) -> Optional[Role]:
        """
        Gets the first role with the specified name

        Parameters
        ----------
        role_name: `str`
            The name of the role to get (case sensitive)

        Returns
        -------
        `Optional[Role]`
            The role if it exists, else `None`
        """
        return next((
            r for r in self.roles
            if isinstance(r, Role) and
            r.name == role_name
        ), None)

    @property
    def me(self) -> "Member | PartialMember | None":
        """
        `Optional[Member]`: Returns the bot's member object.
        Only useable if you are using gateway and caching
        """
        return self.get_member(self._state.bot.user.id)

    def get_member_top_role(self, member: "Member") -> Optional[Role]:
        """
        Get the top role of a member, because Discord API does not order roles

        Parameters
        ----------
        member: `Member`
            The member to get the top role of

        Returns
        -------
        `Optional[Role]`
            The top role of the member
        """
        if not getattr(member, "roles", None):
            return None

        _roles_sorted = sorted(
            [r for r in self.roles if isinstance(r, Role)],
            key=lambda r: r.position,
            reverse=True
        )

        return next((
            r for r in _roles_sorted
            if r.id in member.roles
        ), None)
