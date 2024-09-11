import inspect
import logging

from typing import TYPE_CHECKING, Callable, Union, Optional, Any, Self
from datetime import datetime, timedelta

from . import utils
from .channel import (
    TextChannel, DMChannel, VoiceChannel,
    GroupDMChannel, CategoryChannel, NewsThread,
    PublicThread, PrivateThread, StageChannel,
    DirectoryChannel, ForumChannel, StoreChannel,
    NewsChannel, BaseChannel
)
from .cooldowns import Cooldown
from .embeds import Embed
from .entitlements import Entitlements
from .enums import (
    ApplicationCommandType, CommandOptionType,
    ResponseType, ChannelType, InteractionType
)
from .file import File
from .flag import Permissions
from .guild import PartialGuild
from .member import Member
from .mentions import AllowedMentions
from .message import Message, Attachment, Poll
from .response import (
    MessageResponse, DeferResponse,
    AutocompleteResponse, ModalResponse
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


class SelectValues:
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

    @property
    def members(self) -> list[Member]:
        """ `List[Member]`: of members selected """
        return self._parsed_data["members"]

    @property
    def users(self) -> list[User]:
        """ `List[User]`: of users selected """
        return self._parsed_data["users"]

    @property
    def channels(self) -> list[BaseChannel]:
        """ `List[BaseChannel]`: of channels selected """
        return self._parsed_data["channels"]

    @property
    def roles(self) -> list[Role]:
        """ `List[Role]`: of roles selected """
        return self._parsed_data["roles"]

    @property
    def strings(self) -> list[str]:
        """ `List[str]`: of strings selected """
        return self._parsed_data["strings"]

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
                    to_append.append(channel_types[g["type"]](state=ctx.bot.state, data=_data))

                case "roles":
                    if not ctx.guild:
                        raise ValueError("While parsing roles, guild object was not available")
                    to_append.append(Role(state=ctx.bot.state, guild=ctx.guild, data=_data))

                case _:
                    pass


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
        call_after: Optional[Callable] = None
    ) -> DeferResponse:
        """
        Defer the response to the interaction

        Parameters
        ----------
        ephemeral: `bool`
            If the response should be ephemeral (show only to the user)
        thinking: `bool`
            If the response should show the "thinking" status
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

        return DeferResponse(ephemeral=ephemeral, thinking=thinking)

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
                _log.warn(
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
        self.select_values: SelectValues = SelectValues.none(self)
        self.modal_values: dict[str, str] = {}

        self.options: list[dict] = data.get("data", {}).get("options", [])
        self.followup_token: str = data.get("token", None)

        self._original_response: Optional[Message] = None
        self._resolved: dict = data.get("data", {}).get("resolved", {})

        self.entitlements: list[Entitlements] = [
            Entitlements(state=self.bot.state, data=g)
            for g in data.get("entitlements", [])
        ]

        # Should not be used, but if you *really* want the raw data, here it is
        self._data: dict = data

        self._from_data(data)

    def _from_data(self, data: dict):
        self.channel_id: Optional[int] = None
        if data.get("channel_id", None):
            self.channel_id = int(data["channel_id"])

        self.channel: Optional[BaseChannel] = None
        if data.get("channel", None):
            self.channel = channel_types[data["channel"]["type"]](
                state=self.bot.state,
                data=data["channel"]
            )

        self.guild: Optional[PartialGuild] = None
        if data.get("guild_id", None):
            self.guild = PartialGuild(
                state=self.bot.state,
                id=int(data["guild_id"])
            )

        self.message: Optional[Message] = None
        if data.get("message", None):
            self.message = Message(
                state=self.bot.state,
                data=data["message"],
                guild=self.guild
            )
        elif self._resolved.get("messages", {}):
            _first_msg = next(iter(self._resolved["messages"].values()), None)
            if _first_msg:
                self.message = Message(
                    state=self.bot.state,
                    data=_first_msg,
                    guild=self.guild
                )

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

    async def original_response(self) -> Message:
        """ `Message` Returns the original response to the interaction """
        if self._original_response is not None:
            return self._original_response

        r = await self.bot.state.query(
            "GET",
            f"/webhooks/{self.bot.application_id}/{self.followup_token}/messages/@original"
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
        _msg_kwargs = MessageResponse(
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
            json=_msg_kwargs.to_dict()["data"]
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
            f"/webhooks/{self.bot.application_id}/{self.followup_token}/messages/@original"
        )

    def _create_args(self) -> tuple[list[Union[Member, User, Message, None]], dict]:
        match self.command_type:
            case ApplicationCommandType.chat_input:
                return [], self._create_args_chat_input()

            case ApplicationCommandType.user:
                if self._resolved.get("members", {}):
                    _first: Optional[dict] = next(
                        iter(self._resolved["members"].values()),
                        None
                    )

                    if not _first:
                        raise ValueError("User command detected members, but was unable to parse it")
                    if not self.guild:
                        raise ValueError("While parsing members, guild was not available")

                    _first["user"] = next(
                        iter(self._resolved["users"].values()),
                        None
                    )

                    _target = Member(
                        state=self.bot.state,
                        guild=self.guild,
                        data=_first
                    )

                elif self._resolved.get("users", {}):
                    _first: Optional[dict] = next(
                        iter(self._resolved["users"].values()),
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

    def _create_args_chat_input(self) -> dict:
        def _create_args_recursive(data, resolved) -> dict:
            if not data.get("options"):
                return {}

            kwargs = {}

            for option in data["options"]:
                match option["type"]:
                    case x if x in (
                        CommandOptionType.sub_command,
                        CommandOptionType.sub_command_group
                    ):
                        sub_kwargs = _create_args_recursive(option, resolved)
                        kwargs.update(sub_kwargs)

                    case CommandOptionType.user:
                        if "members" in resolved:
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

                    case CommandOptionType.integer:
                        kwargs[option["name"]] = int(option["value"])

                    case CommandOptionType.number:
                        kwargs[option["name"]] = float(option["value"])

                    case CommandOptionType.boolean:
                        kwargs[option["name"]] = bool(option["value"])

                    case _:
                        kwargs[option["name"]] = option["value"]

            return kwargs

        return _create_args_recursive(
            {"options": self.options},
            self._resolved
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
