import asyncio

from datetime import timedelta, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Optional, Self
from collections.abc import AsyncIterator, Callable

from . import utils
from .colour import Colour
from .embeds import Embed
from .emoji import EmojiParser
from .enums import MessageReferenceType, MessageType, InteractionType
from .errors import HTTPException
from .file import File
from .flags import AttachmentFlags, MessageFlags
from .mentions import AllowedMentions
from .object import PartialBase, Snowflake
from .response import MessageResponse
from .role import Role, PartialRole
from .sticker import PartialSticker
from .user import User
from .view import View

if TYPE_CHECKING:
    from .channel import BaseChannel, PartialChannel, PublicThread
    from .guild import Guild, PartialGuild
    from .http import DiscordAPI, HTTPResponse
    from .member import Member

MISSING = utils.MISSING

__all__ = (
    "Attachment",
    "JumpURL",
    "Message",
    "MessageInteraction",
    "MessageReference",
    "PartialMessage",
    "Poll",
    "WebhookMessage",
)


class MessageInteraction(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(id=int(data["id"]))
        self._state = state

        self.type: InteractionType = InteractionType(data["type"])
        self.name: str | None = data.get("name")
        self.user: User = User(
            state=state,
            data=data["user"]
        )


class MessageReaction:
    def __init__(self, *, state: "DiscordAPI", message: "Message", data: dict):
        self._state = state
        self._message = message

        self.count: int = int(data["count"])
        self.burst_count: int = int(data["burst_count"])

        self.me: bool = data.get("me", False)
        self.emoji: EmojiParser = EmojiParser.from_dict(data["emoji"])

        self.me_burst: bool = data.get("me_burst", False)
        self.burst_me: bool = data.get("burst_me", False)
        self.burst_count: int = data.get("burst_count", 0)
        self.burst_colors: list[Colour] = [
            Colour.from_hex(g)
            for g in data.get("burst_colors", [])
        ]

    async def add(self) -> None:
        """ Make the bot react with this emoji. """
        parsed = self.emoji.to_reaction()
        await self._state.query(
            "PUT",
            f"/channels/{self._message.channel.id}/messages/{self._message.id}/reactions/{parsed}/@me",
            res_method="text"
        )

    async def remove(self, *, user_id: int | None = None) -> None:
        """
        Remove the reaction from the message.

        Parameters
        ----------
        user_id:
            User ID to remove the reaction from
            If none provided, it will remove the reaction from the bot
        """
        parsed = self.emoji.to_reaction()
        url = (
            f"/channels/{self._message.channel.id}/messages/{self._message.id}/reactions/{parsed}"
            f"/{user_id}" if user_id is not None else "/@me"
        )

        await self._state.query(
            "DELETE",
            url,
            res_method="text"
        )


class JumpURL:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        url: str | None = None,
        guild_id: int | None = None,
        channel_id: int | None = None,
        message_id: int | None = None
    ):
        self._state = state

        self.guild_id: int | None = int(guild_id) if guild_id else None
        self.channel_id: int | None = channel_id or None
        self.message_id: int | None = message_id or None

        if url:
            if any([guild_id, channel_id, message_id]):
                raise ValueError("Cannot provide both a URL and a guild_id, channel_id or message_id")

            parse_url: list[tuple[str, str, str | None]] | None = utils.re_jump_url.findall(url)
            if not parse_url:
                raise ValueError("Invalid jump URL provided")

            gid, cid, mid = parse_url[0]

            self.channel_id = int(cid)
            if gid != "@me":
                self.guild_id = int(gid)
            if mid:
                self.message_id = int(mid)

        if not self.channel_id:
            raise ValueError("Cannot create a JumpURL without a channel_id")

    def __repr__(self) -> str:
        return (
            f"<JumpURL guild_id={self.guild_id} channel_id={self.channel_id} "
            f"message_id={self.message_id}>"
        )

    def __str__(self) -> str:
        return self.url

    @property
    def guild(self) -> Optional["Guild | PartialGuild"]:
        """ The guild the message was sent in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(
            state=self._state,
            id=self.guild_id
        )

    async def fetch_guild(self) -> "Guild":
        """ Returns the guild the message was sent in. """
        if not self.guild_id:
            raise ValueError("Cannot fetch a guild without a guild_id available")

        return await self.guild.fetch()

    @property
    def channel(self) -> Optional["BaseChannel | PartialChannel"]:
        """
        Returns the channel the message was sent in.

        If guild and channel cache is enabled, it can also return full channel object.
        """
        if not self.channel_id:
            return None

        if self.guild_id:
            cache = self._state.cache.get_channel_thread(
                guild_id=self.guild_id,
                channel_id=self.channel_id
            )

            if cache:
                return cache

        from .channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    async def fetch_channel(self) -> "BaseChannel":
        """ Returns the channel the message was sent in. """
        return await self.channel.fetch()

    @property
    def message(self) -> Optional["PartialMessage"]:
        """ Returns the message if a message_id is available. """
        if not self.channel_id or not self.message_id:
            return None

        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            guild_id=self.guild_id,
            id=self.message_id
        )

    async def fetch_message(self) -> "Message":
        """ Returns the message if a message_id is available. """
        if not self.message_id:
            raise ValueError("Cannot fetch a message without a message_id available")

        return await self.message.fetch()

    @property
    def url(self) -> str:
        """ Returns the jump URL. """
        if self.channel_id and self.message_id:
            return f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}/{self.message_id}"
        return f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}"


class PollAnswer:
    def __init__(
        self,
        *,
        id: int,  # noqa: A002
        text: str | None = None,
        emoji: EmojiParser | str | None = None
    ):
        self.id: int = id
        self.text: str | None = text

        self.emoji: EmojiParser | str | None = None
        if isinstance(emoji, str):
            self.emoji = EmojiParser(emoji)

        if self.text is None and self.emoji is None:
            raise ValueError("Either text or emoji must be provided")

        # Data only available when fetching message data
        self.count: int = 0
        self.me_voted: bool = False

    def __repr__(self) -> str:
        return f"<PollAnswer id={self.id} count={self.count}>"

    def __int__(self) -> int:
        return self.id

    def __str__(self) -> str:
        return self.text or str(self.emoji)

    def to_dict(self) -> dict:
        data = {
            "answer_id": self.id,
            "poll_media": {}
        }

        if self.text:
            data["poll_media"]["text"] = self.text
        if isinstance(self.emoji, EmojiParser):
            data["poll_media"]["emoji"] = self.emoji.to_dict()

        return data

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        emoji = data["poll_media"].get("emoji", None)
        if emoji:
            emoji = EmojiParser.from_dict(emoji)

        return cls(
            id=data["answer_id"],
            text=data["poll_media"].get("text", None),
            emoji=emoji
        )


class Poll:
    def __init__(
        self,
        *,
        text: str,
        allow_multiselect: bool = False,
        duration: timedelta | int | None = None
    ):
        self.text: str | None = text

        self.allow_multiselect: bool = allow_multiselect
        self.answers: list[PollAnswer] = []

        self.duration: int | None = None

        if duration is not None:
            if isinstance(duration, timedelta):
                duration = int(duration.total_seconds())
            self.duration = duration

            if self.duration > timedelta(days=7).total_seconds():
                raise ValueError("Duration cannot be more than 7 days")

            # Convert to hours int
            self.duration = int(self.duration / 3600)

        self.layout_type: int = 1  # This is the only layout type available

        # Data only available when fetching message data
        self.expiry: datetime | None = None
        self.is_finalized: bool = False

    def __repr__(self) -> str:
        return f"<Poll text='{self.text}' answers={self.answers}>"

    def __str__(self) -> str:
        return self.text or ""

    def __len__(self) -> int:
        return len(self.answers)

    def add_answer(
        self,
        *,
        text: str | None = None,
        emoji: EmojiParser | str | None = None
    ) -> PollAnswer:
        """
        Add an answer to the poll.

        Parameters
        ----------
        text:
            The text of the answer
        emoji:
            The emoji of the answer
        """
        if not text and not emoji:
            raise ValueError("Either text or emoji must be provided")

        answer = PollAnswer(
            id=len(self.answers) + 1,
            text=text,
            emoji=emoji
        )

        self.answers.append(answer)

        return answer

    def remove_answer(
        self,
        answer_id: PollAnswer | int
    ) -> None:
        """
        Remove an answer from the poll.

        Parameters
        ----------
        answer_id:
            The ID to the answer to remove

        Raises
        ------
        `ValueError`
            - If the answer ID does not exist
            - If the answer is not a PollAnswer or integer
        """
        try:
            self.answers.pop(int(answer_id) - 1)
        except IndexError:
            raise ValueError("Answer ID does not exist")
        except ValueError:
            raise ValueError("Answer must be an PollAnswer or integer")

        # Make sure IDs are in order
        for i, a in enumerate(self.answers, start=1):
            a.id = i

    def to_dict(self) -> dict:
        """ The poll as a dictionary. """
        return {
            "question": {"text": self.text},
            "answers": [a.to_dict() for a in self.answers],
            "duration": self.duration,
            "allow_multiselect": self.allow_multiselect,
            "layout_type": self.layout_type
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """ Create a poll from a dictionary. """
        poll = cls(
            text=data["question"]["text"],
            allow_multiselect=data["allow_multiselect"],
        )

        poll.answers = [PollAnswer.from_dict(a) for a in data["answers"]]

        if data.get("expiry"):
            poll.expiry = utils.parse_time(data["expiry"])

        results = data.get("results", {})
        poll.is_finalized = results.get("is_finalized", False)

        for g in results.get("answer_counts", []):
            find_answer = next(
                (a for a in poll.answers if a.id == g["id"]),
                None
            )

            if not find_answer:
                continue

            find_answer.count = g["count"]
            find_answer.me_voted = g["me_voted"]

        return poll


class MessageReference:
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self._state = state

        self.type: MessageReferenceType = MessageReferenceType(data["type"])
        self.guild_id: int | None = utils.get_int(data, "guild_id")
        self.channel_id: int | None = utils.get_int(data, "channel_id")
        self.message_id: int | None = utils.get_int(data, "message_id")

    def __repr__(self) -> str:
        return (
            f"<MessageReference guild_id={self.guild_id} channel_id={self.channel_id} "
            f"message_id={self.message_id}>"
        )

    @property
    def jump_url(self) -> JumpURL:
        """ The jump URL of the message. """
        return JumpURL(
            state=self._state,
            url=f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}/{self.message_id}"
        )

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ The guild the message was sent in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(
            state=self._state,
            id=self.guild_id
        )

    @property
    def channel(self) -> "PartialChannel | None":
        """ Returns the channel the message was sent in. """
        if not self.channel_id:
            return None

        if self.guild_id:
            cache = self._state.cache.get_channel_thread(
                guild_id=self.guild_id,
                channel_id=self.channel_id
            )

            if cache:
                return cache

        from .channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    @property
    def message(self) -> "PartialMessage | None":
        """ Returns the message if a message_id and channel_id is available. """
        if not self.channel_id or not self.message_id:
            return None

        return PartialMessage(
            state=self._state,
            channel_id=self.channel_id,
            guild_id=self.guild_id,
            id=self.message_id
        )

    def to_dict(self) -> dict:
        """ Returns the message reference as a dictionary. """
        payload = {}

        if self.guild_id:
            payload["guild_id"] = self.guild_id
        if self.channel_id:
            payload["channel_id"] = self.channel_id
        if self.message_id:
            payload["message_id"] = self.message_id
        if self.type:
            payload["type"] = int(self.type)

        return payload


class Attachment:
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self._state = state

        self.id: int = int(data["id"])
        self.filename: str = data["filename"]
        self.size: int = int(data["size"])
        self.url: str = data["url"]
        self.proxy_url: str = data["proxy_url"]
        self.ephemeral: bool = data.get("ephemeral", False)
        self.flags: AttachmentFlags = AttachmentFlags(data.get("flags", 0))

        self.content_type: str | None = data.get("content_type")
        self.title: str | None = data.get("title")
        self.description: str | None = data.get("description")

        self.height: int | None = data.get("height")
        self.width: int | None = data.get("width")
        self.ephemeral: bool = data.get("ephemeral", False)

        self.duration_secs: int | None = data.get("duration_secs")
        self.waveform: str | None = data.get("waveform")

    def __str__(self) -> str:
        return self.filename or ""

    def __int__(self) -> int:
        return self.id

    def __repr__(self) -> str:
        return (
            f"<Attachment id={self.id} filename='{self.filename}' "
            f"url='{self.url}'>"
        )

    def is_spoiler(self) -> bool:
        """ Whether the attachment is a spoiler or not. """
        return self.filename.startswith("SPOILER_")

    def is_voice_message(self) -> bool:
        """:class:`bool`: Whether this attachment is a voice message."""
        return self.duration_secs is not None and "voice-message" in self.url

    async def fetch(self, *, use_cached: bool = False) -> bytes:
        """
        Fetches the file from the attachment URL and returns it as bytes.

        Parameters
        ----------
        use_cached:
            Whether to use the cached URL or not, defaults to `False`

        Returns
        -------
            The attachment as bytes

        Raises
        ------
        `HTTPException`
            If the request returned anything other than 2XX
        """
        r = await self._state.http.request(
            "GET",
            self.proxy_url if use_cached else self.url,
            res_method="read"
        )

        if r.status not in range(200, 300):
            raise HTTPException(r)

        return r.response

    async def save(
        self,
        path: str,
        *,
        use_cached: bool = False
    ) -> int:
        """
        Fetches the file from the attachment URL and saves it locally to the path.

        Parameters
        ----------
        path:
            Path to save the file to, which includes the filename and extension.
            Example:
        use_cached:
            Whether to use the cached URL or not, defaults to `False`

        Returns
        -------
            The amount of bytes written to the file
        """
        data = await self.fetch(use_cached=use_cached)
        with open(path, "wb") as f:
            return f.write(data)

    async def to_file(
        self,
        *,
        filename: str | None = MISSING,
        spoiler: bool = False
    ) -> File:
        """
        Convert the attachment to a sendable File object for Message.send().

        Parameters
        ----------
        filename:
            Filename for the file, if empty, the attachment's filename will be used
        spoiler:
            Weather the file should be marked as a spoiler or not, defaults to `False`

        Returns
        -------
            The attachment as a File object
        """
        if filename is MISSING:
            filename = self.filename

        data = await self.fetch()

        return File(
            data=BytesIO(data),
            filename=str(filename),
            spoiler=spoiler,
            description=self.description
        )

    def to_dict(self) -> dict:
        """ The attachment as a dictionary. """
        data = {
            "id": self.id,
            "filename": self.filename,
            "size": self.size,
            "url": self.url,
            "proxy_url": self.proxy_url,
            "spoiler": self.is_spoiler(),
            "flags": self.flags
        }

        if self.title is not None:
            data["title"] = self.title
        if self.description is not None:
            data["description"] = self.description
        if self.height:
            data["height"] = self.height
        if self.width:
            data["width"] = self.width
        if self.content_type:
            data["content_type"] = self.content_type
        if self.duration_secs:
            data["duration_secs"] = self.duration_secs
        if self.waveform:
            data["waveform"] = self.waveform

        return data


class PartialMessage(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        channel_id: int,
        guild_id: int | None = None
    ):
        super().__init__(id=int(id))
        self._state = state

        self.channel_id: int = int(channel_id)
        self.guild_id: int | None = int(guild_id) if guild_id else None

    def __repr__(self) -> str:
        return f"<PartialMessage id={self.id}>"

    @property
    def channel(self) -> "BaseChannel | PartialChannel":
        """ Returns the channel the message was sent in. """
        if self.guild_id:
            cache = self._state.cache.get_channel_thread(
                guild_id=self.guild_id,
                channel_id=self.channel_id
            )

            if cache:
                return cache

        from .channel import PartialChannel
        return PartialChannel(
            state=self._state,
            id=self.channel_id,
            guild_id=self.guild_id
        )

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ Returns the guild the message was sent in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def jump_url(self) -> JumpURL:
        """ Returns the jump URL of the message, GuildID will always be @me. """
        return JumpURL(
            state=self._state,
            url=f"https://discord.com/channels/@me/{self.channel_id}/{self.id}"
        )

    async def fetch(self) -> "Message":
        """ Returns the message object. """
        r = await self._state.query(
            "GET",
            f"/channels/{self.channel.id}/messages/{self.id}"
        )

        return Message(
            state=self._state,
            data=r.response,
            guild=self.channel.guild
        )

    async def delete(
        self,
        *,
        delay: float | None = None,
        reason: str | None = None
    ) -> None:
        """
        Delete the message.

        Parameters
        ----------
        delay:
            How many seconds it should wait in background to delete
        reason:
            Reason for deleting the message
            (Only applies when deleting messages not made by yourself)
        """
        async def _delete() -> None:
            await self._state.query(
                "DELETE",
                f"/channels/{self.channel.id}/messages/{self.id}",
                reason=reason,
                res_method="text"
            )

        async def _delete_after(d: float) -> None:
            await asyncio.sleep(d)
            try:
                await _delete()
            except HTTPException:
                pass

        if delay is not None:
            asyncio.create_task(_delete_after(delay))  # noqa: RUF006
        else:
            await _delete()

    async def expire_poll(self) -> "Message":
        """
        Immediately end the poll, then returns new Message object.

        This can only be done if you created it

        Returns
        -------
            The message object of the poll
        """
        r = await self._state.query(
            "POST",
            f"/channels/{self.channel_id}/polls/{self.id}/expire"
        )

        return Message(
            state=self._state,
            data=r.response
        )

    async def fetch_poll_voters(
        self,
        answer: PollAnswer | int,
        after: Snowflake | int | None = None,
        limit: int | None = 100,
    ) -> AsyncIterator["User"]:
        """
        Fetch the users who voted for this answer.

        Parameters
        ----------
        answer:
            The answer to fetch the voters from
        after:
            The user ID to start fetching from
        limit:
            The amount of users to fetch, defaults to 100.
            `None` will fetch all users.

        Yields
        ------
        `User`
            User object of people who voted
        """
        answer_id = answer
        if isinstance(answer, PollAnswer):
            answer_id = answer.id

        async def _get_history(limit: int, **kwargs) -> "HTTPResponse[dict]":
            params = {"limit": min(limit, 100)}
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = int(value)

            return await self._state.query(
                "GET",
                f"/channels/{self.channel_id}/polls/"
                f"{self.id}/answers/{answer_id}",
                params=params
            )

        async def _after_http(
            http_limit: int,
            after_id: int | None,
            limit: int | None
        ) -> tuple[dict, int | None, int | None]:
            r = await _get_history(http_limit, after=after_id)
            if r.response:
                if limit is not None:
                    limit -= len(r.response["users"])
                after_id = r.response["users"][-1]["id"]
            return r.response, after_id, limit

        if after:
            strategy, state = _after_http, utils.normalize_entity_id(after)
        else:
            strategy, state = _after_http, None

        while True:
            http_limit: int = 100 if limit is None else min(limit, 100)
            if http_limit <= 0:
                break

            strategy: Callable
            users, state, limit = await strategy(http_limit, state, limit)

            i = 0
            for i, u in enumerate(users["users"], start=1):
                yield User(state=self._state, data=u)
                i += 1

            if i < 100:
                break

    async def edit(
        self,
        *,
        content: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        view: View | None = MISSING,
        attachment: File | None = MISSING,
        attachments: list[File] | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        flags: MessageFlags | None = MISSING
    ) -> "Message":
        """
        Edit the message.

        Parameters
        ----------
        content:
            Content of the message
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        view:
            Components of the message
        attachment:
            New attachment of the message
        attachments:
            New attachments of the message
        allowed_mentions:
            Allowed mentions of the message
        flags:
            Flags of the message

        Returns
        -------
            The edited message
        """
        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            attachment=attachment,
            attachments=attachments,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            ),
        )

        r = await self._state.query(
            "PATCH",
            f"/channels/{self.channel.id}/messages/{self.id}",
            headers={"Content-Type": payload.content_type},
            data=payload.to_multipart(is_request=True),
        )

        return Message(
            state=self._state,
            data=r.response,
            guild=self.channel.guild
        )

    async def publish(self) -> "Message":
        """ Crosspost the message to another channel. """
        r = await self._state.query(
            "POST",
            f"/channels/{self.channel.id}/messages/{self.id}/crosspost",
            res_method="json"
        )

        return Message(
            state=self._state,
            data=r.response,
            guild=self.channel.guild
        )

    async def reply(
        self,
        content: str | None = MISSING,
        *,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        view: View | None = MISSING,
        tts: bool | None = False,
        allowed_mentions: AllowedMentions | None = MISSING,
    ) -> "Message":
        """
        Sends a reply to a message in a channel.

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
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            ),
            message_reference=MessageReference(
                state=self._state,
                data={
                    "type": int(MessageReferenceType.default),
                    "channel_id": self.channel_id,
                    "message_id": self.id,
                }
            )
        )

        r = await self._state.query(
            "POST",
            f"/channels/{self.channel_id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        return Message(
            state=self._state,
            data=r.response
        )

    async def pin(self, *, reason: str | None = None) -> None:
        """
        Pin the message.

        Parameters
        ----------
        reason:
            Reason for pinning the message
        """
        await self._state.query(
            "PUT",
            f"/channels/{self.channel.id}/pins/{self.id}",
            res_method="text",
            reason=reason
        )

    async def unpin(self, *, reason: str | None = None) -> None:
        """
        Unpin the message.

        Parameters
        ----------
        reason:
            Reason for unpinning the message
        """
        await self._state.query(
            "DELETE",
            f"/channels/{self.channel.id}/pins/{self.id}",
            res_method="text",
            reason=reason
        )

    async def add_reaction(self, emoji: str) -> None:
        """
        Add a reaction to the message.

        Parameters
        ----------
        emoji:
            Emoji to add to the message
        """
        parsed = EmojiParser(emoji).to_reaction()
        await self._state.query(
            "PUT",
            f"/channels/{self.channel.id}/messages/{self.id}/reactions/{parsed}/@me",
            res_method="text"
        )

    async def remove_reaction(
        self,
        emoji: str,
        *,
        user_id: int | None = None
    ) -> None:
        """
        Remove a reaction from the message.

        Parameters
        ----------
        emoji:
            Emoji to remove from the message
        user_id:
            User ID to remove the reaction from
        """
        parsed = EmojiParser(emoji).to_reaction()
        url = (
            f"/channels/{self.channel.id}/messages/{self.id}/reactions/{parsed}"
            f"/{user_id}" if user_id is not None else "/@me"
        )

        await self._state.query(
            "DELETE",
            url,
            res_method="text"
        )

    async def remove_all_reactions(self) -> None:
        """ Remove all reactions from the message. """
        await self._state.query(
            "DELETE",
            f"/channels/{self.channel.id}/messages/{self.id}/reactions",
            res_method="text"
        )

    async def create_public_thread(
        self,
        name: str,
        *,
        auto_archive_duration: int | None = 60,
        rate_limit_per_user: timedelta | int | None = None,
        reason: str | None = None
    ) -> "PublicThread":
        """
        Create a public thread from the message.

        Parameters
        ----------
        name:
            Name of the thread
        auto_archive_duration:
            Duration in minutes to automatically archive the thread after recent activity,
        rate_limit_per_user:
            A per-user rate limit for this thread (0-21600 seconds, default 0)
        reason:
            Reason for creating the thread

        Returns
        -------
            The created thread

        Raises
        ------
        `ValueError`
            - If `auto_archive_duration` is not 60, 1440, 4320 or 10080
            - If `rate_limit_per_user` is not between 0 and 21600 seconds
        """
        payload = {
            "name": name,
            "auto_archive_duration": auto_archive_duration,
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
            f"/channels/{self.channel.id}/messages/{self.id}/threads",
            json=payload,
            reason=reason
        )

        from .channel import PublicThread
        return PublicThread(
            state=self._state,
            data=r.response
        )


class MessageSnapshot:
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        self._state = state
        self._message: dict = data.get("message", {})

        self.type: MessageType = MessageType(self._message.get("type", 0))
        self.content: str = self._message.get("content", "")

        self.timestamp: datetime | None = None
        self.edited_timestamp: datetime | None = None

        self.embeds: list[Embed] = [
            Embed.from_dict(embed)
            for embed in self._message.get("embeds", [])
        ]

        self.attachments: list[Attachment] = [
            Attachment(state=state, data=a)
            for a in self._message.get("attachments", [])
        ]

        self._from_data(data)

    def _from_data(self, data: dict) -> None:  # noqa: ARG002
        if self._message.get("edited_timestamp", None):
            self.edited_timestamp = utils.parse_time(
                self._message["edited_timestamp"]
            )

        if self._message.get("timestamp", None):
            self.timestamp = utils.parse_time(
                self._message["timestamp"]
            )


class Message(PartialMessage):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | None" = None
    ):
        super().__init__(
            state=state,
            id=int(data["id"]),
            channel_id=int(data["channel_id"]),
            guild_id=guild.id if guild else None
        )

        self.type: MessageType = MessageType(data["type"])
        self.content: str = data.get("content", "")
        self.author: "User | Member" = User(state=state, data=data["author"])
        self.pinned: bool = data.get("pinned", False)
        self.mention_everyone: bool = data.get("mention_everyone", False)
        self.tts: bool = data.get("tts", False)
        self.poll: Poll | None = None

        self.embeds: list[Embed] = [
            Embed.from_dict(embed)
            for embed in data.get("embeds", [])
        ]

        self.attachments: list[Attachment] = [
            Attachment(state=state, data=a)
            for a in data.get("attachments", [])
        ]

        self.stickers: list[PartialSticker] = [
            PartialSticker(state=state, id=int(s["id"]), name=s["name"])
            for s in data.get("sticker_items", [])
        ]

        self.reactions: list[MessageReaction] = [
            MessageReaction(state=state, message=self, data=g)
            for g in data.get("reactions", [])
        ]

        self.mentions: list["Member | User"] = []

        self.view: View | None = None
        self.edited_timestamp: datetime | None = None

        self.reference: MessageReference | None = None

        self.resolved_reply: Message | None = None
        self.resolved_forward: list[MessageSnapshot] = []

        self.interaction: MessageInteraction | None = None

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Message id={self.id} author={self.author}>"

    def __str__(self) -> str:
        return self.content or ""

    def _from_data(self, data: dict) -> None:
        if data.get("components"):
            self.view = View.from_dict(
                state=self._state,
                data=data
            )

        if data.get("message_reference"):
            self.reference = MessageReference(
                state=self._state,
                data=data["message_reference"]
            )

        if data.get("referenced_message"):
            self.resolved_reply = Message(
                state=self._state,
                data=data["referenced_message"],
                guild=self.guild
            )

        if data.get("interaction_metadata"):
            self.interaction = MessageInteraction(
                state=self._state,
                data=data["interaction_metadata"]
            )

        for m in data.get("message_snapshots", []):
            self.resolved_forward.append(
                MessageSnapshot(
                    state=self._state,
                    data=m
                )
            )

        if data.get("poll"):
            self.poll = Poll.from_dict(data["poll"])

        if data.get("edited_timestamp"):
            self.edited_timestamp = utils.parse_time(data["edited_timestamp"])

        if data.get("member"):
            from .member import Member

            # Append author data to member data
            data["member"]["user"] = data["author"]

            self.author = Member(
                state=self._state,
                guild=self.guild,  # type: ignore
                data=data["member"]
            )

        if data.get("mentions"):
            from .member import Member

            for m in data["mentions"]:
                if m.get("member", None) and self.guild_id:
                    # This is only done through the gateway
                    fake_member = m["member"]
                    fake_member["user"] = m
                    self.mentions.append(
                        Member(
                            state=self._state,
                            guild=self.guild,  # type: ignore
                            data=fake_member
                        )
                    )

                else:
                    self.mentions.append(
                        User(state=self._state, data=m)
                    )

    def is_system(self) -> bool:
        """ Returns whether the message is a system message. """
        return self.type not in (
            MessageType.default,
            MessageType.reply,
            MessageType.chat_input_command,
            MessageType.context_menu_command,
            MessageType.thread_starter_message
        )

    @property
    def emojis(self) -> list[EmojiParser]:
        """ Returns the emojis in the message. """
        return [
            EmojiParser(f"<{e[0]}:{e[1]}:{e[2]}>")
            for e in utils.re_emoji.findall(self.content)
        ]

    @property
    def jump_url(self) -> JumpURL:
        """ Returns the jump URL of the message. """
        return JumpURL(
            state=self._state,
            url=f"https://discord.com/channels/{self.guild_id or '@me'}/{self.channel_id}/{self.id}"
        )

    @property
    def role_mentions(self) -> list[Role | PartialRole]:
        """
        Returns the role mentions in the message.

        Can return full role object if guild and role cache is enabled
        """
        if not self.guild_id:
            return []

        return [
            self.guild.get_role(int(role_id)) or
            PartialRole(
                state=self._state,
                id=int(role_id),
                guild_id=self.guild_id
            )
            for role_id in utils.re_role.findall(self.content)
        ]

    @property
    def channel_mentions(self) -> list["BaseChannel | PartialChannel"]:
        """
        Returns the channel mentions in the message.

        Can return full role object if guild and channel cache is enabled
        """
        from .channel import PartialChannel

        return [
            self.guild.get_channel(int(channel_id)) or
            PartialChannel(state=self._state, id=int(channel_id))
            for channel_id in utils.re_channel.findall(self.content)
        ]

    @property
    def jump_urls(self) -> list[JumpURL]:
        """ Returns the jump URLs in the message. """
        return [
            JumpURL(
                state=self._state,
                guild_id=int(gid) if gid != "@me" else None,
                channel_id=int(cid),
                message_id=int(mid) if mid else None
            )
            for gid, cid, mid in utils.re_jump_url.findall(self.content)
        ]


class WebhookMessage(Message):
    def __init__(self, *, state: "DiscordAPI", data: dict, application_id: int, token: str):
        super().__init__(state=state, data=data)
        self.application_id = int(application_id)
        self.token = token

    async def edit(
        self,
        *,
        content: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        attachment: File | None = MISSING,
        attachments: list[File] | None = MISSING,
        view: View | None = MISSING,
        flags: MessageFlags | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING
    ) -> "WebhookMessage":
        """
        Edit the webhook message.

        Parameters
        ----------
        content:
            Content of the message
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        attachment:
            Attachment of the message
        attachments:
            Attachments of the message
        view:
            Components of the message
        allowed_mentions:
            Allowed mentions of the message
        flags:
            Flags of the message

        Returns
        -------
            The edited message
        """
        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            attachment=attachment,
            attachments=attachments,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            ),
        )

        r = await self._state.query(
            "PATCH",
            f"/webhooks/{self.application_id}/{self.token}/messages/{self.id}",
            webhook=True,
            headers={"Content-Type": payload.content_type},
            data=payload.to_multipart(is_request=True),
        )

        return WebhookMessage(
            state=self._state,
            data=r.response,
            application_id=self.application_id,
            token=self.token
        )

    async def delete(
        self,
        *,
        delay: float | None = None,
        reason: str | None = None
    ) -> None:
        """
        Delete the webhook message.

        Parameters
        ----------
        delay:
            How many seconds it should wait in background to delete.
        reason:
            Reason for deleting the message.
        """
        async def _delete() -> None:
            await self._state.query(
                "DELETE",
                f"/webhooks/{self.application_id}/{self.token}/messages/{self.id}",
                reason=reason,
                webhook=True,
                res_method="text"
            )

        async def _delete_after(d: float) -> None:
            await asyncio.sleep(d)
            try:
                await _delete()
            except HTTPException:
                pass

        if delay is not None:
            asyncio.create_task(_delete_after(delay))  # noqa: RUF006
        else:
            await _delete()
