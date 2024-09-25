from datetime import datetime, timedelta
from typing import Union, TYPE_CHECKING, Optional, AsyncIterator, Callable, Self

from . import utils
from .embeds import Embed
from .emoji import EmojiParser
from .enums import (
    ChannelType, ResponseType, VideoQualityType,
    SortOrderType, ForumLayoutType
)
from .file import File
from .flags import PermissionOverwrite, ChannelFlags
from .member import ThreadMember
from .mentions import AllowedMentions
from .multipart import MultipartData
from .object import PartialBase, Snowflake
from .response import MessageResponse
from .view import View
from .webhook import Webhook

if TYPE_CHECKING:
    from .guild import PartialGuild
    from .http import DiscordAPI
    from .invite import Invite
    from .message import PartialMessage, Message, Poll
    from .user import PartialUser, User

MISSING = utils.MISSING

__all__ = (
    "BaseChannel",
    "CategoryChannel",
    "DMChannel",
    "DirectoryChannel",
    "ForumChannel",
    "ForumTag",
    "ForumThread",
    "GroupDMChannel",
    "NewsChannel",
    "NewsThread",
    "PartialChannel",
    "PrivateThread",
    "PublicThread",
    "StageChannel",
    "StoreChannel",
    "TextChannel",
    "Thread",
    "VoiceChannel",
    "VoiceRegion",
)


class PartialChannel(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        guild_id: Optional[int] = None
    ):
        super().__init__(id=int(id))
        self._state = state
        self.guild_id: Optional[int] = guild_id

        self._raw_type: ChannelType = ChannelType.unknown

    def __repr__(self) -> str:
        return f"<PartialChannel id={self.id}>"

    @property
    def guild(self) -> Optional["PartialGuild"]:
        """ `Optional[PartialGuild]`: The guild the channel belongs to (if available) """
        from .guild import PartialGuild

        if not self.guild_id:
            return None
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return self._raw_type

    def get_partial_message(self, message_id: int) -> "PartialMessage":
        """
        Get a partial message object from the channel

        Parameters
        ----------
        message_id: `int`
            The message ID to get the partial message from

        Returns
        -------
        `PartialMessage`
            The partial message object
        """
        from .message import PartialMessage
        return PartialMessage(
            state=self._state,
            channel_id=self.id,
            id=message_id
        )

    async def fetch_message(self, message_id: int) -> "Message":
        """
        Fetch a message from the channel

        Parameters
        ----------
        message_id: `int`
            The message ID to fetch

        Returns
        -------
        `Message`
            The message object
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/messages/{message_id}"
        )

        from .message import Message
        return Message(
            state=self._state,
            data=r.response,
            guild=self.guild
        )

    async def fetch_pins(self) -> list["Message"]:
        """
        Fetch all pinned messages for the channel in question

        Returns
        -------
        `list[Message]`
            The list of pinned messages
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/pins"
        )

        from .message import Message
        return [
            Message(
                state=self._state,
                data=data,
                guild=self.guild
            )
            for data in r.response
        ]

    async def follow_announcement_channel(
        self,
        source_channel_id: Union[Snowflake, int]
    ) -> None:
        """
        Follow an announcement channel to send messages to the webhook

        Parameters
        ----------
        source_channel_id: `int`
            The channel ID to follow
        """
        await self._state.query(
            "POST",
            f"/channels/{source_channel_id}/followers",
            json={"webhook_channel_id": self.id},
            res_method="text"
        )

    async def fetch_archived_public_threads(self) -> list["PublicThread"]:
        """
        Fetch all archived public threads

        Returns
        -------
        `list[PublicThread]`
            The list of public threads
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/threads/archived/public"
        )

        from .channel import PublicThread
        return [
            PublicThread(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    async def fetch_archived_private_threads(
        self,
        *,
        client: bool = False
    ) -> list["PrivateThread"]:
        """
        Fetch all archived private threads

        Parameters
        ----------
        client: `bool`
            If it should fetch only where the client is a member of the thread

        Returns
        -------
        `list[PrivateThread]`
            The list of private threads
        """
        path = f"/channels/{self.id}/threads/archived/private"
        if client:
            path = f"/channels/{self.id}/users/@me/threads/archived/private"

        r = await self._state.query("GET", path)

        from .channel import PrivateThread
        return [
            PrivateThread(
                state=self._state,
                data=data
            )
            for data in r.response
        ]

    async def create_invite(
        self,
        *,
        max_age: Union[timedelta, int] = 86400,  # 24 hours
        max_uses: Optional[int] = 0,
        temporary: bool = False,
        unique: bool = False,
    ) -> "Invite":
        """
        Create an invite for the channel

        Parameters
        ----------
        max_age: `Union[timedelta, int]`
            How long the invite should last
        temporary: `bool`
            If the invite should be temporary
        unique: `bool`
            If the invite should be unique

        Returns
        -------
        `Invite`
            The invite object
        """
        if isinstance(max_age, timedelta):
            max_age = int(max_age.total_seconds())

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/invites",
            json={
                "max_age": max_age,
                "max_uses": max_uses,
                "temporary": temporary,
                "unique": unique
            }
        )

        from .invite import Invite
        return Invite(
            state=self._state,
            data=r.response
        )

    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        type: Union[ResponseType, int] = 4,
        poll: Optional["Poll"] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
    ) -> "Message":
        """
        Send a message to the channel

        Parameters
        ----------
        content: `Optional[str]`
            Cotnent of the message
        embed: `Optional[Embed]`
            Includes an embed object
        embeds: `Optional[list[Embed]]`
            List of embed objects
        file: `Optional[File]`
            A file object
        files: `Union[list[File], File]`
            A list of file objects
        view: `View`
            Send components to the message
        tts: `bool`
            If the message should be sent as a TTS message
        type: `Optional[ResponseType]`
            The type of response to the message
        allowed_mentions: `Optional[AllowedMentions]`
            The allowed mentions for the message
        poll: `Optional[Poll]`
            The poll to be sent

        Returns
        -------
        `Message`
            The message object
        """
        payload = MessageResponse(
            content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            view=view,
            tts=tts,
            type=type,
            poll=poll,
            allowed_mentions=allowed_mentions,
        )

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        from .message import Message
        return Message(
            state=self._state,
            data=r.response
        )

    def _class_to_return(
        self,
        data: dict,
        *,
        state: Optional["DiscordAPI"] = None
    ) -> "BaseChannel":
        match data["type"]:
            case x if x in (ChannelType.guild_text, ChannelType.guild_news):
                _class = TextChannel

            case ChannelType.guild_voice:
                _class = VoiceChannel

            case ChannelType.guild_category:
                _class = CategoryChannel

            case ChannelType.guild_news_thread:
                _class = NewsThread

            case ChannelType.guild_public_thread:
                _class = PublicThread

            case ChannelType.guild_private_thread:
                _class = PrivateThread

            case ChannelType.guild_stage_voice:
                _class = StageChannel

            case ChannelType.guild_forum:
                _class = ForumChannel

            case _:
                _class = BaseChannel

        _class: type["BaseChannel"]

        return _class(
            state=state or self._state,
            data=data
        )

    @classmethod
    def from_dict(cls, *, state: "DiscordAPI", data: dict) -> Self:
        """
        Create a channel object from a dictionary
        Requires the state to be set

        Parameters
        ----------
        state: `DiscordAPI`
            The state to use
        data: `dict`
            Data provided by Discord API

        Returns
        -------
        `BaseChannel`
            The channel object
        """
        temp_class = cls(
            state=state,
            id=int(data["id"]),
            guild_id=utils.get_int(data, "guild_id")
        )

        return temp_class._class_to_return(data=data, state=state)  # type: ignore

    async def fetch(self) -> "BaseChannel":
        """ `BaseChannel`: Fetches the channel and returns the channel object """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}"
        )

        return self._class_to_return(
            data=r.response
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        type: Optional[Union[ChannelType, int]] = MISSING,
        position: Optional[int] = MISSING,
        topic: Optional[str] = MISSING,
        nsfw: Optional[bool] = MISSING,
        rate_limit_per_user: Optional[int] = MISSING,
        bitrate: Optional[int] = MISSING,
        user_limit: Optional[int] = MISSING,
        overwrites: Optional[list[PermissionOverwrite]] = MISSING,
        parent_id: Optional[Union[Snowflake, int]] = MISSING,
        rtc_region: Optional[str] = MISSING,
        video_quality_mode: Optional[Union[VideoQualityType, int]] = MISSING,
        default_auto_archive_duration: Optional[int] = MISSING,
        flags: Optional[ChannelFlags] = MISSING,
        available_tags: Optional[list["ForumTag"]] = MISSING,
        default_reaction_emoji: Optional[str] = MISSING,
        default_thread_rate_limit_per_user: Optional[int] = MISSING,
        default_sort_order: Optional[Union[SortOrderType, int]] = MISSING,
        default_forum_layout: Optional[Union[ForumLayoutType, int]] = MISSING,
        archived: Optional[bool] = MISSING,
        auto_archive_duration: Optional[int] = MISSING,
        locked: Optional[bool] = MISSING,
        invitable: Optional[bool] = MISSING,
        applied_tags: Optional[list[Union["ForumTag", int]]] = MISSING,
        reason: Optional[str] = None,
    ) -> Self:
        """
        Edit the channel

        Note that this method globaly edits any channel type.
        So be sure to use the correct parameters for the channel.

        Parameters
        ----------
        name: `Optional[str]`
            New name of the channel (All)
        type: `Optional[Union[ChannelType, int]]`
            The new type of the channel (Text, Announcement)
        position: `Optional[int]`
            The new position of the channel (All)
        topic: `Optional[str]`
            The new topic of the channel (Text, Announcement, Forum, Media)
        nsfw: `Optional[bool]`
            If the channel should be NSFW (Text, Voice, Announcement, Stage, Forum, Media)
        rate_limit_per_user: `Optional[int]`
            How long the slowdown should be (Text, Voice, Stage, Forum, Media)
        bitrate: `Optional[int]`
            The new bitrate of the channel (Voice, Stage)
        user_limit: `Optional[int]`
            The new user limit of the channel (Voice, Stage)
        overwrites: `Optional[list[PermissionOverwrite]]`
            The new permission overwrites of the channel (All)
        parent_id: `Optional[Union[Snowflake, int]]`
            The new parent ID of the channel (Text, Voice, Announcement, Stage, Forum, Media)
        rtc_region: `Optional[str]`
            The new RTC region of the channel (Voice, Stage)
        video_quality_mode: `Optional[Union[VideoQualityType, int]]`
            The new video quality mode of the channel (Voice, Stage)
        default_auto_archive_duration: `Optional[int]`
            The new default auto archive duration of the channel (Text, Announcement, Forum, Media)
        flags: `Optional[ChannelFlags]`
            The new flags of the channel (Forum, Media)
        available_tags: `Optional[list[ForumTag]]`
            The new available tags of the channel (Forum, Media)
        default_reaction_emoji: `Optional[str]`
            The new default reaction emoji of the channel (Forum, Media)
        default_thread_rate_limit_per_user: `Optional[int]`
            The new default thread rate limit per user of the channel (Text, Forum, Media)
        default_sort_order: `Optional[Union[SortOrderType, int]]`
            The new default sort order of the channel (Forum, Media)
        default_forum_layout: `Optional[Union[ForumLayoutType, int]]`
            The new default forum layout of the channel (Forum)
        archived: `Optional[bool]`
            If the thread should be archived (Thread, Forum)
        auto_archive_duration: `Optional[int]`
            The new auto archive duration of the thread (Thread, Forum)
        locked: `Optional[bool]`
            If the thread should be locked (Thread, Forum)
        invitable: `Optional[bool]`
            If the thread should be invitable by everyone (Thread)
        applied_tags: `Optional[list[Union[ForumTag, int]]`
            The new applied tags of the forum thread (Forum, Media)
        reason: `Optional[str]`
            The reason for editing the channel (All)

        Returns
        -------
        `BaseChannel`
            The channel object
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = str(name)

        if type is not MISSING:
            payload["type"] = int(type or 0)

        if position is not MISSING:
            payload["position"] = int(position or 0)

        if topic is not MISSING:
            payload["topic"] = topic

        if nsfw is not MISSING:
            payload["nsfw"] = bool(nsfw)

        if rate_limit_per_user is not MISSING:
            payload["rate_limit_per_user"] = int(
                rate_limit_per_user or 0
            )

        if bitrate is not MISSING:
            payload["bitrate"] = int(bitrate or 64000)

        if user_limit is not MISSING:
            payload["user_limit"] = int(user_limit or 0)

        if overwrites is not MISSING:
            if overwrites is None:
                payload["permission_overwrites"] = []
            else:
                payload["permission_overwrites"] = [
                    g.to_dict() for g in overwrites
                    if isinstance(g, PermissionOverwrite)
                ]

        if parent_id is not MISSING:
            if parent_id is None:
                payload["parent_id"] = None
            else:
                payload["parent_id"] = str(int(parent_id))

        if rtc_region is not MISSING:
            payload["rtc_region"] = rtc_region

        if video_quality_mode is not MISSING:
            payload["video_quality_mode"] = int(
                video_quality_mode or 1
            )

        if default_auto_archive_duration is not MISSING:
            payload["default_auto_archive_duration"] = int(
                default_auto_archive_duration or 4320
            )

        if flags is not MISSING:
            payload["flags"] = int(flags or 0)

        if available_tags is not MISSING:
            if available_tags is None:
                payload["available_tags"] = []
            else:
                payload["available_tags"] = [
                    g.to_dict() for g in available_tags
                    if isinstance(g, ForumTag)
                ]

        if default_reaction_emoji is not MISSING:
            if default_reaction_emoji is None:
                payload["default_reaction_emoji"] = None
            else:
                _emoji = EmojiParser(default_reaction_emoji)
                payload["default_reaction_emoji"] = _emoji.to_forum_dict()

        if default_thread_rate_limit_per_user is not MISSING:
            payload["default_thread_rate_limit_per_user"] = int(
                default_thread_rate_limit_per_user or 0
            )

        if default_sort_order is not MISSING:
            payload["default_sort_order"] = int(
                default_sort_order or 0
            )

        if default_forum_layout is not MISSING:
            payload["default_forum_layout"] = int(
                default_forum_layout or 0
            )

        if archived is not MISSING:
            payload["archived"] = bool(archived)

        if auto_archive_duration is not MISSING:
            payload["auto_archive_duration"] = int(
                auto_archive_duration or 4320
            )

        if locked is not MISSING:
            payload["locked"] = bool(locked)

        if invitable is not MISSING:
            payload["invitable"] = bool(invitable)

        if applied_tags is not MISSING:
            if applied_tags is None:
                payload["applied_tags"] = []
            else:
                payload["applied_tags"] = [
                    str(int(g))
                    for g in applied_tags
                ]

        r = await self._state.query(
            "PATCH",
            f"/channels/{self.id}",
            json=payload,
            reason=reason
        )

        return self._class_to_return(data=r.response)  # type: ignore

    async def typing(self) -> None:
        """
        Makes the bot trigger the typing indicator.
        Times out after 10 seconds
        """
        await self._state.query(
            "POST",
            f"/channels/{self.id}/typing",
            res_method="text"
        )

    async def set_permission(
        self,
        id: Union[Snowflake, int],
        *,
        overwrite: PermissionOverwrite,
        reason: Optional[str] = None
    ) -> None:
        """
        Set a permission overwrite for the channel

        Parameters
        ----------
        id: `Union[Snowflake, int]`
            The ID of the overwrite
        overwrite: `PermissionOverwrite`
            The new overwrite permissions
        reason: `Optional[str]`
            The reason for editing the overwrite
        """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/permissions/{int(id)}",
            json=overwrite.to_dict(),
            res_method="text",
            reason=reason
        )

    async def delete_permission(
        self,
        id: Union[Snowflake, int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Delete a permission overwrite for the channel

        Parameters
        ----------
        id: `Union[Snowflake, int]`
            The ID of the overwrite
        reason: `Optional[str]`
            The reason for deleting the overwrite
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}/permissions/{int(id)}",
            res_method="text",
            reason=reason
        )

    async def delete(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Delete the channel

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for deleting the channel
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def delete_messages(
        self,
        message_ids: list[int],
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        _summary_

        Parameters
        ----------
        message_ids: `list[int]`
            List of message IDs to delete
        reason: `Optional[str]`
            The reason of why you are deleting them (appears in audit log)

        Raises
        ------
        `ValueError`
            If you provide >100 IDs to delete
        """
        if len(message_ids) <= 0:
            return None

        if len(message_ids) == 1:
            msg = self.get_partial_message(message_ids[0])
            return await msg.delete(reason=reason)
        if len(message_ids) > 100:
            raise ValueError("message_ids must be less than or equal to 100")

        await self._state.query(
            "POST",
            f"/channels/{self.id}/messages/bulk-delete",
            json={"messages": message_ids},
            reason=reason,
            res_method="text"
        )

    async def create_webhook(
        self,
        name: str,
        *,
        avatar: Optional[Union[File, bytes]] = None,
        reason: Optional[str] = None
    ) -> Webhook:
        """
        Create a webhook for the channel

        Parameters
        ----------
        name: `str`
            The name of the webhook
        avatar: `Optional[File]`
            The avatar of the webhook
        reason: `Optional[str]`
            The reason for creating the webhook that appears in audit logs

        Returns
        -------
        `Webhook`
            The webhook object
        """
        payload = {"name": name}

        if avatar is not None:
            payload["avatar"] = utils.bytes_to_base64(avatar)

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/webhooks",
            json=payload,
            reason=reason,
        )

        return Webhook(state=self._state, data=r.response)

    async def create_forum_or_media(
        self,
        name: str,
        *,
        content: Optional[str] = None,
        embed: Optional[Embed] = None,
        embeds: Optional[list[Embed]] = None,
        file: Optional[File] = None,
        files: Optional[list[File]] = None,
        allowed_mentions: Optional[AllowedMentions] = None,
        view: Optional[View] = None,
        auto_archive_duration: Optional[int] = 4320,
        rate_limit_per_user: Optional[int] = None,
        applied_tags: Optional[list[Union["ForumTag", int]]] = None
    ) -> "ForumThread":
        """
        Create a forum or media thread in the channel

        Parameters
        ----------
        name: `str`
            The name of the thread
        content: `Optional[str]`
            The content of the message
        embed: `Optional[Embed]`
            Embed to be sent
        embeds: `Optional[list[Embed]]`
            List of embeds to be sent
        file: `Optional[File]`
            File to be sent
        files: `Optional[list[File]]`
            List of files to be sent
        allowed_mentions: `Optional[AllowedMentions]`
            The allowed mentions for the message
        view: `Optional[View]`
            The view to be sent
        auto_archive_duration: `Optional[int]`
            The duration in minutes to automatically archive the thread after recent activity
        rate_limit_per_user: `Optional[int]`
            How long the slowdown should be
        applied_tags: `Optional[list[Union[&quot;ForumTag&quot;, int]]]`
            The tags to be applied to the thread

        Returns
        -------
        `ForumThread`
            _description_
        """
        payload = {
            "name": name,
            "message": {}
        }

        if auto_archive_duration in (60, 1440, 4320, 10080):
            payload["auto_archive_duration"] = auto_archive_duration

        if rate_limit_per_user is not None:
            payload["rate_limit_per_user"] = int(rate_limit_per_user)

        if applied_tags is not None:
            payload["applied_tags"] = [
                str(int(g)) for g in applied_tags
            ]

        temp_msg = MessageResponse(
            embeds=embeds or ([embed] if embed else None),
            files=files or ([file] if file else None),
        )

        if content is not None:
            payload["message"]["content"] = str(content)

        if allowed_mentions is not None:
            payload["message"]["allowed_mentions"] = allowed_mentions.to_dict()

        if view is not None:
            payload["message"]["components"] = view.to_dict()

        if temp_msg.embeds is not None:
            payload["message"]["embeds"] = [
                e.to_dict() for e in temp_msg.embeds
            ]

        if temp_msg.files is not None:
            multidata = MultipartData()

            for i, file in enumerate(temp_msg.files):
                multidata.attach(
                    f"files[{i}]",
                    file,  # type: ignore
                    filename=file.filename
                )

            multidata.attach("payload_json", payload)

            r = await self._state.query(
                "POST",
                f"/channels/{self.id}/threads",
                headers={"Content-Type": multidata.content_type},
                data=multidata.finish(),
            )
        else:
            r = await self._state.query(
                "POST",
                f"/channels/{self.id}/threads",
                json=payload
            )

        return ForumThread(
            state=self._state,
            data=r.response
        )

    async def create_thread(
        self,
        name: str,
        *,
        type: Union[ChannelType, int] = ChannelType.guild_private_thread,
        auto_archive_duration: Optional[int] = 4320,
        invitable: bool = True,
        rate_limit_per_user: Optional[Union[timedelta, int]] = None,
        reason: Optional[str] = None
    ) -> Union["PublicThread", "PrivateThread", "NewsThread"]:
        """
        Creates a thread in the channel

        Parameters
        ----------
        name: `str`
            The name of the thread
        type: `Optional[Union[ChannelType, int]]`
            The type of thread to create
        auto_archive_duration: `Optional[int]`
            The duration in minutes to automatically archive the thread after recent activity
        invitable: `bool`
            If the thread is invitable
        rate_limit_per_user: `Optional[Union[timedelta, int]]`
            How long the slowdown should be
        reason: `Optional[str]`
            The reason for creating the thread

        Returns
        -------
        `Union[PublicThread, PrivateThread, NewsThread]`
            The thread object

        Raises
        ------
        `ValueError`
            - If the auto_archive_duration is not 60, 1440, 4320 or 10080
            - If the rate_limit_per_user is not between 0 and 21600 seconds
        """
        payload = {
            "name": name,
            "type": int(type),
            "invitable": invitable,
        }

        if auto_archive_duration not in (60, 1440, 4320, 10080):
            raise ValueError("auto_archive_duration must be 60, 1440, 4320 or 10080")

        if rate_limit_per_user is not None:
            if isinstance(rate_limit_per_user, timedelta):
                rate_limit_per_user = int(rate_limit_per_user.total_seconds())

            if rate_limit_per_user not in range(0, 21601):
                raise ValueError("rate_limit_per_user must be between 0 and 21600 seconds")

            payload["rate_limit_per_user"] = rate_limit_per_user

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/threads",
            json=payload,
            reason=reason
        )

        match r.response["type"]:
            case ChannelType.guild_public_thread:
                _class = PublicThread

            case ChannelType.guild_private_thread:
                _class = PrivateThread

            case ChannelType.guild_news_thread:
                _class = NewsThread

            case _:
                raise ValueError("Invalid thread type")

        return _class(
            state=self._state,
            data=r.response
        )

    async def fetch_history(
        self,
        *,
        before: Optional[Union[datetime, "Message", Snowflake, int]] = None,
        after: Optional[Union[datetime, "Message", Snowflake, int]] = None,
        around: Optional[Union[datetime, "Message", Snowflake, int]] = None,
        limit: Optional[int] = 100,
    ) -> AsyncIterator["Message"]:
        """
        Fetch the channel's message history

        Parameters
        ----------
        before: `Optional[Union[datetime, Message, Snowflake, int]]`
            Get messages before this message
        after: `Optional[Union[datetime, Message, Snowflake, int]]`
            Get messages after this message
        around: `Optional[Union[datetime, Message, Snowflake, int]]`
            Get messages around this message
        limit: `Optional[int]`
            The maximum amount of messages to fetch.
            `None` will fetch all users.

        Yields
        ------
        `Message`
            The message object
        """
        def _resolve_id(entry) -> int:
            match entry:
                case x if isinstance(x, Snowflake):
                    return int(x)

                case x if isinstance(x, int):
                    return x

                case x if isinstance(x, str):
                    if not x.isdigit():
                        raise TypeError("Got a string that was not a Snowflake ID for before/after/around")
                    return int(x)

                case x if isinstance(x, datetime):
                    return utils.time_snowflake(x)

                case _:
                    raise TypeError("Got an unknown type for before/after/around")

        async def _get_history(limit: int, **kwargs):
            params = {"limit": limit}
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = _resolve_id(value)

            return await self._state.query(
                "GET",
                f"/channels/{self.id}/messages",
                params=params
            )

        async def _around_http(
            http_limit: int,
            around_id: Optional[int],
            limit: Optional[int]
        ):
            r = await _get_history(limit=http_limit, around=around_id)
            return r.response, None, limit

        async def _after_http(
            http_limit: int,
            after_id: Optional[int],
            limit: Optional[int]
        ):
            r = await _get_history(limit=http_limit, after=after_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                after_id = int(r.response[0]["id"])

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
                before_id = int(r.response[-1]["id"])

            return r.response, before_id, limit

        if around:
            if limit is None:
                raise ValueError("limit must be specified when using around")
            if limit > 100:
                raise ValueError("limit must be less than or equal to 100 when using around")

            strategy, state = _around_http, _resolve_id(around)
        elif after:
            strategy, state = _after_http, _resolve_id(after)
        elif before:
            strategy, state = _before_http, _resolve_id(before)
        else:
            strategy, state = _before_http, None

        # Must be imported here to avoid circular import
        # From the top of the file
        from .message import Message

        while True:
            http_limit: int = 100 if limit is None else min(limit, 100)
            if http_limit <= 0:
                break

            strategy: Callable
            messages, state, limit = await strategy(http_limit, state, limit)

            i = 0
            for i, msg in enumerate(messages, start=1):
                yield Message(
                    state=self._state,
                    data=msg,
                    guild=self.guild
                )

            if i < 100:
                break

    async def join_thread(self) -> None:
        """ Make the bot join a thread """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/thread-members/@me",
            res_method="text"
        )

    async def leave_thread(self) -> None:
        """ Make the bot leave a thread """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}/thread-members/@me",
            res_method="text"
        )

    async def add_thread_member(
        self,
        user_id: int
    ) -> None:
        """
        Add a thread member

        Parameters
        ----------
        user_id: `int`
            The user ID to add
        """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/thread-members/{user_id}",
            res_method="text"
        )

    async def remove_thread_member(
        self,
        user_id: int
    ) -> None:
        """
        Remove a thread member

        Parameters
        ----------
        user_id: `int`
            The user ID to remove
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}/thread-members/{user_id}",
            res_method="text"
        )

    async def fetch_thread_member(
        self,
        user_id: int
    ) -> ThreadMember:
        """
        Fetch a thread member

        Parameters
        ----------
        user_id: `int`
            The user ID to fetch

        Returns
        -------
        `ThreadMember`
            The thread member object
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/thread-members/{user_id}",
            params={"with_member": "true"}
        )

        return ThreadMember(
            state=self._state,
            data=r.response,
        )

    async def fetch_thread_members(self) -> list[ThreadMember]:
        """
        Fetch all thread members

        Returns
        -------
        `list[ThreadMember]`
            The list of thread members
        """
        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/thread-members",
            params={"with_member": "true"},
        )

        return [
            ThreadMember(
                state=self._state,
                data=data
            )
            for data in r.response
        ]


class BaseChannel(PartialChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(
            state=state,
            id=int(data["id"]),
            guild_id=utils.get_int(data, "guild_id")
        )

        self.id: int = int(data["id"])
        self.name: Optional[str] = data.get("name", None)
        self.nsfw: bool = data.get("nsfw", False)
        self.topic: Optional[str] = data.get("topic", None)
        self.position: Optional[int] = utils.get_int(data, "position")
        self.last_message_id: Optional[int] = utils.get_int(data, "last_message_id")
        self.parent_id: Optional[int] = utils.get_int(data, "parent_id")

        self._raw_type: ChannelType = ChannelType(data["type"])

        self.permission_overwrites: list[PermissionOverwrite] = [
            PermissionOverwrite.from_dict(g)
            for g in data.get("permission_overwrites", [])
        ]

    def __repr__(self) -> str:
        return f"<Channel id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name or ""

    @property
    def mention(self) -> str:
        """ `str`: The channel's mention """
        return f"<#{self.id}>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_text

    @classmethod
    def from_dict(cls, *, state: "DiscordAPI", data: dict) -> "BaseChannel":
        """
        Create a channel object from a dictionary
        Requires the state to be set

        Parameters
        ----------
        state: `DiscordAPI`
            The state to use
        data: `dict`
            Data provided by Discord API

        Returns
        -------
        `BaseChannel`
            The channel object
        """
        _class = cls(state=state, data=data)._class_to_return(
            data=data,
            state=state,
        )

        return _class


class TextChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<TextChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        if self._raw_type == 0:
            return ChannelType.guild_text
        return ChannelType.guild_news


class DMChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

        self.name: Optional[str] = None
        self.user: Optional["User"] = None
        self.last_message: Optional["PartialMessage"] = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<DMChannel id={self.id} name='{self.user}'>"

    def _from_data(self, data: dict):
        if data.get("recipients", None):
            from .user import User
            self.user = User(state=self._state, data=data["recipients"][0])
            self.name = self.user.name

        if data.get("last_message_id", None):
            from .message import PartialMessage
            self.last_message = PartialMessage(
                state=self._state,
                channel_id=self.id,
                id=int(data["last_message_id"])
            )

        if data.get("last_pin_timestamp", None):
            self.last_pin_timestamp = utils.parse_time(data["last_pin_timestamp"])

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.dm

    @property
    def mention(self) -> str:
        """ `str`: The channel's mention """
        return f"<@{self.id}>"

    async def edit(self, *args, **kwargs) -> None:
        """
        Only here to prevent errors

        Raises
        ------
        `TypeError`
            If you try to edit a DM channel
        """
        raise TypeError("Cannot edit a DM channel")


class StoreChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<StoreChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_store


class GroupDMChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<GroupDMChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.group_dm


class DirectoryChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<DirectoryChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_directory


class CategoryChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<CategoryChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_category

    async def create_text_channel(
        self,
        name: str,
        **kwargs
    ) -> TextChannel:
        """
        Create a text channel in the category

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
            The channel object
        """
        return await self.guild.create_text_channel(
            name=name,
            parent_id=self.id,
            **kwargs
        )

    async def create_voice_channel(
        self,
        name: str,
        **kwargs
    ) -> "VoiceChannel":
        """
        Create a voice channel to category

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
        parent_id: `Optional[Snowflake]`
            The Category ID where the channel will be placed
        nsfw: `Optional[bool]`
            Whether the channel is NSFW or not
        reason: `Optional[str]`
            The reason for creating the voice channel

        Returns
        -------
        `VoiceChannel`
            The channel object
        """
        return await self.guild.create_voice_channel(
            name=name,
            parent_id=self.id,
            **kwargs
        )

    async def create_stage_channel(
        self,
        name: str,
        **kwargs
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
        return await self.guild.create_stage_channel(
            name=name,
            parent_id=self.id,
            **kwargs
        )


class NewsChannel(BaseChannel):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<NewsChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_news


# Thread channels
class PublicThread(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

        self.name: str = data["name"]

        self.message_count: int = utils.get_int(data, "message_count") or 0
        self.member_count: int = utils.get_int(data, "member_count") or 0
        self.rate_limit_per_user: int = utils.get_int(data, "rate_limit_per_user") or 0
        self.total_message_sent: int = utils.get_int(data, "total_message_sent") or 0

        self._metadata: dict = data.get("thread_metadata", {})

        self.locked: bool = self._metadata.get("locked", False)
        self.archived: bool = self._metadata.get("archived", False)
        self.auto_archive_duration: int = self._metadata.get("auto_archive_duration", 60)

        self.channel_id: int = int(data["id"])
        self.guild_id: Optional[int] = utils.get_int(data, "guild_id")
        self.owner_id: Optional[int] = utils.get_int(data, "owner_id")
        self.last_message_id: Optional[int] = utils.get_int(data, "last_message_id")
        self.parent_id: Optional[int] = utils.get_int(data, "parent_id")

    def __repr__(self) -> str:
        return f"<PublicThread id={self.id} name='{self.name}'>"

    @property
    def channel(self) -> "PartialChannel":
        """ `PartialChannel`: Returns a partial channel object """
        from .channel import PartialChannel
        return PartialChannel(state=self._state, id=self.channel_id)

    @property
    def guild(self) -> Optional["PartialGuild"]:
        """ `PartialGuild`: Returns a partial guild object """
        if not self.guild_id:
            return None

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def owner(self) -> Optional["PartialUser"]:
        """ `PartialUser`: Returns a partial user object """
        if not self.owner_id:
            return None

        from .user import PartialUser
        return PartialUser(state=self._state, id=self.owner_id)

    @property
    def last_message(self) -> Optional["PartialMessage"]:
        """ `Optional[PartialMessage]`: Returns a partial message object if the last message ID is available """
        if not self.last_message_id:
            return None

        from .message import PartialMessage
        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            id=self.last_message_id
        )


class ForumTag:
    def __init__(self, *, data: dict):
        self.id: Optional[int] = utils.get_int(data, "id")

        self.name: str = data["name"]
        self.moderated: bool = data["moderated"]

        self.emoji_id: Optional[int] = utils.get_int(data, "emoji_id")
        self.emoji_name: Optional[str] = data.get("emoji_name", None)

    def __repr__(self) -> str:
        return f"<ForumTag id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return int(self.id or -1)

    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        *,
        emoji_id: Optional[int] = None,
        emoji_name: Optional[str] = None,
        moderated: bool = False
    ) -> "ForumTag":
        """
        Create a forum tag, used for editing available_tags

        Parameters
        ----------
        name: `Optional[str]`
            The name of the tag
        emoji_id: `Optional[int]`
            The emoji ID of the tag
        emoji_name: `Optional[str]`
            The emoji name of the tag
        moderated: `bool`
            If the tag is moderated

        Returns
        -------
        `ForumTag`
            The tag object
        """
        if emoji_id and emoji_name:
            raise ValueError(
                "Cannot have both emoji_id and "
                "emoji_name defined for a tag."
            )

        return cls(data={
            "name": name or "New Tag",
            "emoji_id": emoji_id,
            "emoji_name": emoji_name,
            "moderated": moderated
        })

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "moderated": self.moderated,
        }

        if self.id:
            payload["id"] = str(self.id)
        if self.emoji_id:
            payload["emoji_id"] = str(self.emoji_id)
        if self.emoji_name:
            payload["emoji_name"] = self.emoji_name

        return payload


class ForumChannel(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self.default_reaction_emoji: Optional[EmojiParser] = None

        self.tags: list[ForumTag] = [
            ForumTag(data=g)
            for g in data.get("tags", [])
        ]

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ForumChannel id={self.id} name='{self.name}'>"

    def _from_data(self, data: dict):
        if data.get("default_reaction_emoji", None):
            self.default_reaction_emoji = EmojiParser(
                data["default_reaction_emoji"]["id"] or
                data["default_reaction_emoji"]["name"]
            )


class ForumThread(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ForumThread id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def _from_data(self, data: dict):
        from .message import Message

        self.message: Message = Message(
            state=self._state,
            data=data["message"],
            guild=self.guild
        )


class NewsThread(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<NewsThread id={self.id} name='{self.name}'>"


class PrivateThread(PublicThread):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_private_thread


class Thread(PublicThread):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        if self._raw_type == 11:
            return ChannelType.guild_public_thread
        return ChannelType.guild_private_thread


# Voice channels

class VoiceRegion:
    def __init__(self, *, data: dict):
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.custom: bool = data["custom"]
        self.deprecated: bool = data["deprecated"]
        self.optimal: bool = data["optimal"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<VoiceRegion id='{self.id}' name='{self.name}'>"


class VoiceChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self.bitrate: int = int(data["bitrate"])
        self.user_limit: int = int(data["user_limit"])
        self.rtc_region: Optional[str] = data.get("rtc_region", None)

    def __repr__(self) -> str:
        return f"<VoiceChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_voice


class StageChannel(VoiceChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<StageChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ `ChannelType`: Returns the channel's type """
        return ChannelType.guild_stage_voice
