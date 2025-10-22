# flake8: noqa: E731
import asyncio
import time

from collections.abc import AsyncIterator, Callable, Generator
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Self, overload

from . import utils
from .embeds import Embed
from .emoji import EmojiParser
from .errors import NotFound
from .enums import (
    ChannelType, ResponseType, VideoQualityType,
    SortOrderType, ForumLayoutType, PrivacyLevelType
)
from .file import File
from .flags import PermissionOverwrite, ChannelFlags, Permissions, MessageFlags
from .mentions import AllowedMentions
from .multipart import MultipartData
from .object import PartialBase, Snowflake
from .response import MessageResponse
from .view import View
from .webhook import Webhook

if TYPE_CHECKING:
    from .guild import Guild, PartialGuild, PartialScheduledEvent
    from .http import DiscordAPI, HTTPResponse
    from .invite import Invite
    from .member import Member
    from .member import ThreadMember
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
    "PartialThread",
    "PrivateThread",
    "PublicThread",
    "StageChannel",
    "StoreChannel",
    "TextChannel",
    "Thread",
    "VoiceChannel",
    "VoiceRegion",
)


def _typing_done_callback(f: asyncio.Future) -> None:
    try:
        f.exception()
    except (asyncio.CancelledError, Exception):
        pass


class Typing:
    def __init__(self, *, state: "DiscordAPI", channel: "PartialChannel"):
        self._state = state

        self.loop = state.bot.loop
        self.channel = channel

    def __await__(self) -> Generator[None, None, None]:
        return self._send_typing().__await__()

    async def __aenter__(self) -> None:
        await self._send_typing()
        self.task = self.loop.create_task(self.do_typing_loop())
        self.task.add_done_callback(_typing_done_callback)

    async def __aexit__(self, *args) -> None:  # noqa: ANN002
        self.task.cancel()

    async def _send_typing(self) -> None:
        await self._state.query(
            "POST",
            f"/channels/{self.channel.id}/typing",
            res_method="text"
        )

    async def do_typing_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            await self._send_typing()


class PartialChannel(PartialBase):
    """
    Represents a partial channel object.

    Attributes
    ----------
    guild_id: `int | None`
        The ID of the guild the channel belongs to, if any
    parent_id: `int | None`
        The ID of the parent channel or category, if any
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        guild_id: int | None = None
    ):
        super().__init__(id=int(id))
        self._state = state

        self.guild_id: int | None = int(guild_id) if guild_id else None
        self.parent_id: int | None = None

        self._raw_type: ChannelType = ChannelType.unknown

    def __repr__(self) -> str:
        return f"<PartialChannel id={self.id}>"

    @property
    def mention(self) -> str:
        """ The channel's mention. """
        return f"<#{self.id}>"

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """
        The guild the channel belongs to (if available).

        If you are using gateway cache, it can return full object too
        """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "BaseChannel | CategoryChannel | PartialChannel | None":
        """
        Returns the channel the thread is in.

        Only returns a full object if cache is enabled for guild and channel.
        """
        if self.guild_id:
            cache = self._state.cache.get_channel_thread(
                guild_id=self.guild_id,
                channel_id=self.id
            )

            if cache:
                return cache

        return PartialChannel(
            state=self._state,
            id=self.id,
            guild_id=self.guild_id
        )

    @property
    def parent(self) -> "BaseChannel | CategoryChannel | PartialChannel | None":
        """
        Returns the parent channel of the thread or the parent category of the channel.

        Only returns a full object if cache is enabled for guild and channel.
        """
        if not self.parent_id:
            return None

        if self.guild_id:
            cache = self._state.cache.get_channel_thread(
                guild_id=self.guild_id,
                channel_id=self.parent_id
            )

            if cache:
                return cache

        return PartialChannel(
            state=self._state,
            id=self.parent_id,
            guild_id=self.guild_id
        )

    def permissions_for(self, member: "Member") -> Permissions:  # noqa: ARG002
        """
        Returns the permissions for a member in the channel.

        However since this is Partial, it will always return Permissions.none()

        Parameters
        ----------
        member:
            The member to get the permissions for.

        Returns
        -------
            The permissions for the member in the channel.
        """
        return Permissions.none()

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return self._raw_type

    def get_partial_message(self, message_id: int) -> "PartialMessage":
        """
        Get a partial message object from the channel.

        Parameters
        ----------
        message_id:
            The message ID to get the partial message from

        Returns
        -------
            The partial message object
        """
        from .message import PartialMessage
        return PartialMessage(
            state=self._state,
            channel_id=self.id,
            guild_id=self.guild_id,
            id=message_id,
        )

    async def fetch_message(self, message_id: int) -> "Message":
        """
        Fetch a message from the channel.

        Parameters
        ----------
        message_id:
            The message ID to fetch

        Returns
        -------
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
        Fetch all pinned messages for the channel in question.

        Returns
        -------
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
        source_channel_id: Snowflake | int
    ) -> None:
        """
        Follow an announcement channel to send messages to the webhook.

        Parameters
        ----------
        source_channel_id:
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
        Fetch all archived public threads.

        Returns
        -------
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
        Fetch all archived private threads.

        Parameters
        ----------
        client:
            If it should fetch only where the client is a member of the thread

        Returns
        -------
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
        max_age: timedelta | int = 86400,  # 24 hours
        max_uses: int | None = 0,
        temporary: bool = False,
        unique: bool = False,
    ) -> "Invite":
        """
        Create an invite for the channel.

        Parameters
        ----------
        max_age:
            How long the invite should last
        max_uses:
            The maximum amount of uses for the invite
        temporary:
            If the invite should be temporary
        unique:
            If the invite should be unique

        Returns
        -------
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
        content: str | None = MISSING,
        *,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        view: View | None = MISSING,
        tts: bool | None = False,
        type: ResponseType | int = 4,  # noqa: A002
        poll: "Poll | None" = MISSING,
        flags: MessageFlags | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        delete_after: float | None = None
    ) -> "Message":
        """
        Send a message to the channel.

        Parameters
        ----------
        content:
            Cotnent of the message
        embed:
            Includes an embed object
        embeds:
            List of embed objects
        file:
            A file object
        files:
            A list of file objects
        view:
            Send components to the message
        tts:
            If the message should be sent as a TTS message
        type:
            The type of response to the message
        allowed_mentions:
            The allowed mentions for the message
        poll:
            The poll to be sent
        flags:
            Flags of the message
        delete_after:
            How long to wait before deleting the message

        Returns
        -------
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
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            )
        )

        r = await self._state.query(
            "POST",
            f"/channels/{self.id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        from .message import Message
        msg = Message(
            state=self._state,
            data=r.response
        )

        if delete_after is not None:
            await msg.delete(delay=float(delete_after))
        return msg

    def _class_to_return(
        self,
        data: dict,
        *,
        state: "DiscordAPI | None" = None,
        guild_id: int | None = None
    ) -> "BaseChannel":
        match data["type"]:
            case x if x in (ChannelType.guild_text, ChannelType.guild_news):
                class_ = TextChannel

            case ChannelType.guild_voice:
                class_ = VoiceChannel

            case ChannelType.guild_category:
                class_ = CategoryChannel

            case ChannelType.guild_news_thread:
                class_ = NewsThread

            case ChannelType.guild_public_thread:
                class_ = PublicThread

            case ChannelType.guild_private_thread:
                class_ = PrivateThread

            case ChannelType.guild_stage_voice:
                class_ = StageChannel

            case ChannelType.guild_forum:
                class_ = ForumChannel

            case _:
                class_ = BaseChannel

        class_: type["BaseChannel"]

        if guild_id is not None:
            data["guild_id"] = int(guild_id)

        return class_(
            state=state or self._state,
            data=data
        )

    @classmethod
    def from_dict(cls, *, state: "DiscordAPI", data: dict) -> Self:
        """
        Create a channel object from a dictionary.

        Requires the state to be set

        Parameters
        ----------
        state:
            The state to use
        data:
            Data provided by Discord API

        Returns
        -------
            The channel object
        """
        temp_class = cls(
            state=state,
            id=int(data["id"]),
            guild_id=utils.get_int(data, "guild_id")
        )

        return temp_class._class_to_return(data=data, state=state)  # type: ignore

    async def fetch(self) -> "BaseChannel":
        """ Fetches the channel and returns the channel object. """
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
        name: str | None = MISSING,
        type: ChannelType | int | None = MISSING,  # noqa: A002
        position: int | None = MISSING,
        topic: str | None = MISSING,
        nsfw: bool | None = MISSING,
        rate_limit_per_user: int | None = MISSING,
        bitrate: int | None = MISSING,
        user_limit: int | None = MISSING,
        overwrites: list[PermissionOverwrite] | None = MISSING,
        parent_id: Snowflake | int | None = MISSING,
        rtc_region: str | None = MISSING,
        video_quality_mode: VideoQualityType | int | None = MISSING,
        default_auto_archive_duration: int | None = MISSING,
        flags: ChannelFlags | None = MISSING,
        available_tags: list["ForumTag"] | None = MISSING,
        default_reaction_emoji: str | None = MISSING,
        default_thread_rate_limit_per_user: int | None = MISSING,
        default_sort_order: SortOrderType | int | None = MISSING,
        default_forum_layout: ForumLayoutType | int | None = MISSING,
        archived: bool | None = MISSING,
        auto_archive_duration: int | None = MISSING,
        locked: bool | None = MISSING,
        invitable: bool | None = MISSING,
        applied_tags: list["ForumTag | int"] | None = MISSING,
        reason: str | None = None,
    ) -> Self:
        """
        Edit the channel.

        Note that this method globaly edits any channel type.
        So be sure to use the correct parameters for the channel.

        Parameters
        ----------
        name:
            New name of the channel (All)
        type:
            The new type of the channel (Text, Announcement)
        position:
            The new position of the channel (All)
        topic:
            The new topic of the channel (Text, Announcement, Forum, Media)
        nsfw:
            If the channel should be NSFW (Text, Voice, Announcement, Stage, Forum, Media)
        rate_limit_per_user:
            How long the slowdown should be (Text, Voice, Stage, Forum, Media)
        bitrate:
            The new bitrate of the channel (Voice, Stage)
        user_limit:
            The new user limit of the channel (Voice, Stage)
        overwrites:
            The new permission overwrites of the channel (All)
        parent_id:
            The new parent ID of the channel (Text, Voice, Announcement, Stage, Forum, Media)
        rtc_region:
            The new RTC region of the channel (Voice, Stage)
        video_quality_mode:
            The new video quality mode of the channel (Voice, Stage)
        default_auto_archive_duration:
            The new default auto archive duration of the channel (Text, Announcement, Forum, Media)
        flags:
            The new flags of the channel (Forum, Media)
        available_tags:
            The new available tags of the channel (Forum, Media)
        default_reaction_emoji:
            The new default reaction emoji of the channel (Forum, Media)
        default_thread_rate_limit_per_user:
            The new default thread rate limit per user of the channel (Text, Forum, Media)
        default_sort_order:
            The new default sort order of the channel (Forum, Media)
        default_forum_layout:
            The new default forum layout of the channel (Forum)
        archived:
            If the thread should be archived (Thread, Forum)
        auto_archive_duration:
            The new auto archive duration of the thread (Thread, Forum)
        locked:
            If the thread should be locked (Thread, Forum)
        invitable:
            If the thread should be invitable by everyone (Thread)
        applied_tags:
            The new applied tags of the forum thread (Forum, Media)
        reason:
            The reason for editing the channel (All)

        Returns
        -------
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
                emoji = EmojiParser(default_reaction_emoji)
                payload["default_reaction_emoji"] = emoji.to_forum_dict()

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

    def typing(self) -> Typing:
        """
        Makes the bot trigger the typing indicator.

        There are two ways you can use this:
        - Usual await call
        - Using `async with` to type as long as you need

        .. code-block:: python

            # Method 1
            await channel.typing()  # Stops after 10 seconds or message sent

            # Method 2
            async with channel.typing():
                asyncio.sleep(4)
        """
        return Typing(state=self._state, channel=self)

    async def set_permission(
        self,
        overwrite: PermissionOverwrite,
        *,
        reason: str | None = None
    ) -> None:
        """
        Set a permission overwrite for the channel.

        Parameters
        ----------
        overwrite:
            The new overwrite permissions for the spesific role/user
        reason:
            The reason for editing the overwrite
        """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/permissions/{int(overwrite.target.id)}",
            json=overwrite.to_dict(),
            res_method="text",
            reason=reason
        )

    async def delete_permission(
        self,
        id: Snowflake | int,  # noqa: A002
        *,
        reason: str | None = None
    ) -> None:
        """
        Delete a permission overwrite for the channel.

        Parameters
        ----------
        id:
            The ID of the overwrite
        reason:
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
        reason: str | None = None
    ) -> None:
        """
        Delete the channel.

        Parameters
        ----------
        reason:
            The reason for deleting the channel
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def create_webhook(
        self,
        name: str,
        *,
        avatar: File | bytes | None = None,
        reason: str | None = None
    ) -> Webhook:
        """
        Create a webhook for the channel.

        Parameters
        ----------
        name:
            The name of the webhook
        avatar:
            The avatar of the webhook
        reason:
            The reason for creating the webhook that appears in audit logs

        Returns
        -------
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
        content: str | None = None,
        embed: Embed | None = None,
        embeds: list[Embed] | None = None,
        file: File | None = None,
        files: list[File] | None = None,
        allowed_mentions: AllowedMentions | None = None,
        view: View | None = None,
        auto_archive_duration: int | None = 4320,
        rate_limit_per_user: int | None = None,
        applied_tags: list["ForumTag | int"] | None = None
    ) -> "ForumThread":
        """
        Create a forum or media thread in the channel.

        Parameters
        ----------
        name:
            The name of the thread
        content:
            The content of the message
        embed:
            Embed to be sent
        embeds:
            List of embeds to be sent
        file:
            File to be sent
        files:
            List of files to be sent
        allowed_mentions:
            The allowed mentions for the message
        view:
            The view to be sent
        auto_archive_duration:
            The duration in minutes to automatically archive the thread after recent activity
        rate_limit_per_user:
            How long the slowdown should be
        applied_tags:
            The tags to be applied to the thread

        Returns
        -------
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
        type: ChannelType | int = ChannelType.guild_private_thread,  # noqa: A002
        auto_archive_duration: int | None = 4320,
        invitable: bool = True,
        rate_limit_per_user: timedelta | int | None = None,
        reason: str | None = None
    ) -> "PublicThread | PrivateThread | NewsThread":
        """
        Creates a thread in the channel.

        Parameters
        ----------
        name:
            The name of the thread
        type:
            The type of thread to create
        auto_archive_duration:
            The duration in minutes to automatically archive the thread after recent activity
        invitable:
            If the thread is invitable
        rate_limit_per_user:
            How long the slowdown should be
        reason:
            The reason for creating the thread

        Returns
        -------
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

            if rate_limit_per_user not in range(21601):
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
                class_ = PublicThread

            case ChannelType.guild_private_thread:
                class_ = PrivateThread

            case ChannelType.guild_news_thread:
                class_ = NewsThread

            case _:
                raise ValueError("Invalid thread type")

        return class_(
            state=self._state,
            data=r.response
        )

    async def fetch_history(
        self,
        *,
        before: "datetime | Message | Snowflake | int | None" = None,
        after: "datetime | Message | Snowflake | int | None" = None,
        around: "datetime | Message | Snowflake | int | None" = None,
        limit: int | None = 100,
        oldest_first: bool = False
    ) -> AsyncIterator["Message"]:
        """
        Fetch the channel's message history.

        Parameters
        ----------
        before:
            Get messages before this message
        after:
            Get messages after this message
        around:
            Get messages around this message
        limit:
            The maximum amount of messages to fetch.
            `None` will fetch all users.
        oldest_first:
            Whether to fetch the oldest messages first

        Yields
        ------
        `Message`
            The message object
        """
        async def _get_history(limit: int, **kwargs) -> "HTTPResponse[dict]":
            params = {"limit": limit}
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = utils.normalize_entity_id(value)

            return await self._state.query(
                "GET",
                f"/channels/{self.id}/messages",
                params=params
            )

        async def _around_http(
            http_limit: int,
            around_id: int | None,
            limit: int | None
        ) -> tuple[dict, int | None, int | None]:
            r = await _get_history(limit=http_limit, around=around_id)
            return r.response, None, limit

        async def _after_http(
            http_limit: int,
            after_id: int | None,
            limit: int | None
        ) -> tuple[dict, int | None, int | None]:
            r = await _get_history(limit=http_limit, after=after_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                after_id = int(r.response[0]["id"])

            return r.response, after_id, limit

        async def _before_http(
            http_limit: int,
            before_id: int | None,
            limit: int | None
        ) -> tuple[dict, int | None, int | None]:
            r = await _get_history(limit=http_limit, before=before_id)

            if r.response:
                if limit is not None:
                    limit -= len(r.response)
                before_id = int(r.response[-1]["id"])

            return r.response, before_id, limit

        # Default values
        predicate = None

        if around:
            if limit is None:
                raise ValueError("limit must be specified when using around")
            if limit > 100:
                raise ValueError("limit must be less than or equal to 100 when using around")

            strategy, state = _around_http, utils.normalize_entity_id(around)
        elif after:
            strategy, state = _after_http, utils.normalize_entity_id(after)
            if before:
                predicate = lambda x: int(x["id"]) < utils.normalize_entity_id(before)
        elif before:
            strategy, state = _before_http, utils.normalize_entity_id(before)
            if after:
                predicate = lambda x: int(x["id"]) > utils.normalize_entity_id(after)
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

            if oldest_first:
                messages = reversed(messages)
            if predicate:
                messages = filter(predicate, messages)

            i = 0
            for msg in messages:
                yield Message(
                    state=self._state,
                    data=msg,
                    guild=self.guild
                )
                i += 1

            if i < 100:
                break

    @overload
    async def bulk_delete_messages(
        self,
        *,
        check: Callable[["Message"], bool] | None = None,
        before: "datetime | Message | Snowflake | int | None" = None,
        after: "datetime | Message | Snowflake | int | None" = None,
        around: "datetime | Message | Snowflake | int | None" = None,
        message_ids: list["Message | Snowflake"],
        limit: int | None = 100,
        reason: str | None = None
    ) -> None:
        ...

    @overload
    async def bulk_delete_messages(
        self,
        *,
        check: Callable[["Message"], bool] | None = None,
        before: "datetime | Message | Snowflake | int | None" = None,
        after: "datetime | Message | Snowflake | int | None" = None,
        around: "datetime | Message | Snowflake | int | None" = None,
        message_ids: None = None,
        limit: int | None = 100,
        reason: str | None = None
    ) -> list["Message"]:
        ...

    async def bulk_delete_messages(
        self,
        *,
        check: Callable[["Message"], bool] | None = None,
        before: "datetime | Message | Snowflake | int | None" = None,
        after: "datetime | Message | Snowflake | int | None" = None,
        around: "datetime | Message | Snowflake | int | None" = None,
        message_ids: list["Message | Snowflake"] | None = None,
        limit: int | None = 100,
        reason: str | None = None
    ) -> list["Message"] | None:
        """
        Deletes messages in bulk.

        Parameters
        ----------
        check:
            A function to check if the message should be deleted
        before:
            The message before which to delete
        after:
            The message after which to delete
        around:
            The message around which to delete
        message_ids:
            The message IDs to delete
        limit:
            The maximum amount of messages to delete
        reason:
            The reason for deleting the messages

        Returns
        -------
            Returns a list of messages deleted
            If you provide message_ids upfront, it will skip history search and delete
        """
        msg_collector: list["Message"] = []

        async def _bulk_delete(messages: list["Message"]) -> None:
            if len(messages) > 1:
                await self._state.query(
                    "POST",
                    f"/channels/{self.id}/messages/bulk-delete",
                    res_method="text",
                    json={"messages": [str(int(g)) for g in messages]},
                    reason=reason
                )
            else:
                await _single_delete(messages)

        async def _single_delete(messages: list["Message"]) -> None:
            for g in messages:
                try:
                    await g.delete()
                except NotFound as e:
                    if e.code == 10008:
                        pass
                    raise e

        if message_ids is not None:
            # Remove duplicates just in case
            message_ids = list(set(message_ids))
            await _bulk_delete(message_ids)  # type: ignore
            return None

        count = 0
        minimum_time = int((time.time() - 14 * 24 * 60 * 60) * 1000 - 1420070400000) << 22
        strategy = _bulk_delete

        async for message in self.fetch_history(
            before=before,
            after=after,
            around=around,
            limit=limit
        ):
            if count == 100:
                to_delete = msg_collector[-100:]
                await strategy(to_delete)
                count = 0
                await asyncio.sleep(0.5)

            if check is not None and not check(message):
                continue

            if message.id < minimum_time:
                if count == 1:
                    await msg_collector[-1].delete()
                elif count >= 2:
                    await strategy(msg_collector[-count:])

                count = 0
                strategy = _single_delete

            count += 1
            msg_collector.append(message)

        if count != 0:
            await strategy(msg_collector[-count:])

        return msg_collector

    async def join_thread(self) -> None:
        """ Make the bot join a thread. """
        await self._state.query(
            "PUT",
            f"/channels/{self.id}/thread-members/@me",
            res_method="text"
        )

    async def leave_thread(self) -> None:
        """ Make the bot leave a thread. """
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
        Add a thread member.

        Parameters
        ----------
        user_id:
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
        Remove a thread member.

        Parameters
        ----------
        user_id:
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
    ) -> "ThreadMember":
        """
        Fetch a thread member.

        Parameters
        ----------
        user_id:
            The user ID to fetch

        Returns
        -------
            The thread member object
        """
        if not self.guild:
            raise ValueError("Cannot fetch thread member without guild_id")

        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/thread-members/{user_id}",
            params={"with_member": "true"}
        )

        from .member import ThreadMember
        return ThreadMember(
            state=self._state,
            guild=self.guild,
            data=r.response,
        )

    async def fetch_thread_members(self) -> list["ThreadMember"]:
        """
        Fetch all thread members.

        Returns
        -------
            The list of thread members
        """
        if not self.guild:
            raise ValueError("Cannot fetch thread member without guild_id")

        r = await self._state.query(
            "GET",
            f"/channels/{self.id}/thread-members",
            params={"with_member": "true"},
        )

        from .member import ThreadMember
        return [
            ThreadMember(
                state=self._state,
                guild=self.guild,
                data=data
            )
            for data in r.response
        ]


class BaseChannel(PartialChannel):
    """
    Represents a base channel object.

    Attributes
    ----------
    name: str | None
        The name of the channel
    nsfw: bool
        Whether the channel is NSFW
    topic: str | None
        The topic of the channel
    position: int | None
        The position of the channel in the guild
    last_message_id: int | None
        The ID of the last message in the channel
    parent_id: int | None
        The ID of the parent channel (if any)
    rate_limit_per_user: int
        The rate limit per user in seconds
    permission_overwrites: list[PermissionOverwrite]
        The permission overwrites for the channel
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild_id: int | None = None
    ):
        super().__init__(
            state=state,
            id=int(data["id"]),
            guild_id=utils.get_int(data, "guild_id", default=guild_id)
        )

        self.name: str | None = data.get("name")
        self.nsfw: bool = data.get("nsfw", False)
        self.topic: str | None = data.get("topic")
        self.position: int | None = utils.get_int(data, "position")
        self.last_message_id: int | None = utils.get_int(data, "last_message_id")
        self.parent_id: int | None = utils.get_int(data, "parent_id")
        self.rate_limit_per_user: int = data.get("rate_limit_per_user", 0)

        self._raw_type: ChannelType = ChannelType(data["type"])

        self.permission_overwrites: list[PermissionOverwrite] = [
            PermissionOverwrite.from_dict(g)
            for g in data.get("permission_overwrites", [])
        ]

    def __repr__(self) -> str:
        return f"<Channel id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name or ""

    def permissions_for(self, member: "Member") -> Permissions:
        """
        Returns the permissions for a member in the channel.

        Note that this only works if you are using Gateway with guild, role and channel cache.

        Parameters
        ----------
        member:
            The member to get the permissions for.

        Returns
        -------
            The permissions for the member in the channel.
        """
        if getattr(self.guild, "owner_id", None) == member.id:
            return Permissions.all()

        base: Permissions = getattr(
            self.guild.default_role,
            "permissions",
            Permissions.none()
        )

        for r in member.roles:
            role = self.guild.get_role(r.id)
            if role is None:
                continue
            base |= getattr(role, "permissions", Permissions.none())

        if Permissions.administrator in base:
            return Permissions.all()

        everyone = next((
            g for g in self.permission_overwrites
            if g.target.id == self.guild.default_role.id
        ), None)

        if everyone:
            base = base.handle_overwrite(int(everyone.allow), int(everyone.deny))
            overwrites = [
                g for g in self.permission_overwrites
                if g.target.id != everyone.target.id
            ]
        else:
            overwrites = self.permission_overwrites

        allows, denies = 0, 0

        for ow in overwrites:
            if ow.is_role() and ow.target.id in member.roles:
                allows |= int(ow.allow)
                denies |= int(ow.deny)

        base = base.handle_overwrite(allows, denies)

        for ow in overwrites:
            if ow.is_member() and ow.target.id == member.id:
                allows |= int(ow.allow)
                denies |= int(ow.deny)
                break

        if member.is_timed_out():
            timeout_perm = (
                Permissions.view_channel |
                Permissions.read_message_history
            )

            if Permissions.view_channel not in base:
                timeout_perm &= ~Permissions.view_channel
            if Permissions.read_message_history not in base:
                timeout_perm &= ~Permissions.read_message_history

            base = timeout_perm

        return base

    @property
    def mention(self) -> str:
        """ The channel's mention. """
        return f"<#{self.id}>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_text

    @classmethod
    def from_dict(
        cls,
        *,
        state: "DiscordAPI",
        data: dict,
        guild_id: int | None = None
    ) -> "BaseChannel":
        """
        Create a channel object from a dictionary.

        Requires the state to be set

        Parameters
        ----------
        state:
            The state to use
        data:
            Data provided by Discord API
        guild_id:
            Guild ID to create the channel object with

        Returns
        -------
            The channel object
        """
        return cls(state=state, data=data)._class_to_return(
            data=data,
            state=state,
            guild_id=guild_id
        )


class TextChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<TextChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        if self._raw_type == 0:
            return ChannelType.guild_text
        return ChannelType.guild_news


class DMChannel(BaseChannel):
    """
    Represents a Direct Message channel.

    Attributes
    ----------
    name: str | None
        The name of the channel (usually the user's name)
    user: User | None
        The user in the DM channel
    last_message: PartialMessage | None
        The last message in the DM channel
    """
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

        self.name: str | None = None
        self.user: "User | None" = None
        self.last_message: "PartialMessage | None" = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<DMChannel id={self.id} name='{self.user}'>"

    def _from_data(self, data: dict) -> None:
        if data.get("recipients"):
            from .user import User
            self.user = User(state=self._state, data=data["recipients"][0])
            self.name = self.user.name

        if data.get("last_message_id"):
            from .message import PartialMessage
            self.last_message = PartialMessage(
                state=self._state,
                channel_id=self.id,
                id=int(data["last_message_id"])
            )

        if data.get("last_pin_timestamp"):
            self.last_pin_timestamp = utils.parse_time(data["last_pin_timestamp"])

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.dm

    @property
    def mention(self) -> str:
        """ The channel's mention. """
        return f"<@{self.id}>"

    async def edit(self, *args, **kwargs) -> None:  # noqa: ANN002, ARG002
        """
        Only here to prevent errors.

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
        """ Returns the channel's type. """
        return ChannelType.guild_store


class GroupDMChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<GroupDMChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.group_dm


class DirectoryChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<DirectoryChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_directory


class CategoryChannel(BaseChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<CategoryChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_category

    @property
    def channels(self) -> list["BaseChannel | PartialChannel"]:
        """
        Returns a list of channels in this category.

        This will only return channels that are in the same guild as the category.
        """
        guild = self._state.cache.get_guild(self.guild_id)
        if not guild:
            return []

        channels: list["BaseChannel | PartialChannel"] = [
            g for g in guild.channels
            if g.parent_id == self.id
        ]

        voice_types = [
            ChannelType.guild_voice,
            ChannelType.guild_stage_voice
        ]

        return sorted(
            channels,
            key=lambda x: (
                1 if x.type in voice_types else 0,
                getattr(x, "position", 0)
            )
        )

    async def create_text_channel(
        self,
        name: str,
        **kwargs
    ) -> TextChannel:
        """
        Create a text channel in the category.

        Parameters
        ----------
        name:
            The name of the channel
        topic:
            The topic of the channel
        rate_limit_per_user:
            The rate limit per user of the channel
        overwrites:
            The permission overwrites of the category
        parent_id:
            The Category ID where the channel will be placed
        nsfw:
            Whether the channel is NSFW or not
        reason:
            The reason for creating the text channel
        **kwargs:
            Keyword arguments to pass to the channel, look above

        Returns
        -------
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
        Create a voice channel to category.

        Parameters
        ----------
        name:
            The name of the channel
        bitrate:
            The bitrate of the channel
        user_limit:
            The user limit of the channel
        rate_limit_per_user:
            The rate limit per user of the channel
        overwrites:
            The permission overwrites of the category
        position:
            The position of the channel
        parent_id:
            The Category ID where the channel will be placed
        nsfw:
            Whether the channel is NSFW or not
        reason:
            The reason for creating the voice channel
        **kwargs:
            Keyword arguments to pass to the channel, look above

        Returns
        -------
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
        Create a stage channel.

        Parameters
        ----------
        name:
            The name of the channel
        bitrate:
            The bitrate of the channel
        user_limit:
            The user limit of the channel
        overwrites:
            The permission overwrites of the category
        position:
            The position of the channel
        video_quality_mode:
            The video quality mode of the channel
        parent_id:
            The Category ID where the channel will be placed
        reason:
            The reason for creating the stage channel
        **kwargs:
            Keyword arguments to pass to the channel, look above

        Returns
        -------
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
        """ Returns the channel's type. """
        return ChannelType.guild_news


# Thread channels
class PartialThread(PartialChannel):
    """
    Represents a partial thread channel object.

    Attributes
    ----------
    parent_id: int
        The ID of the parent channel
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        guild_id: int,
        parent_id: int,
        type: ChannelType | int  # noqa: A002
    ):
        super().__init__(state=state, id=int(id), guild_id=int(guild_id))
        self.parent_id: int = int(parent_id)
        self._raw_type: ChannelType = ChannelType(int(type))

    def __repr__(self) -> str:
        return f"<PartialThread id={self.id} type={self.type}>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return self._raw_type


class PublicThread(BaseChannel):
    """
    Represents a public thread channel object.

    Attributes
    ----------
    name: str
        The name of the thread
    message_count: int
        The number of messages in the thread
    member_count: int
        The number of members in the thread
    rate_limit_per_user: int
        The rate limit per user in seconds
    locked: bool
        Whether the thread is locked
    archived: bool
        Whether the thread is archived
    auto_archive_duration: int
        The duration in minutes to automatically archive the thread after recent activity
    channel_id: int
        The ID of the channel
    newly_created: bool
        Whether the thread was newly created
    guild_id: int | None
        The ID of the guild the thread belongs to
    owner_id: int | None
        The ID of the user who owns the thread
    last_message_id: int | None
        The ID of the last message in the thread
    """
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
        self.newly_created: bool = data.get("newly_created", False)
        self.guild_id: int | None = utils.get_int(data, "guild_id")
        self.owner_id: int | None = utils.get_int(data, "owner_id")
        self.last_message_id: int | None = utils.get_int(data, "last_message_id")

    def __repr__(self) -> str:
        return f"<PublicThread id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_public_thread

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ Returns a partial guild object. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def owner(self) -> "PartialUser | None":
        """ Returns a partial user object. """
        if not self.owner_id:
            return None

        from .user import PartialUser
        return PartialUser(state=self._state, id=self.owner_id)

    @property
    def last_message(self) -> "PartialMessage | None":
        """ Returns a partial message object if the last message ID is available. """
        if not self.last_message_id:
            return None

        from .message import PartialMessage
        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            guild_id=self.guild_id,
            id=self.last_message_id
        )


class ForumTag:
    """
    Represents a forum tag object.

    Attributes
    ----------
    id: int | None
        The ID of the tag
    name: str
        The name of the tag
    moderated: bool
        Whether the tag is moderated
    emoji_id: int | None
        The emoji ID of the tag
    emoji_name: str | None
        The emoji name of the tag
    """
    def __init__(self, *, data: dict):
        self.id: int | None = utils.get_int(data, "id")

        self.name: str = data["name"]
        self.moderated: bool = data.get("moderated", False)

        self.emoji_id: int | None = utils.get_int(data, "emoji_id")
        self.emoji_name: str | None = data.get("emoji_name")

    def __repr__(self) -> str:
        return f"<ForumTag id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return int(self.id or -1)

    @classmethod
    def create(
        cls,
        name: str | None = None,
        *,
        emoji_id: int | None = None,
        emoji_name: str | None = None,
        moderated: bool = False
    ) -> "ForumTag":
        """
        Create a forum tag, used for editing available_tags.

        Parameters
        ----------
        name:
            The name of the tag
        emoji_id:
            The emoji ID of the tag
        emoji_name:
            The emoji name of the tag
        moderated:
            If the tag is moderated

        Returns
        -------
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
        """ The forum tag as a dictionary. """
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

    @classmethod
    def from_data(cls, *, data: dict) -> Self:
        """
        Create a forum tag from a dictionary.

        Parameters
        ----------
        data:
            The dictionary to create the forum tag from

        Returns
        -------
            The forum tag
        """
        self = cls.__new__(cls)
        self.name = data["name"]
        self.id = int(data["id"])
        self.moderated = data.get("moderated", False)

        self.emoji_id = utils.get_int(data, "emoji_id")
        self.emoji_name = data.get("emoji_name")

        return self


class ForumChannel(PublicThread):
    """
    Represents a forum channel object.

    Attributes
    ----------
    default_reaction_emoji: EmojiParser | None
        The default reaction emoji for the forum channel
    tags: list[ForumTag]
        The available tags for the forum channel
    """
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self.default_reaction_emoji: EmojiParser | None = None

        self.tags: list[ForumTag] = [
            ForumTag(data=g)
            for g in data.get("available_tags", [])
        ]

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ForumChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_forum

    def _from_data(self, data: dict) -> None:
        if data.get("default_reaction_emoji"):
            target = (
                data["default_reaction_emoji"].get("id", None) or
                data["default_reaction_emoji"].get("name", None)
            )

            if target:
                self.default_reaction_emoji = EmojiParser(target)


class ForumThread(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self._from_data(data)

    def __repr__(self) -> str:
        return f"<ForumThread id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def _from_data(self, data: dict) -> None:
        from .message import Message

        self.message: Message = Message(
            state=self._state,
            data=data["message"],
            guild=self.guild
        )

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_public_thread


class NewsThread(PublicThread):
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<NewsThread id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_news_thread


class PrivateThread(PublicThread):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_private_thread


class Thread(PublicThread):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        if self._raw_type == 11:
            return ChannelType.guild_public_thread
        return ChannelType.guild_private_thread


# Voice channels

class VoiceRegion:
    """
    Represents a voice region object.

    Attributes
    ----------
    id: str
        The ID of the voice region
    name: str
        The name of the voice region
    custom: bool
        Whether the voice region is custom
    deprecated: bool
        Whether the voice region is deprecated
    optimal: bool
        Whether the voice region is optimal for the current user
    """
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
    """
    Represents a voice channel object.

    Attributes
    ----------
    id: int
        The ID of the voice channel
    name: str | None
        The name of the voice channel
    bitrate: int
        The bitrate of the voice channel in bits per second
    user_limit: int
        The user limit of the voice channel
    rtc_region: str | None
        The RTC region of the voice channel, if set
    """
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)
        self.bitrate: int = int(data["bitrate"])
        self.user_limit: int = int(data["user_limit"])
        self.rtc_region: str | None = data.get("rtc_region")

    def __repr__(self) -> str:
        return f"<VoiceChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_voice


class StageInstance(PartialBase):
    """
    Represents a stage instance for a stage channel.

    This holds information about a live stage.

    Attributes
    ----------
    id: int
        The ID of the stage instance
    channel_id: int
        The ID of the stage channel
    guild_id: int
        The associated guild ID of the stage channel
    topic: str
        The topic of the stage instance
    privacy_level: PrivacyLevelType
        The privacy level of the stage instance
    guild_scheduled_event_id: int | None
        The guild scheduled event ID associated with this stage instance
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | None" = None,
    ) -> None:
        super().__init__(id=int(data["id"]))
        self._state: "DiscordAPI" = state
        self._guild: "PartialGuild | None" = guild
        self._from_data(data)

    def _from_data(self, data: dict) -> None:
        self.channel_id: int = int(data["channel_id"])
        self.guild_id: int = int(data["guild_id"])
        self.topic: str = data["topic"]
        self.privacy_level: PrivacyLevelType = PrivacyLevelType(data["privacy_level"])
        self.guild_scheduled_event_id: int | None = utils.get_int(data, "guild_scheduled_event_id")

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "PartialChannel | StageChannel":
        return self.guild.get_channel(self.channel_id) or (
            PartialChannel(state=self._state, id=self.channel_id)
        )

    @property
    def scheduled_event(self) -> "PartialScheduledEvent | None":
        if not self.guild_scheduled_event_id:
            return None

        from .guild import PartialScheduledEvent
        return PartialScheduledEvent(
            state=self._state,
            id=self.guild_scheduled_event_id,
            guild_id=self.guild_id
        )

    def __repr__(self) -> str:
        return f"<StageInstance id={self.id!r} topic={self.topic!r}>"

    async def edit(
        self,
        *,
        topic: str = MISSING,
        privacy_level: PrivacyLevelType = MISSING,
        reason: str | None = None
    ) -> Self:
        """
        Edit this stage instance.

        Parameters
        ----------
        topic:
            The new topic of this stage instance.
        privacy_level:
            The new privacy level of this stage instance.
        reason:
            The reason for editing the stage instance.

        Returns
        -------
            The edited stage instance
        """
        payload = {}

        if topic is not MISSING:
            payload["topic"] = str(topic)

        if privacy_level is not MISSING:
            payload["privacy_level"] = int(privacy_level)

        r = await self._state.query(
            "PATCH",
            f"/stage-instances/{self.id}",
            json=payload,
            reason=reason
        )

        return self.__class__(
            state=self._state,
            data=r.response,
            guild=self._guild,
        )

    async def delete(self, *, reason: str | None = None) -> None:
        """
        Delete this stage instance.

        Parameters
        ----------
        reason:
            The reason for deleting the stage instance
        """
        await self._state.query(
            "DELETE",
            f"/stage-instances/{self.id}",
            res_method="text",
            reason=reason
        )


class StageChannel(VoiceChannel):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        super().__init__(state=state, data=data)

        self._stage_instance: StageInstance | None = None

    def __repr__(self) -> str:
        return f"<StageChannel id={self.id} name='{self.name}'>"

    @property
    def type(self) -> ChannelType:
        """ Returns the channel's type. """
        return ChannelType.guild_stage_voice

    @property
    def stage_instance(self) -> StageInstance | None:
        """ Returns the stage instance for this channel, if available and cached."""
        return self._stage_instance

    async def fetch_stage_instance(self) -> StageInstance:
        """
        Fetch the stage instance associated with this stage channel.

        Returns
        -------
            The stage instance of the channel
        """
        r = await self._state.query(
            "GET",
            f"/stage-instances/{self.id}"
        )

        return StageInstance(
            state=self._state,
            data=r.response,
            guild=self.guild
        )

    async def create_stage_instance(
        self,
        *,
        topic: str,
        privacy_level: PrivacyLevelType = MISSING,
        send_start_notification: bool = MISSING,
        guild_scheduled_event: Snowflake | int = MISSING,
        reason: str | None = None
    ) -> StageInstance:
        """
        Create a stage instance.

        Parameters
        ----------
        topic:
            The topic of the stage instance
        privacy_level:
            The privacy level of the stage instance.
            Defaults to `PrivacyLevelType.guild_only`
        send_start_notification:
            Whether to notify @everyone that the stage instance has started.
        guild_scheduled_event:
            The guild scheduled event to associate with this stage instance.
        reason:
            The reason for creating the stage instance

        Returns
        -------
            The created stage instance
        """
        payload = {
            "channel_id": self.id,
            "topic": topic,
        }

        if privacy_level is not MISSING:
            payload["privacy_level"] = int(privacy_level)

        if send_start_notification is not MISSING:
            payload["send_start_notification"] = send_start_notification

        if guild_scheduled_event is not MISSING:
            payload["guild_scheduled_event_id"] = utils.normalize_entity_id(guild_scheduled_event)

        r = await self._state.query(
            "POST",
            "/stage-instances",
            json=payload,
            reason=reason
        )

        self._stage_instance = StageInstance(
            state=self._state,
            data=r.response,
            guild=self.guild
        )
        return self._stage_instance
