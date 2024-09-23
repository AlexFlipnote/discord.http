from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Union, Optional, AsyncIterator

from . import utils
from .asset import Asset
from .colour import Colour, Color
from .enums import (
    ChannelType, VerificationLevel,
    DefaultNotificationLevel, ContentFilterLevel,
    ScheduledEventEntityType, ScheduledEventPrivacyType,
    ScheduledEventStatusType, VideoQualityType
)
from .emoji import Emoji, PartialEmoji
from .file import File
from .flag import Permissions, SystemChannelFlags, PermissionOverwrite
from .multipart import MultipartData
from .object import PartialBase, Snowflake
from .role import Role, PartialRole
from .sticker import Sticker, PartialSticker

if TYPE_CHECKING:
    from .channel import (
        TextChannel, VoiceChannel,
        PartialChannel, BaseChannel,
        CategoryChannel, PublicThread,
        VoiceRegion, StageChannel
    )
    from .http import DiscordAPI
    from .invite import Invite
    from .member import PartialMember, Member, VoiceState
    from .user import User

MISSING = utils.MISSING

__all__ = (
    "Guild",
    "PartialGuild",
    "PartialScheduledEvent",
    "ScheduledEvent",
)


@dataclass
class _GuildLimits:
    bitrate: int
    emojis: int
    filesize: int
    soundboards: int
    stickers: int


class PartialScheduledEvent(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        guild_id: int
    ):
        super().__init__(id=int(id))
        self.guild_id: int = guild_id

        self._state = state

    def __repr__(self) -> str:
        return f"<PartialScheduledEvent id={self.id}>"

    @property
    def guild(self) -> "PartialGuild":
        """ `PartialGuild`: The guild object this event is in """
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

    async def delete(self) -> None:
        """ Delete the event (the bot must own the event) """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild_id}/scheduled-events/{self.id}",
            res_method="text"
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        channel: Optional[Union["PartialChannel", int]] = MISSING,
        external_location: Optional[str] = MISSING,
        privacy_level: Optional[ScheduledEventPrivacyType] = MISSING,
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
        privacy_level: `Optional[ScheduledEventPrivacyType]`
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
                ScheduledEventPrivacyType.guild_only
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

        self.privacy_level: ScheduledEventPrivacyType = ScheduledEventPrivacyType(data["privacy_level"])
        self.status: ScheduledEventStatusType = ScheduledEventStatusType(data["status"])
        self.entity_type: ScheduledEventEntityType = ScheduledEventEntityType(data["entity_type"])

        self.channel: Optional[PartialChannel] = None
        self.creator: Optional["User"] = None

        self.start_time: datetime = utils.parse_time(data["scheduled_start_time"])
        self.end_time: Optional[datetime] = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ScheduledEvent id={self.id} name='{self.name}'>"

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

    def __repr__(self) -> str:
        return f"<PartialGuild id={self.id}>"

    @property
    def default_role(self) -> PartialRole:
        """ `Role`: Returns the default role, but as a partial role object """
        return PartialRole(
            state=self._state,
            id=self.id,
            guild_id=self.id
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

    async def create_guild(
        self,
        name: str,
        *,
        icon: Optional[Union[File, bytes]] = None,
        reason: Optional[str] = None
    ) -> "Guild":
        """
        Create a guild

        Note that the bot must be in less than 10 guilds to use this endpoint

        Parameters
        ----------
        name: `str`
            The name of the guild
        icon: `Optional[File]`
            The icon of the guild
        reason: `Optional[str]`
            The reason for creating the guild

        Returns
        -------
        `Guild`
            The created guild
        """
        payload = {"name": name}

        if icon is not None:
            payload["icon"] = utils.bytes_to_base64(icon)

        r = await self._state.query(
            "POST",
            "/guilds",
            json=payload,
            reason=reason
        )

        return Guild(
            state=self._state,
            data=r.response
        )

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
        privacy_level: Optional[ScheduledEventPrivacyType] = None,
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
        privacy_level: `Optional[ScheduledEventPrivacyType]`
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
                ScheduledEventPrivacyType.guild_only
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

    async def ban(
        self,
        member: Union["Member", "PartialMember", int],
        *,
        reason: Optional[str] = None,
        delete_message_days: Optional[int] = 0,
        delete_message_seconds: Optional[int] = 0,
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
        if isinstance(member, int):
            from .member import PartialMember
            member = PartialMember(state=self._state, id=member, guild_id=self.id)

        await member.ban(
            reason=reason,
            delete_message_days=delete_message_days,
            delete_message_seconds=delete_message_seconds
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
        if isinstance(member, int):
            from .member import PartialMember
            member = PartialMember(state=self._state, id=member, guild_id=self.id)

        await member.unban(reason=reason)

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
        if isinstance(member, int):
            from .member import PartialMember
            member = PartialMember(state=self._state, id=member, guild_id=self.id)

        await member.kick(reason=reason)

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

    async def fetch_voice_state(self, member: Snowflake) -> "VoiceState":
        """
        Fetches the voice state of the member

        Parameters
        ----------
        member: `Snowflake`
            The member to fetch the voice state from

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
        r = await self._state.query(
            "GET",
            f"/guilds/{self.id}/voice-states/{int(member)}"
        )

        from .member import VoiceState
        return VoiceState(state=self._state, data=r.response)

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

    async def delete(self) -> None:
        """ Delete the guild (the bot must own the server) """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.id}"
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
        self.emojis: list[Emoji] = [
            Emoji(state=self._state, guild=self, data=e)
            for e in data.get("emojis", [])
        ]
        self.stickers: list[Sticker] = [
            Sticker(state=self._state, guild=self, data=s)
            for s in data.get("stickers", [])
        ]

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
        self.roles: list[Role] = [
            Role(state=self._state, guild=self, data=r)
            for r in data.get("roles", [])
        ]
        self.safety_alerts_channel_id: Optional[int] = utils.get_int(data, "safety_alerts_channel_id")
        self.system_channel_flags: int = data.get("system_channel_flags", 0)
        self.system_channel_id: Optional[int] = utils.get_int(data, "system_channel_id")
        self.vanity_url_code: Optional[str] = data.get("vanity_url_code", None)
        self.verification_level: int = data.get("verification_level", 0)
        self.widget_channel_id: Optional[int] = utils.get_int(data, "widget_channel_id")
        self.widget_enabled: bool = data.get("widget_enabled", False)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Guild id={self.id} name='{self.name}'>"

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
        return Asset._from_guild_icon(self._state, self.id, self._icon)

    @property
    def banner(self) -> Optional[Asset]:
        """ `Optional[Asset]`: The guild's banner """
        if self._banner is None:
            return None
        return Asset._from_guild_banner(self._state, self.id, self._banner)

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
            (r for r in self.roles if r.is_premium_subscriber()),
            None
        )

    @property
    def self_role(self) -> Optional[Role]:
        """ `Optional[Role]`: The guild's bot role if available """
        return next(
            (
                r for r in self.roles
                if r.bot_id and
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
            if r.id == role_id
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
            if r.name == role_name
        ), None)

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
            self.roles,
            key=lambda r: r.position,
            reverse=True
        )

        return next((
            r for r in _roles_sorted
            if r.id in member.roles
        ), None)
