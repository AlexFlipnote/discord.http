import inspect
import logging
import asyncio

from typing import TYPE_CHECKING, Callable, Union, Optional, Any, Self
from datetime import datetime, timedelta

from . import utils
from .channel import (
    TextChannel, DMChannel, VoiceChannel,
    GroupDMChannel, CategoryChannel, NewsThread,
    PublicThread, PrivateThread, StageChannel,
    DirectoryChannel, ForumChannel, StoreChannel,
    NewsChannel, BaseChannel, PartialChannel
)
from .cooldowns import Cooldown
from .embeds import Embed
from .errors import CheckFailed
from .entitlements import Entitlements
from .enums import (
    ApplicationCommandType, CommandOptionType,
    ResponseType, ChannelType, InteractionType
)
from .file import File
from .multipart import MultipartData
from .flags import Permissions, MessageFlags
from .guild import Guild, PartialGuild
from .member import Member
from .mentions import AllowedMentions
from .message import Message, Attachment, Poll
from .response import (
    MessageResponse, DeferResponse,
    AutocompleteResponse, ModalResponse,
    EmptyResponse
)
from .role import Role
from .user import User
from .view import View, Modal
from .webhook import Webhook

if TYPE_CHECKING:
    from .client import Client
    from .commands import Command

_log = logging.getLogger(__name__)

MISSING = utils.MISSING

channel_types = {
    int(ChannelType.guild_text): TextChannel,
    int(ChannelType.dm): DMChannel,
    int(ChannelType.guild_voice): VoiceChannel,
    int(ChannelType.group_dm): GroupDMChannel,
    int(ChannelType.guild_category): CategoryChannel,
    int(ChannelType.guild_news): NewsChannel,
    int(ChannelType.guild_store): StoreChannel,
    int(ChannelType.guild_news_thread): NewsThread,
    int(ChannelType.guild_public_thread): PublicThread,
    int(ChannelType.guild_private_thread): PrivateThread,
    int(ChannelType.guild_stage_voice): StageChannel,
    int(ChannelType.guild_directory): DirectoryChannel,
    int(ChannelType.guild_forum): ForumChannel,
}

__all__ = (
    "Context",
    "InteractionResponse",
)


class _ResolveParser:
    def __init__(self, ctx: "Context", data: dict):
        self._parsed_data = {
            "members": [], "users": [],
            "channels": [], "roles": [],
            "strings": [],
        }

        self._from_data(ctx, data)

    def _from_data(self, ctx: "Context", data: dict):
        self._parsed_data["strings"] = data.get("data", {}).get("values", [])

        _resolved = data.get("data", {}).get("resolved", {})
        data_to_resolve = ["members", "users", "channels", "roles"]

        for key in data_to_resolve:
            self._parse_resolved(ctx, key, _resolved)

    @classmethod
    def none(cls, ctx: "Context") -> Self:
        """ `SelectValues`: with no values """
        return cls(ctx, {})

    def is_empty(self) -> bool:
        """ `bool`: Whether no values were selected """
        return not any(self._parsed_data.values())

    def _parse_resolved(self, ctx: "Context", key: str, data: dict):
        if not data.get(key, {}):
            return None

        for g in data[key]:
            if key == "members":
                data["members"][g]["user"] = data["users"][g]

            to_append: list = self._parsed_data[key]
            _data = data[key][g]

            match key:
                case "members":
                    if not ctx.guild:
                        raise ValueError("While parsing members, guild object was not available")
                    to_append.append(Member(state=ctx.bot.state, guild=ctx.guild, data=_data))

                case "users":
                    to_append.append(User(state=ctx.bot.state, data=_data))

                case "channels":
                    to_append.append(channel_types[_data["type"]](state=ctx.bot.state, data=_data))

                case "roles":
                    if not ctx.guild:
                        raise ValueError("While parsing roles, guild object was not available")
                    to_append.append(Role(state=ctx.bot.state, guild=ctx.guild, data=_data))

                case _:
                    pass


class ResolvedValues(_ResolveParser):
    def __init__(self, ctx: "Context", data: dict):
        super().__init__(ctx, data)

    @property
    def members(self) -> list[Member]:
        """ `List[Member]`: of members resolved """
        return self._parsed_data["members"]

    @property
    def users(self) -> list[User]:
        """ `List[User]`: of users resolved """
        return self._parsed_data["users"]

    @property
    def channels(self) -> list[BaseChannel]:
        """ `List[BaseChannel]`: of channels resolved """
        return self._parsed_data["channels"]

    @property
    def roles(self) -> list[Role]:
        """ `List[Role]`: of roles resolved """
        return self._parsed_data["roles"]


class SelectValues(ResolvedValues):
    def __init__(self, ctx: "Context", data: dict):
        super().__init__(ctx, data)

    @property
    def strings(self) -> list[str]:
        """ `List[str]`: of strings selected """
        return self._parsed_data["strings"]


class InteractionResponse:
    def __init__(self, parent: "Context"):
        self._parent = parent

    def pong(self) -> dict:
        """
        Only used to acknowledge a ping from
        Discord Developer portal Interaction URL
        """
        return {"type": 1}

    def defer(
        self,
        ephemeral: bool = False,
        thinking: bool = False,
        flags: MessageFlags | None = MISSING,
        call_after: Callable | None = None
    ) -> DeferResponse:
        """
        Defer the response to the interaction

        Parameters
        ----------
        ephemeral: `bool`
            If the response should be ephemeral (show only to the user)
        thinking: `bool`
            If the response should show the "thinking" status
        flags: `Optional[int]`
            The flags of the message (overrides ephemeral)
        call_after: `Optional[Callable]`
            A coroutine to run after the response is sent

        Returns
        -------
        `DeferResponse`
            The response to the interaction

        Raises
        ------
        `TypeError`
            If `call_after` is not a coroutine
        """
        if call_after:
            if not inspect.iscoroutinefunction(call_after):
                raise TypeError("call_after must be a coroutine")

            self._parent.bot.loop.create_task(
                self._parent._background_task_manager(call_after)
            )

        return DeferResponse(ephemeral=ephemeral, thinking=thinking, flags=flags)

    def send_modal(
        self,
        modal: Modal,
        *,
        call_after: Optional[Callable] = None
    ) -> ModalResponse:
        """
        Send a modal to the interaction

        Parameters
        ----------
        modal: `Modal`
            The modal to send
        call_after: `Optional[Callable]`
            A coroutine to run after the response is sent

        Returns
        -------
        `ModalResponse`
            The response to the interaction

        Raises
        ------
        `TypeError`
            - If `modal` is not a `Modal` instance
            - If `call_after` is not a coroutine
        """
        if not isinstance(modal, Modal):
            raise TypeError("modal must be a Modal instance")

        if call_after:
            if not inspect.iscoroutinefunction(call_after):
                raise TypeError("call_after must be a coroutine")

            self._parent.bot.loop.create_task(
                self._parent._background_task_manager(call_after)
            )

        return ModalResponse(modal=modal)

    def send_empty(
        self,
        *,
        call_after: Optional[Callable] = None
    ) -> EmptyResponse:
        """
        Send an empty response to the interaction

        Parameters
        ----------
        call_after: `Optional[Callable]`
            A coroutine to run after the response is sent

        Returns
        -------
        `EmptyResponse`
            The response to the interaction
        """
        if call_after:
            if not inspect.iscoroutinefunction(call_after):
                raise TypeError("call_after must be a coroutine")

            self._parent.bot.loop.create_task(
                self._parent._background_task_manager(call_after)
            )

        return EmptyResponse()

    def send_message(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        ephemeral: Optional[bool] = False,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        poll: Optional[Poll] = MISSING,
        flags: Optional[MessageFlags] = MISSING,
        call_after: Optional[Callable] = None
    ) -> MessageResponse:
        """
        Send a message to the interaction

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        embed: `Optional[Embed]`
            The embed to send
        embeds: `Optional[list[Embed]]`
            Multiple embeds to send
        file: `Optional[File]`
            A file to send
        files: `Optional[Union[list[File], File]]`
            Multiple files to send
        ephemeral: `bool`
            If the message should be ephemeral (show only to the user)
        view: `Optional[View]`
            Components to include in the message
        tts: `bool`
            Whether the message should be sent using text-to-speech
        type: `Optional[ResponseType]`
            The type of response to send
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions for the message
        flags: `Optional[int]`
            The flags of the message (overrides ephemeral)
        call_after: `Optional[Callable]`
            A coroutine to run after the response is sent

        Returns
        -------
        `MessageResponse`
            The response to the interaction

        Raises
        ------
        `ValueError`
            - If both `embed` and `embeds` are passed
            - If both `file` and `files` are passed
        `TypeError`
            If `call_after` is not a coroutine
        """
        if call_after:
            if not inspect.iscoroutinefunction(call_after):
                raise TypeError("call_after must be a coroutine")

            self._parent.bot.loop.create_task(
                self._parent._background_task_manager(call_after)
            )

        if embed is not MISSING and embeds is not MISSING:
            raise ValueError("Cannot pass both embed and embeds")
        if file is not MISSING and files is not MISSING:
            raise ValueError("Cannot pass both file and files")

        if isinstance(embed, Embed):
            embeds = [embed]
        if isinstance(file, File):
            files = [file]

        return MessageResponse(
            content=content,
            embeds=embeds,
            ephemeral=ephemeral,
            view=view,
            tts=tts,
            attachments=files,
            type=type,
            poll=poll,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self._parent.bot._default_allowed_mentions
            )
        )

    def edit_message(
        self,
        *,
        content: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        view: Optional[View] = MISSING,
        attachment: Optional[File] = MISSING,
        attachments: Optional[list[File]] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        flags: Optional[MessageFlags] = MISSING,
        call_after: Optional[Callable] = None
    ) -> MessageResponse:
        """
        Edit the original message of the interaction

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        embed: `Optional[Embed]`
            Embed to edit the message with
        embeds: `Optional[list[Embed]]`
            Multiple embeds to edit the message with
        view: `Optional[View]`
            Components to include in the message
        attachment: `Optional[File]`
            New file to edit the message with
        attachments: `Optional[Union[list[File], File]]`
            Multiple new files to edit the message with
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions for the message
        flags: `Optional[int]`
            The flags of the message
        call_after: `Optional[Callable]`
            A coroutine to run after the response is sent

        Returns
        -------
        `MessageResponse`
            The response to the interaction

        Raises
        ------
        `ValueError`
            - If both `embed` and `embeds` are passed
            - If both `attachment` and `attachments` are passed
        `TypeError`
            If `call_after` is not a coroutine
        """
        if call_after:
            if not inspect.iscoroutinefunction(call_after):
                raise TypeError("call_after must be a coroutine")

            self._parent.bot.loop.create_task(
                self._parent._background_task_manager(call_after)
            )

        if embed is not MISSING and embeds is not MISSING:
            raise ValueError("Cannot pass both embed and embeds")
        if attachment is not MISSING and attachments is not MISSING:
            raise ValueError("Cannot pass both attachment and attachments")

        if isinstance(embed, Embed):
            embeds = [embed]
        if isinstance(attachment, File):
            attachments = [attachment]

        return MessageResponse(
            content=content,
            embeds=embeds,
            attachments=attachments,
            view=view,
            type=int(ResponseType.update_message),
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self._parent.bot._default_allowed_mentions
            )
        )

    def send_autocomplete(
        self,
        choices: dict[Any, str]
    ) -> AutocompleteResponse:
        """
        Send an autocomplete response to the interaction

        Parameters
        ----------
        choices: `dict[Union[str, int, float], str]`
            The choices to send

        Returns
        -------
        `AutocompleteResponse`
            The response to the interaction

        Raises
        ------
        `TypeError`
            - If `choices` is not a `dict`
            - If `choices` is not a `dict[Union[str, int, float], str]`
        """
        if not isinstance(choices, dict):
            raise TypeError("choices must be a dict")

        for k, v in choices.items():
            if (
                not isinstance(k, str) and
                not isinstance(k, int) and
                not isinstance(k, float)
            ):
                raise TypeError(
                    f"key {k} must be a string, got {type(k)}"
                )

            if (isinstance(k, int) or isinstance(k, float)) and k >= 2**53:
                _log.warning(
                    f"'{k}: {v}' (int) is too large, "
                    "Discord might ignore it and make autocomplete fail"
                )

            if not isinstance(v, str):
                raise TypeError(
                    f"value {v} must be a string, got {type(v)}"
                )

        return AutocompleteResponse(choices)


class Context:
    def __init__(
        self,
        bot: "Client",
        data: dict
    ):
        self.bot = bot

        self.id: int = int(data["id"])

        self.type: InteractionType = InteractionType(data["type"])
        self.command_type: ApplicationCommandType = ApplicationCommandType(
            data.get("data", {}).get("type", ApplicationCommandType.chat_input)
        )

        # Arguments that gets parsed on runtime
        self.command: Optional["Command"] = None

        self.app_permissions: Permissions = Permissions(int(data.get("app_permissions", 0)))
        self.custom_id: Optional[str] = data.get("data", {}).get("custom_id", None)

        self.resolved: ResolvedValues = ResolvedValues.none(self)
        self.select_values: SelectValues = SelectValues.none(self)
        self.modal_values: dict[str, str] = {}

        self.options: list[dict] = data.get("data", {}).get("options", [])
        self.followup_token: str = data.get("token", None)

        self._original_response: Optional[Message] = None
        self._raw_resolved: dict = data.get("data", {}).get("resolved", {})

        self.entitlements: list[Entitlements] = [
            Entitlements(state=self.bot.state, data=g)
            for g in data.get("entitlements", [])
        ]

        self.last_message_id: int | None = None
        if data.get("channel", {}).get("last_message_id", None):
            self.last_message_id = int(data["channel"]["last_message_id"])

        self.recipients: list[User] = [
            User(state=self.bot.state, data=g)
            for g in data.get("channel", {}).get("recipients", [])
        ]

        # Should not be used, but if you *really* want the raw data, here it is
        self._data: dict = data

        self._from_data(data)

    def _from_data(self, data: dict):
        self.channel_id: Optional[int] = None
        if data.get("channel_id", None):
            self.channel_id = int(data["channel_id"])

        self._guild: Optional[PartialGuild] = None
        if data.get("guild_id", None):
            self._guild = PartialGuild(
                state=self.bot.state,
                id=int(data["guild_id"])
            )

        self._channel: Optional[BaseChannel] = None
        if data.get("channel", None):
            _channel_data = data["channel"]
            if self._guild:
                _channel_data["guild_id"] = self._guild.id

            self._channel = channel_types[_channel_data["type"]](
                state=self.bot.state,
                data=_channel_data
            )

        self.message: Optional[Message] = None
        if data.get("message", None):
            self.message = Message(
                state=self.bot.state,
                data=data["message"],
                guild=self._guild
            )
        elif self._raw_resolved.get("messages", {}):
            _first_msg = next(iter(self._raw_resolved["messages"].values()), None)
            if _first_msg:
                self.message = Message(
                    state=self.bot.state,
                    data=_first_msg,
                    guild=self._guild
                )

        if self._raw_resolved:
            self.resolved = ResolvedValues(self, data)

        self.author: Optional[Union[Member, User]] = None
        if self.message is not None:
            self.author = self.message.author

        self.user: Union[Member, User] = self._parse_user(data)

        match self.type:
            case InteractionType.message_component:
                self.select_values = SelectValues(self, data)

            case InteractionType.modal_submit:
                for comp in data["data"]["components"]:
                    ans = comp["components"][0]
                    self.modal_values[ans["custom_id"]] = ans["value"]

    async def _background_task_manager(self, call_after: Callable) -> None:
        try:
            if isinstance(self.bot.call_after_delay, float):
                await asyncio.sleep(self.bot.call_after_delay)
                # Somehow, Discord thinks @original messages is HTTP 404
                # Give them a smaaaall chance to fix it
            await call_after()
        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", self, e)
            else:
                _log.error(
                    f"Error while running call_after:{call_after}",
                    exc_info=e
                )

    @property
    def guild(self) -> Guild | PartialGuild | None:
        """
        `Guild | PartialGuild | None`: Returns the guild the interaction was made in
        If you are using gateway cache, it can return full object too
        """
        if not self._guild:
            return None

        cache = self.bot.cache.get_guild(self._guild.id)
        if cache:
            return cache

        return self._guild

    @property
    def channel(self) -> "BaseChannel | PartialChannel | None":
        """ `BaseChannel | PartialChannel`: Returns the channel the interaction was made in """
        if not self.channel_id:
            return None

        if self.guild:
            cache = self.bot.cache.get_channel_thread(
                guild_id=self.guild.id,
                channel_id=self.channel_id
            )

            if cache:
                return cache

        if self._channel:
            # Prefer the channel from context
            return self._channel

        return PartialChannel(
            state=self.bot.state,
            id=self.channel_id,
            guild_id=self.guild.id if self.guild else None
        )

    @property
    def channel_type(self) -> ChannelType:
        """ `ChannelType` Returns the type of the channel """
        if self._channel:
            return self._channel.type
        return ChannelType.unknown

    @property
    def created_at(self) -> datetime:
        """ `datetime` Returns the time the interaction was created """
        return utils.snowflake_time(self.id)

    @property
    def cooldown(self) -> Optional[Cooldown]:
        """ `Optional[Cooldown]` Returns the context cooldown """
        _cooldown = self.command.cooldown

        if _cooldown is None:
            return None

        return _cooldown.get_bucket(
            self, self.created_at.timestamp()
        )

    @property
    def expires_at(self) -> datetime:
        """ `datetime` Returns the time the interaction expires """
        return self.created_at + timedelta(minutes=15)

    def is_expired(self) -> bool:
        """ `bool` Returns whether the interaction is expired """
        return utils.utcnow() >= self.expires_at

    @property
    def response(self) -> InteractionResponse:
        """ `InteractionResponse` Returns the response to the interaction """
        return InteractionResponse(self)

    @property
    def followup(self) -> Webhook:
        """ `Webhook` Returns the followup webhook object """
        payload = {
            "application_id": self.bot.application_id,
            "token": self.followup_token,
            "type": 3,
        }

        return Webhook.from_state(
            state=self.bot.state,
            data=payload
        )

    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        ephemeral: Optional[bool] = False,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        poll: Optional[Poll] = MISSING,
        flags: Optional[MessageFlags] = MISSING,
        delete_after: Optional[float] = None
    ) -> Message:
        """
        Send a message after responding with an empty response in the initial interaction

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        embed: `Optional[Embed]`
            Embed of the message
        embeds: `Optional[list[Embed]]`
            Embeds of the message
        file: `Optional[File]`
            File of the message
        files: `Optional[Union[list[File], File]]`
            Files of the message
        ephemeral: `bool`
            Whether the message should be sent as ephemeral
        view: `Optional[View]`
            Components of the message
        type: `Optional[ResponseType]`
            Which type of response should be sent
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions of the message
        wait: `bool`
            Whether to wait for the message to be sent
        thread_id: `Optional[int]`
            Thread ID to send the message to
        poll: `Optional[Poll]`
            Poll to send with the message
        flags: `Optional[MessageFlags]`
            Flags of the message
        delete_after: `Optional[float]`
            How long to wait before deleting the message

        Returns
        -------
        `Message`
            Returns the message that was sent
        """
        if embed is not MISSING and embeds is not MISSING:
            raise ValueError("Cannot pass both embed and embeds")
        if file is not MISSING and files is not MISSING:
            raise ValueError("Cannot pass both file and files")

        if isinstance(embed, Embed):
            embeds = [embed]
        if isinstance(file, File):
            files = [file]

        payload = MessageResponse(
            content=content,
            embeds=embeds,
            ephemeral=ephemeral,
            view=view,
            tts=tts,
            attachments=files,
            type=type,
            poll=poll,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self.bot._default_allowed_mentions
            )
        )

        multidata = MultipartData()

        if isinstance(payload.files, list):
            for i, file in enumerate(payload.files):
                multidata.attach(
                    f"file{i}",
                    file,  # type: ignore
                    filename=file.filename
                )

        _modified_payload = payload.to_dict()
        multidata.attach("payload_json", _modified_payload)

        r = await self.bot.state.query(
            "POST",
            f"/interactions/{self.id}/{self.followup_token}/callback",
            data=multidata.finish(),
            params={"with_response": "true"},
            headers={"Content-Type": multidata.content_type}
        )

        _msg = Message(
            state=self.bot.state,
            data=r.response["resource"]["message"],
            guild=self.guild
        )

        if delete_after is not None:
            await _msg.delete(delay=float(delete_after))
        return _msg

    async def original_response(self) -> Message:
        """ `Message` Returns the original response to the interaction """
        if self._original_response is not None:
            return self._original_response

        r = await self.bot.state.query(
            "GET",
            f"/webhooks/{self.bot.application_id}/{self.followup_token}/messages/@original",
            retry_codes=[404]
        )

        msg = Message(
            state=self.bot.state,
            data=r.response,
            guild=self.guild
        )

        self._original_response = msg
        return msg

    async def edit_original_response(
        self,
        *,
        content: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        view: Optional[View] = MISSING,
        attachment: Optional[File] = MISSING,
        attachments: Optional[list[File]] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING
    ) -> Message:
        """ `Message` Edit the original response to the interaction """
        payload = MessageResponse(
            content=content,
            embeds=embeds,
            embed=embed,
            attachment=attachment,
            attachments=attachments,
            view=view,
            allowed_mentions=allowed_mentions
        )

        r = await self.bot.state.query(
            "PATCH",
            f"/webhooks/{self.bot.application_id}/{self.followup_token}/messages/@original",
            headers={"Content-Type": payload.content_type},
            data=payload.to_multipart(is_request=True),
            retry_codes=[404]
        )

        msg = Message(
            state=self.bot.state,
            data=r.response,
            guild=self.guild
        )

        self._original_response = msg
        return msg

    async def delete_original_response(self) -> None:
        """ Delete the original response to the interaction """
        await self.bot.state.query(
            "DELETE",
            f"/webhooks/{self.bot.application_id}/{self.followup_token}/messages/@original",
            retry_codes=[404]
        )

    async def _create_args(self) -> tuple[list[Union[Member, User, Message, None]], dict]:
        match self.command_type:
            case ApplicationCommandType.chat_input:
                return [], await self._create_args_chat_input()

            case ApplicationCommandType.user:
                if self.resolved.members:
                    _first: Optional[dict] = next(
                        iter(self._raw_resolved["members"].values()),
                        None
                    )

                    if not _first:
                        raise ValueError("User command detected members, but was unable to parse it")
                    if not self.guild:
                        raise ValueError("While parsing members, guild was not available")

                    _first["user"] = next(
                        iter(self._raw_resolved["users"].values()),
                        None
                    )

                    _target = Member(
                        state=self.bot.state,
                        guild=self.guild,
                        data=_first
                    )

                elif self._raw_resolved.get("users", {}):
                    _first: Optional[dict] = next(
                        iter(self._raw_resolved["users"].values()),
                        None
                    )

                    if not _first:
                        raise ValueError("User command detected users, but was unable to parse it")

                    _target = User(state=self.bot.state, data=_first)

                else:
                    raise ValueError("Neither members nor users were detected while parsing user command")

                return [_target], {}

            case ApplicationCommandType.message:
                return [self.message], {}

            case _:
                raise ValueError("Unknown command type")

    async def _create_args_chat_input(self) -> dict:
        async def _create_args_recursive(data, resolved) -> dict:
            if not data.get("options"):
                return {}

            kwargs: dict[str, Any] = {}

            for option in data["options"]:
                match option["type"]:
                    case x if x in (
                        CommandOptionType.sub_command,
                        CommandOptionType.sub_command_group
                    ):
                        sub_kwargs = await _create_args_recursive(option, resolved)
                        kwargs.update(sub_kwargs)

                    case CommandOptionType.user:
                        if "members" in resolved:
                            if option["value"] not in resolved["members"]:
                                raise CheckFailed(
                                    "It would seem that the user you are trying to get is not within reach. "
                                    "Please check if the user is in the same channel as the command."
                                )

                            member_data = resolved["members"][option["value"]]
                            member_data["user"] = resolved["users"][option["value"]]

                            if not self.guild:
                                raise ValueError("Guild somehow was not available while parsing Member")

                            kwargs[option["name"]] = Member(
                                state=self.bot.state,
                                guild=self.guild,
                                data=member_data
                            )

                        else:
                            kwargs[option["name"]] = User(
                                state=self.bot.state,
                                data=resolved["users"][option["value"]]
                            )

                    case CommandOptionType.channel:
                        type_id = resolved["channels"][option["value"]]["type"]
                        kwargs[option["name"]] = channel_types[type_id](
                            state=self.bot.state,
                            data=resolved["channels"][option["value"]]
                        )

                    case CommandOptionType.attachment:
                        kwargs[option["name"]] = Attachment(
                            state=self.bot.state,
                            data=resolved["attachments"][option["value"]]
                        )

                    case CommandOptionType.role:
                        if not self.guild:
                            raise ValueError("Guild somehow was not available while parsing Role")

                        kwargs[option["name"]] = Role(
                            state=self.bot.state,
                            guild=self.guild,
                            data=resolved["roles"][option["value"]]
                        )

                    case CommandOptionType.string:
                        kwargs[option["name"]] = option["value"]

                        _has_converter = self.command._converters.get(option["name"], None)
                        if _has_converter:
                            _conv_class = _has_converter()
                            if inspect.iscoroutinefunction(_conv_class.convert):
                                kwargs[option["name"]] = await _conv_class.convert(
                                    self,
                                    option["value"]
                                )
                            else:
                                kwargs[option["name"]] = _conv_class.convert(
                                    self,
                                    option["value"]
                                )

                    case CommandOptionType.integer:
                        kwargs[option["name"]] = int(option["value"])

                    case CommandOptionType.number:
                        kwargs[option["name"]] = float(option["value"])

                    case CommandOptionType.boolean:
                        kwargs[option["name"]] = bool(option["value"])

                    case _:
                        kwargs[option["name"]] = option["value"]

            return kwargs

        return await _create_args_recursive(
            {"options": self.options},
            self._raw_resolved
        )

    def _parse_user(self, data: dict) -> Union[Member, User]:
        if data.get("member", None):
            return Member(
                state=self.bot.state,
                guild=self.guild,  # type: ignore
                data=data["member"]
            )
        elif data.get("user", None):
            return User(
                state=self.bot.state,
                data=data["user"]
            )
        else:
            raise ValueError(
                "Neither member nor user was detected while parsing user"
            )
