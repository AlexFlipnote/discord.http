import inspect
import logging
import asyncio

from typing import TYPE_CHECKING, Any, Self
from collections.abc import Callable
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
from .message import Message, Attachment, Poll, WebhookMessage
from .response import (
    MessageResponse, DeferResponse,
    AutocompleteResponse, ModalResponse,
    EmptyResponse
)
from .role import Role
from .user import User
from .view import View, Modal

if TYPE_CHECKING:
    from .client import Client
    from .commands import Command, LocaleTypes

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

    def _from_data(self, ctx: "Context", data: dict) -> None:
        self._parsed_data["strings"] = data.get("data", {}).get("values", [])

        resolved = data.get("data", {}).get("resolved", {})
        data_to_resolve = ["members", "users", "channels", "roles"]

        for key in data_to_resolve:
            self._parse_resolved(ctx, key, resolved)

    @classmethod
    def none(cls, ctx: "Context") -> Self:
        """ With no values. """
        return cls(ctx, {})

    def is_empty(self) -> bool:
        """ Whether no values were selected. """
        return not any(self._parsed_data.values())

    def _parse_resolved(self, ctx: "Context", key: str, data: dict) -> None:
        if not data.get(key):
            return

        for g in data[key]:
            if key == "members":
                data["members"][g]["user"] = data["users"][g]

            to_append: list = self._parsed_data[key]
            data_ = data[key][g]

            match key:
                case "members":
                    if not ctx.guild:
                        raise ValueError("While parsing members, guild object was not available")
                    to_append.append(Member(state=ctx.bot.state, guild=ctx.guild, data=data_))

                case "users":
                    to_append.append(User(state=ctx.bot.state, data=data_))

                case "channels":
                    to_append.append(channel_types[data_["type"]](state=ctx.bot.state, data=data_))

                case "roles":
                    if not ctx.guild:
                        raise ValueError("While parsing roles, guild object was not available")
                    to_append.append(Role(state=ctx.bot.state, guild=ctx.guild, data=data_))

                case _:
                    pass


class ResolvedValues(_ResolveParser):
    def __init__(self, ctx: "Context", data: dict):
        super().__init__(ctx, data)

    @property
    def members(self) -> list[Member]:
        """ Of members resolved. """
        return self._parsed_data["members"]

    @property
    def users(self) -> list[User]:
        """ Of users resolved. """
        return self._parsed_data["users"]

    @property
    def channels(self) -> list[BaseChannel]:
        """ Of channels resolved. """
        return self._parsed_data["channels"]

    @property
    def roles(self) -> list[Role]:
        """ Of roles resolved. """
        return self._parsed_data["roles"]


class SelectValues(ResolvedValues):
    def __init__(self, ctx: "Context", data: dict):
        super().__init__(ctx, data)

    @property
    def strings(self) -> list[str]:
        """ Of strings selected. """
        return self._parsed_data["strings"]


class InteractionResponse:
    def __init__(self, parent: "Context"):
        self._parent = parent

    def pong(self) -> dict:
        """ Only used to acknowledge a ping from Discord Developer portal Interaction URL. """
        return {"type": 1}

    def defer(
        self,
        ephemeral: bool = False,
        thinking: bool = False,
        flags: MessageFlags | None = MISSING,
        call_after: Callable | None = None
    ) -> DeferResponse:
        """
        Defer the response to the interaction.

        Parameters
        ----------
        ephemeral:
            If the response should be ephemeral (show only to the user)
        thinking:
            If the response should show the "thinking" status
        flags:
            The flags of the message (overrides ephemeral)
        call_after:
            A coroutine to run after the response is sent

        Returns
        -------
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
        call_after: Callable | None = None
    ) -> ModalResponse:
        """
        Send a modal to the interaction.

        Parameters
        ----------
        modal:
            The modal to send
        call_after:
            A coroutine to run after the response is sent

        Returns
        -------
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
        call_after: Callable | None = None
    ) -> EmptyResponse:
        """
        Send an empty response to the interaction.

        Parameters
        ----------
        call_after:
            A coroutine to run after the response is sent

        Returns
        -------
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
        content: str | None = MISSING,
        *,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        ephemeral: bool | None = False,
        view: View | None = MISSING,
        tts: bool | None = False,
        type: ResponseType | int = 4,  # noqa: A002
        allowed_mentions: AllowedMentions | None = MISSING,
        poll: Poll | None = MISSING,
        flags: MessageFlags | None = MISSING,
        call_after: Callable | None = None
    ) -> MessageResponse:
        """
        Send a message to the interaction.

        Parameters
        ----------
        content:
            Content of the message
        embed:
            The embed to send
        embeds:
            Multiple embeds to send
        file:
            A file to send
        files:
            Multiple files to send
        ephemeral:
            If the message should be ephemeral (show only to the user)
        view:
            Components to include in the message
        tts:
            Whether the message should be sent using text-to-speech
        type:
            The type of response to send
        allowed_mentions:
            Allowed mentions for the message
        flags:
            The flags of the message (overrides ephemeral)
        poll:
            The poll to be sent
        call_after:
            A coroutine to run after the response is sent

        Returns
        -------
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

        return MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            ephemeral=ephemeral,
            view=view,
            tts=tts,
            file=file,
            files=files,
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
        content: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        view: View | None = MISSING,
        attachment: File | None = MISSING,
        attachments: list[File] | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        flags: MessageFlags | None = MISSING,
        call_after: Callable | None = None
    ) -> MessageResponse:
        """
        Edit the original message of the interaction.

        Parameters
        ----------
        content:
            Content of the message
        embed:
            Embed to edit the message with
        embeds:
            Multiple embeds to edit the message with
        view:
            Components to include in the message
        attachment:
            New file to edit the message with
        attachments:
            Multiple new files to edit the message with
        allowed_mentions:
            Allowed mentions for the message
        flags:
            The flags of the message
        call_after:
            A coroutine to run after the response is sent

        Returns
        -------
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

        return MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            attachment=attachment,
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
        Send an autocomplete response to the interaction.

        Parameters
        ----------
        choices:
            The choices to send

        Returns
        -------
            The response to the interaction

        Raises
        ------
        `TypeError`
            - If `choices` is not a `dict`
            - If `choices` is not a `dict[str | int | float, str]`
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

            if (isinstance(k, int | float)) and k >= 2**53:
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
        self.command: "Command | None" = None

        self.app_permissions: Permissions = Permissions(int(data.get("app_permissions", 0)))
        self.custom_id: str | None = data.get("data", {}).get("custom_id", None)

        self.resolved: ResolvedValues = ResolvedValues.none(self)
        self.select_values: SelectValues = SelectValues.none(self)
        self.modal_values: dict[str, str] = {}

        self.options: list[dict] = data.get("data", {}).get("options", [])
        self._followup_token: str = data.get("token", "")

        self._original_response: WebhookMessage | None = None
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

        self.locale: "LocaleTypes | None" = data.get("locale")
        self.guild_locale: "LocaleTypes | None" = data.get("guild_locale")

        # Should not be used, but if you *really* want the raw data, here it is
        self._data: dict = data

        self._from_data(data)

    def _from_data(self, data: dict) -> None:
        self.channel_id: int | None = None
        if data.get("channel_id"):
            self.channel_id = int(data["channel_id"])

        self._guild: PartialGuild | None = None
        if data.get("guild_id"):
            self._guild = PartialGuild(
                state=self.bot.state,
                id=int(data["guild_id"])
            )

        self._channel: BaseChannel | None = None
        if data.get("channel"):
            channel_data = data["channel"]
            if self._guild:
                channel_data["guild_id"] = self._guild.id

            self._channel = channel_types[channel_data["type"]](
                state=self.bot.state,
                data=channel_data
            )

        self.message: Message | None = None
        if data.get("message"):
            self.message = Message(
                state=self.bot.state,
                data=data["message"],
                guild=self._guild
            )
        elif self._raw_resolved.get("messages", {}):
            first_msg = next(iter(self._raw_resolved["messages"].values()), None)
            if first_msg:
                self.message = Message(
                    state=self.bot.state,
                    data=first_msg,
                    guild=self._guild
                )

        if self._raw_resolved:
            self.resolved = ResolvedValues(self, data)

        self.author: Member | User | None = None
        if self.message is not None:
            self.author = self.message.author

        self.user: Member | User = self._parse_user(data)

        match self.type:
            case InteractionType.message_component:
                self.select_values = SelectValues(self, data)

            case InteractionType.modal_submit:
                for comp in data["data"]["components"]:
                    ans = comp["components"][0]
                    self.modal_values[ans["custom_id"]] = ans["value"]

    async def _background_task_manager(self, call_after: Callable) -> None:
        try:
            if isinstance(self.bot.call_after_delay, int | float):
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
        Returns the guild the interaction was made in.

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
        """ Returns the channel the interaction was made in. """
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
        """ Returns the type of the channel. """
        if self._channel:
            return self._channel.type
        return ChannelType.unknown

    @property
    def created_at(self) -> datetime:
        """ Returns the time the interaction was created. """
        return utils.snowflake_time(self.id)

    @property
    def cooldown(self) -> Cooldown | None:
        """ Returns the context cooldown. """
        cooldown = self.command.cooldown

        if cooldown is None:
            return None

        return cooldown.get_bucket(
            self, self.created_at.timestamp()
        )

    @property
    def expires_at(self) -> datetime:
        """ Returns the time the interaction expires. """
        return self.created_at + timedelta(minutes=15)

    def is_expired(self) -> bool:
        """ Returns whether the interaction is expired. """
        return utils.utcnow() >= self.expires_at

    @property
    def response(self) -> InteractionResponse:
        """ Returns the response to the interaction. """
        return InteractionResponse(self)

    def is_bot_dm(self) -> bool:
        """ Returns a boolean of whether the interaction was in the bot's DM channel. """
        return (
            len(self.recipients) == 1 and
            self.bot.user.id in self.recipients
        )

    async def send(
        self,
        content: str | None = MISSING,
        *,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        ephemeral: bool | None = False,
        view: View | None = MISSING,
        tts: bool | None = False,
        type: ResponseType | int = 4,  # noqa: A002
        allowed_mentions: AllowedMentions | None = MISSING,
        poll: Poll | None = MISSING,
        flags: MessageFlags | None = MISSING,
        delete_after: float | None = None
    ) -> WebhookMessage:
        """
        Send a message after responding with an empty response in the initial interaction.

        Parameters
        ----------
        content:
            Content of the message
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        file:
            File of the message
        files:
            Files of the message
        ephemeral:
            Whether the message should be sent as ephemeral
        view:
            Components of the message
        type:
            Which type of response should be sent
        allowed_mentions:
            Allowed mentions of the message
        wait:
            Whether to wait for the message to be sent
        thread_id:
            Thread ID to send the message to
        poll:
            Poll to send with the message
        tts:
            Whether the message should be sent as TTS
        flags:
            Flags of the message
        delete_after:
            How long to wait before deleting the message

        Returns
        -------
            Returns the message that was sent
        """
        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            ephemeral=ephemeral,
            view=view,
            tts=tts,
            file=file,
            files=files,
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

        modified_payload = payload.to_dict()
        multidata.attach("payload_json", modified_payload)

        r = await self.bot.state.query(
            "POST",
            f"/interactions/{self.id}/{self._followup_token}/callback",
            data=multidata.finish(),
            params={"with_response": "true"},
            headers={"Content-Type": multidata.content_type}
        )

        msg = WebhookMessage(
            state=self.bot.state,
            data=r.response["resource"]["message"],
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
        )

        if delete_after is not None:
            await msg.delete(delay=float(delete_after))
        return msg

    async def create_followup_response(
        self,
        content: str | None = MISSING,
        *,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        ephemeral: bool | None = False,
        view: View | None = MISSING,
        tts: bool | None = False,
        type: ResponseType | int = 4,  # noqa: A002
        allowed_mentions: AllowedMentions | None = MISSING,
        poll: Poll | None = MISSING,
        flags: MessageFlags | None = MISSING,
        delete_after: float | None = None
    ) -> WebhookMessage:
        """
        Creates a new followup response to the interaction.

        Do not use this to create a followup response when defer was called before.
        Use `edit_original_response` instead.

        Parameters
        ----------
        content:
            Content of the message
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        file:
            File of the message
        files:
            Files of the message
        ephemeral:
            Whether the message should be sent as ephemeral
        view:
            Components of the message
        type:
            Which type of response should be sent
        allowed_mentions:
            Allowed mentions of the message
        wait:
            Whether to wait for the message to be sent
        thread_id:
            Thread ID to send the message to
        poll:
            Poll to send with the message
        tts:
            Whether the message should be sent as TTS
        flags:
            Flags of the message
        delete_after:
            How long to wait before deleting the message

        Returns
        -------
            Returns the message that was sent
        """
        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            ephemeral=ephemeral,
            view=view,
            tts=tts,
            file=file,
            files=files,
            type=type,
            poll=poll,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self.bot._default_allowed_mentions
            )
        )

        r = await self.bot.state.query(
            "POST",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        msg = WebhookMessage(
            state=self.bot.state,
            data=r.response,
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
        )

        if delete_after is not None:
            await msg.delete(delay=float(delete_after))
        return msg

    async def original_response(self) -> WebhookMessage:
        """ Fetch the original response to the interaction. """
        if self._original_response is not None:
            return self._original_response

        r = await self.bot.state.query(
            "GET",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}/messages/@original",
            retry_codes=[404]
        )

        msg = WebhookMessage(
            state=self.bot.state,
            data=r.response,
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
        )

        self._original_response = msg
        return msg

    async def edit_original_response(
        self,
        *,
        content: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        view: View | None = MISSING,
        attachment: File | None = MISSING,
        attachments: list[File] | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        flags: MessageFlags | None = MISSING,
    ) -> WebhookMessage:
        """ Edit the original response to the interaction. """
        payload = MessageResponse(
            content=content,
            embeds=embeds,
            embed=embed,
            attachment=attachment,
            attachments=attachments,
            view=view,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self.bot._default_allowed_mentions
            )
        )

        r = await self.bot.state.query(
            "PATCH",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}/messages/@original",
            headers={"Content-Type": payload.content_type},
            data=payload.to_multipart(is_request=True),
            retry_codes=[404]
        )

        msg = WebhookMessage(
            state=self.bot.state,
            data=r.response,
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
        )

        self._original_response = msg
        return msg

    async def delete_original_response(self) -> None:
        """ Delete the original response to the interaction. """
        await self.bot.state.query(
            "DELETE",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}/messages/@original",
            retry_codes=[404]
        )

    async def _create_args(self) -> tuple[list[Member | User | Message | None], dict]:
        match self.command_type:
            case ApplicationCommandType.chat_input:
                return [], await self._create_args_chat_input()

            case ApplicationCommandType.user:
                if self.resolved.members:
                    first: dict | None = next(
                        iter(self._raw_resolved["members"].values()),
                        None
                    )

                    if not first:
                        raise ValueError("User command detected members, but was unable to parse it")
                    if not self.guild:
                        raise ValueError("While parsing members, guild was not available")

                    first["user"] = next(
                        iter(self._raw_resolved["users"].values()),
                        None
                    )

                    target = Member(
                        state=self.bot.state,
                        guild=self.guild,
                        data=first
                    )

                elif self._raw_resolved.get("users", {}):
                    first: dict | None = next(
                        iter(self._raw_resolved["users"].values()),
                        None
                    )

                    if not first:
                        raise ValueError("User command detected users, but was unable to parse it")

                    target = User(state=self.bot.state, data=first)

                else:
                    raise ValueError("Neither members nor users were detected while parsing user command")

                return [target], {}

            case ApplicationCommandType.message:
                return [self.message], {}

            case _:
                raise ValueError("Unknown command type")

    async def _create_args_chat_input(self) -> dict:
        async def _create_args_recursive(data: dict, resolved: dict) -> dict:
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

                        has_converter = self.command._converters.get(option["name"], None)
                        if has_converter:
                            conv_class = has_converter()
                            if inspect.iscoroutinefunction(conv_class.convert):
                                kwargs[option["name"]] = await conv_class.convert(
                                    self,
                                    option["value"]
                                )
                            else:
                                kwargs[option["name"]] = conv_class.convert(
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

    def _parse_user(self, data: dict) -> Member | User:
        if data.get("member"):
            return Member(
                state=self.bot.state,
                guild=self.guild,  # type: ignore
                data=data["member"]
            )
        if data.get("user"):
            return User(
                state=self.bot.state,
                data=data["user"]
            )
        raise ValueError(
            "Neither member nor user was detected while parsing user"
        )
