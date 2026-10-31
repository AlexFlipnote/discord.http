import asyncio
import inspect
import logging
import time

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Self

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
    ResponseType, ChannelType, InteractionType,
    ComponentType, IntegrationType, InteractionContextType
)
from .file import File
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

# Converted once, compared on every interaction
_CHAT_INPUT = int(ApplicationCommandType.chat_input)
_MESSAGE_COMPONENT = int(InteractionType.message_component)
_MODAL_SUBMIT = int(InteractionType.modal_submit)

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
    int(ChannelType.guild_media): ForumChannel,
}

__all__ = (
    "Context",
    "InteractionResponse",
    "ResolvedValues",
    "SelectValues",
)


class _ResolveParser:
    __slots__ = (
        "_parsed_data",
    )

    def __init__(self, ctx: "Context", data: dict):
        self._parsed_data: dict | None = {
            "members": [], "users": [],
            "channels": [], "roles": [],
            "strings": [], "attachments": []
        }

        self._from_data(ctx, data)

    def _from_data(self, ctx: "Context", data: dict) -> None:
        self._parsed_data["strings"] = data.get("data", {}).get("values", [])

        resolved = data.get("data", {}).get("resolved", {})

        # Read once, a guild that is not cached is rebuilt on every read
        guild = ctx.guild if resolved.get("members") or resolved.get("roles") else None

        for key in ("members", "users", "channels", "roles", "attachments"):
            if resolved.get(key):
                self._parse_resolved(ctx, key, resolved, guild)

    @classmethod
    def none(cls, ctx: "Context") -> Self:  # ruff: ignore[unused-class-method-argument]
        """ With no values. """
        return cls._empty()

    @classmethod
    def _from_parsed(cls, parsed_data: dict | None) -> Self:
        """ Build an instance sharing an already-parsed data dict, skipping a redundant re-parse. """
        self = cls.__new__(cls)
        self._parsed_data = parsed_data
        return self

    @classmethod
    def _empty(cls) -> Self:
        """ With no values, skipping the parsing entirely as there is nothing to parse. """
        self = cls.__new__(cls)
        # Most interactions resolve nothing, so no dict of empty lists is built for them
        self._parsed_data = None
        return self

    def is_empty(self) -> bool:
        """ Whether no values were selected. """
        return self._parsed_data is None or not any(self._parsed_data.values())

    def _values(self, key: str) -> list:
        """
        The parsed values of a kind.

        Parameters
        ----------
        key
            The kind of values, like `members` or `roles`

        Returns
        -------
            The parsed values, a new empty list if nothing was parsed
        """
        if self._parsed_data is None:
            return []
        return self._parsed_data[key]

    def _parse_resolved(
        self,
        ctx: "Context",
        key: str,
        data: dict,
        guild: "Guild | PartialGuild | None"
    ) -> None:

        for g in data[key]:
            if key == "members":
                data["members"][g]["user"] = data["users"][g]

            to_append: list = self._parsed_data[key]
            data_ = data[key][g]

            match key:
                case "members":
                    if not guild:
                        raise ValueError("While parsing members, guild object was not available")
                    to_append.append(ctx.bot.create_member_from_data(data_, guild=guild))

                case "users":
                    to_append.append(ctx.bot.create_user_from_data(data_))

                case "attachments":
                    to_append.append(Attachment(state=ctx.bot.state, data=data_))

                case "channels":
                    to_append.append(channel_types.get(data_["type"], BaseChannel)(state=ctx.bot.state, data=data_))

                case "roles":
                    if not guild:
                        raise ValueError("While parsing roles, guild object was not available")
                    to_append.append(ctx.bot.create_role_from_data(data_, guild=guild))

                case _:
                    pass


class ResolvedValues(_ResolveParser):
    """ Represents the resolved values of an interaction. """

    __slots__ = ()

    def __init__(self, ctx: "Context", data: dict):
        super().__init__(ctx, data)

    @property
    def members(self) -> list[Member]:
        """ The resolved members if any. """
        return self._values("members")

    @property
    def users(self) -> list[User]:
        """ The resolved users if any. """
        return self._values("users")

    @property
    def channels(self) -> list[BaseChannel]:
        """ The resolved channels if any. """
        return self._values("channels")

    @property
    def roles(self) -> list[Role]:
        """ The resolved roles if any. """
        return self._values("roles")

    @property
    def attachments(self) -> list[Attachment]:
        """ The resolved attachments if any. """
        return self._values("attachments")


class SelectValues(ResolvedValues):
    """ Represents the selected values of a select menu interaction. """
    __slots__ = ()

    def __init__(self, ctx: "Context", data: dict):
        super().__init__(ctx, data)

    @property
    def strings(self) -> list[str]:
        """ Of strings selected. """
        return self._values("strings")


class InteractionResponse:
    """ Represents the response to an interaction. """

    __slots__ = ("_parent",)

    def __init__(self, parent: "Context"):
        self._parent = parent

    def _call_after_generator(self, call_after: Callable | None) -> None:
        """
        Helper function to create a background task for `call_after`.

        Parameters
        ----------
        call_after
            A coroutine to run after the response is sent

        Raises
        ------
        TypeError
            If `call_after` is not a coroutine
        """
        if call_after:
            if not inspect.iscoroutinefunction(call_after):
                raise TypeError("call_after must be a coroutine")

            # Create the event now, the backend only tracks the response flush when it exists
            self._parent._ensure_response_sent_event()

            task = self._parent.bot.loop.create_task(
                self._parent._background_task_manager(call_after),
                name=f"discord.http/call_after:{int(time.time())}"
            )
            self._parent.bot._background_tasks.add(task)
            task.add_done_callback(self._parent.bot._cleanup_task)

    def pong(self) -> dict:
        """ Only used to acknowledge a ping from Discord Developer portal Interaction URL. """
        return {"type": 1}

    def defer(
        self,
        thinking: bool = False,
        ephemeral: bool = False,
        flags: MessageFlags | None = MISSING,
        call_after: Callable | None = None
    ) -> DeferResponse:
        """
        Defer the response to the interaction.

        Parameters
        ----------
        thinking
            If the response should show the "thinking" status
        ephemeral
            If the response should be ephemeral (show only to the user)
        flags
            The flags of the message (overrides ephemeral)
        call_after
            A coroutine to run after the response is sent

        Returns
        -------
            The response to the interaction

        Raises
        ------
        TypeError
            If `call_after` is not a coroutine
        """
        self._call_after_generator(call_after)
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
        modal
            The modal to send
        call_after
            A coroutine to run after the response is sent

        Returns
        -------
            The response to the interaction

        Raises
        ------
        TypeError
            - If `modal` is not a `Modal` instance
            - If `call_after` is not a coroutine
        """
        if not isinstance(modal, Modal):
            raise TypeError("modal must be a Modal instance")

        self._call_after_generator(call_after)
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
        call_after
            A coroutine to run after the response is sent

        Returns
        -------
            The response to the interaction
        """
        self._call_after_generator(call_after)
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
        type: ResponseType | int = 4,  # ruff: ignore[builtin-argument-shadowing]
        allowed_mentions: AllowedMentions | None = MISSING,
        poll: Poll | None = MISSING,
        flags: MessageFlags | None = MISSING,
        call_after: Callable | None = None
    ) -> MessageResponse:
        """
        Send a message to the interaction.

        Parameters
        ----------
        content
            Content of the message
        embed
            The embed to send
        embeds
            Multiple embeds to send
        file
            A file to send
        files
            Multiple files to send
        ephemeral
            If the message should be ephemeral (show only to the user)
        view
            Components to include in the message
        tts
            Whether the message should be sent using text-to-speech
        type
            The type of response to send
        allowed_mentions
            Allowed mentions for the message
        flags
            The flags of the message (overrides ephemeral)
        poll
            The poll to be sent
        call_after
            A coroutine to run after the response is sent

        Returns
        -------
            The response to the interaction

        Raises
        ------
        ValueError
            - If both `embed` and `embeds` are passed
            - If both `file` and `files` are passed
        TypeError
            If `call_after` is not a coroutine
        """
        self._call_after_generator(call_after)

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
        content
            Content of the message
        embed
            Embed to edit the message with
        embeds
            Multiple embeds to edit the message with
        view
            Components to include in the message
        attachment
            New file to edit the message with
        attachments
            Multiple new files to edit the message with
        allowed_mentions
            Allowed mentions for the message
        flags
            The flags of the message
        call_after
            A coroutine to run after the response is sent

        Returns
        -------
            The response to the interaction

        Raises
        ------
        ValueError
            - If both `embed` and `embeds` are passed
            - If both `attachment` and `attachments` are passed
        TypeError
            If `call_after` is not a coroutine
        """
        self._call_after_generator(call_after)

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
        choices
            The choices to send

        Returns
        -------
            The response to the interaction

        Raises
        ------
        TypeError
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
    """ Represents the context of an interaction. """

    __slots__ = (
        "_data",
        "_followup_token",
        "_original_response",
        "_raw_app_permissions",
        "_raw_authorizing_integration_owners",
        "_raw_channel",
        "_raw_command_type",
        "_raw_context",
        "_raw_resolved",
        "_raw_type",
        "_response_sent_event",
        "attachment_size_limit",
        "author",
        "benchmark",
        "bot",
        "channel_id",
        "command",
        "custom_id",
        "entitlements",
        "guild_id",
        "guild_locale",
        "id",
        "last_message_id",
        "locale",
        "message",
        "modal_values",
        "options",
        "recipients",
        "response",
        "select_values",
        "user",
    )

    def __init__(
        self,
        bot: "Client",
        data: dict
    ):
        self._raw_channel: dict | None = None
        self._response_sent_event: asyncio.Event | None = None

        self.bot: "Client" = bot
        """ The bot/client instance that the interaction belongs to. """

        self.id: int = int(data["id"])
        """ The ID of the interaction. """

        self._raw_type: int = data["type"]

        data_payload: dict = data.get("data") or {}

        self._raw_command_type: int = data_payload.get("type", _CHAT_INPUT)

        # Default utilities
        self.benchmark: utils.Benchmark = utils.Benchmark()
        """ A utility for benchmarking the time taken to execute code after responding to the interaction. """

        # Arguments that gets parsed on runtime
        self.command: "Command | None" = None
        """ The command that was executed, if any. """

        self._raw_app_permissions: int = int(data.get("app_permissions", 0))

        self.custom_id: str | None = data_payload.get("custom_id")
        """ The custom ID of the interaction, if any. """

        self.select_values: SelectValues = SelectValues._empty()
        """ The selected values of the interaction, if any. """

        self.modal_values: dict[str, str | bool | list[Member | Role | BaseChannel | Attachment | str] | None] = {}
        """ The values of the modal, if any. """

        self.options: list[dict] = data_payload.get("options", [])
        """ The options of the interaction, if any. """

        self._followup_token: str = data.get("token", "")

        self._original_response: WebhookMessage | None = None
        self._raw_resolved: dict = data_payload.get("resolved", {})

        self.entitlements: list[Entitlements] = [
            self.bot.create_entitlements_from_data(g)
            for g in data.get("entitlements", [])
        ]
        """ The entitlements associated with the interaction. """

        self.last_message_id: int | None = None
        """ The ID of the last message in the channel, if any. """

        channel_payload: dict = data.get("channel") or {}

        if channel_payload.get("last_message_id"):
            self.last_message_id = int(channel_payload["last_message_id"])

        self.recipients: list[User] = [
            self.bot.create_user_from_data(g)
            for g in channel_payload.get("recipients", [])
        ]
        """ The recipients of the interaction, if any. """

        self.locale: "LocaleTypes | None" = data.get("locale")
        """ The locale of the interaction, if any. """

        self.guild_locale: "LocaleTypes | None" = data.get("guild_locale")
        """ The locale of the guild, if any. """

        self._raw_context: int | None = data.get("context")

        self._raw_authorizing_integration_owners: dict[str, str] = data.get("authorizing_integration_owners") or {}

        self.attachment_size_limit: int = data.get("attachment_size_limit", 0)
        """ The attachment size limit in bytes for the interaction. """

        self.channel_id: int | None = None
        """ The ID of the channel the interaction was sent in, if applicable. """

        self.guild_id: int | None = None
        """ The ID of the guild the interaction was sent in, if applicable. """

        self.message: Message | None = None
        """ The message associated with the interaction, if any. """

        # Only the `data` sub-payload, the full payload would pin `message`/`member`/`channel` for the Context's lifetime
        self._data: dict = data_payload

        self.author: Member | User | None = None
        """ The author of the message that was interacted with, if any. """

        # Parse the data, then continue with the rest of the initialization
        guild = self._from_data(data)

        self.user: Member | User = self._parse_user(data, guild)
        """ The user who initiated the interaction. """

        self.response: InteractionResponse = InteractionResponse(self)
        """ The response helper for this interaction. """

    def _from_data(self, data: dict) -> "Guild | PartialGuild | None":
        if channel_id := data.get("channel_id"):
            self.channel_id = int(channel_id)

        if guild_id := data.get("guild_id"):
            self.guild_id = int(guild_id)

        if channel := data.get("channel"):
            if self.guild_id:
                channel["guild_id"] = self.guild_id

            # Only built when read, most commands never use it
            self._raw_channel = channel

        # Read once, a guild that is not cached is rebuilt on every read
        guild = self.guild

        if message := data.get("message"):
            self.message = self.bot.create_message_from_data(
                message,
                guild=guild
            )
        elif first_msg := next(iter(self._raw_resolved.get("messages", {}).values()), None):
            self.message = self.bot.create_message_from_data(
                first_msg,
                guild=guild
            )

        if self.message is not None:
            self.author = self.message.author

        if self._raw_type == _MESSAGE_COMPONENT:
            self.select_values = SelectValues(self, data)

        elif self._raw_type == _MODAL_SUBMIT:
            resolved = self.resolved
            for comp in data["data"]["components"]:
                ans = comp.get("component", None)
                if not ans:
                    # This is probably a text component
                    continue
                self.modal_values[ans["custom_id"]] = ans.get("value", None)

                if ans.get("values", None):
                    match ComponentType(ans["type"]):
                        case ComponentType.user_select:
                            self.modal_values[ans["custom_id"]] = [
                                g for g in resolved.members
                                if str(g.id) in ans.get("values", [])
                            ]

                        case ComponentType.role_select:
                            self.modal_values[ans["custom_id"]] = [
                                r for r in resolved.roles
                                if str(r.id) in ans.get("values", [])
                            ]

                        case ComponentType.file_upload:
                            self.modal_values[ans["custom_id"]] = [
                                a for a in resolved.attachments
                                if str(a.id) in ans.get("values", [])
                            ]

                        case ComponentType.channel_select:
                            self.modal_values[ans["custom_id"]] = [
                                c for c in resolved.channels
                                if str(c.id) in ans.get("values", [])
                            ]

                        case ComponentType.mentionable_select:
                            collected_values = []
                            allowed_ids = set(ans.get("values", []))

                            for m in resolved.members:
                                if str(m.id) in allowed_ids:
                                    collected_values.append(m)
                            for r in resolved.roles:
                                if str(r.id) in allowed_ids:
                                    collected_values.append(r)
                            for c in resolved.channels:
                                if str(c.id) in allowed_ids:
                                    collected_values.append(c)
                            self.modal_values[ans["custom_id"]] = collected_values

                        case _:
                            # Probably just strings, default to that
                            self.modal_values[ans["custom_id"]] = (
                                ans.get("values", None) or  # If it was text select
                                ans.get("value", None) or  # If it was text input
                                "discord.http:INVALID"  # It should never reach here...
                            )

        return guild

    async def _background_task_manager(self, call_after: Callable) -> None:
        try:
            try:
                # Give Discord enough time to close their connection
                with self.benchmark.measure("call_after:ack_flush_wait", internal=True):
                    await asyncio.wait_for(self._ensure_response_sent_event().wait(), timeout=5.0)
            except TimeoutError:
                self._ensure_response_sent_event().set()
                _log.error(
                    f"call_after:{call_after} refused: no response confirmation "
                    "from Discord within 5s (connection likely dropped)"
                )
                return

            with self.benchmark.measure("call_after:execution"):
                await call_after()
        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", self, e)
            else:
                _log.error(
                    f"Error while running call_after:{call_after}",
                    exc_info=e
                )

    def _ensure_response_sent_event(self) -> asyncio.Event:
        """ Returns the event set once the HTTP response has been flushed, creating it if needed. """
        if self._response_sent_event is None:
            self._response_sent_event = asyncio.Event()
        return self._response_sent_event

    @property
    def type(self) -> InteractionType:
        """ The type of the interaction. """
        return InteractionType(self._raw_type)

    @property
    def command_type(self) -> ApplicationCommandType:
        """ The type of the command, if any. """
        return ApplicationCommandType(self._raw_command_type)

    @property
    def app_permissions(self) -> Permissions:
        """ The permissions of the application in the guild. """
        return Permissions(self._raw_app_permissions)

    @property
    def context(self) -> InteractionContextType | None:
        """ The context where the interaction was triggered from, if any. """
        if self._raw_context is None:
            return None
        return InteractionContextType(self._raw_context)

    @property
    def resolved(self) -> ResolvedValues:
        """ The resolved values of the interaction, built from the raw data when read. """
        if not self._raw_resolved:
            return ResolvedValues._empty()
        if self._raw_type == _MESSAGE_COMPONENT:
            # Select menus already parsed these, so share the same objects instead of parsing again
            return ResolvedValues._from_parsed(self.select_values._parsed_data)
        return ResolvedValues(self, {"data": self._data})

    def _payload_channel(self) -> BaseChannel | None:
        """ The channel sent with the interaction, built from the raw payload when asked for. """
        if self._raw_channel is None:
            return None
        return channel_types.get(self._raw_channel["type"], BaseChannel)(
            state=self.bot.state,
            data=self._raw_channel
        )

    @property
    def guild(self) -> Guild | PartialGuild | None:
        """
        The guild the interaction was made in.

        If you are using gateway cache, it can return full object too
        """
        if self.guild_id is None:
            return None

        if cache := self.bot.cache.get_guild(self.guild_id):
            return cache

        return self._partial_guild()

    def _partial_guild(self) -> PartialGuild | None:
        """ The partial guild of the interaction, built from its ID when asked for. """
        if self.guild_id is None:
            return None
        return self.bot.get_partial_guild(self.guild_id)

    @property
    def channel(self) -> "BaseChannel | PartialChannel | None":
        """ The channel the interaction was made in. """
        if not self.channel_id:
            return None

        if self.guild_id and (cache := self.bot.cache.get_channel_thread(
            guild_id=self.guild_id,
            channel_id=self.channel_id
        )):
            return cache

        if channel := self._payload_channel():
            # Prefer the channel from context
            return channel

        return self.bot.get_partial_channel(
            self.channel_id,
            guild_id=self.guild_id
        )

    @property
    def channel_type(self) -> ChannelType:
        """ The type of the channel. """
        if self._raw_channel is None:
            return ChannelType.unknown
        return ChannelType(self._raw_channel["type"])

    @property
    def created_at(self) -> datetime:
        """ The time the interaction was created. """
        return utils.snowflake_time(self.id)

    @property
    def cooldown(self) -> Cooldown | None:
        """ The context cooldown. """
        if (cooldown := self.command.cooldown) is None:
            return None

        return cooldown.get_bucket(
            self, self.created_at.timestamp()
        )

    @property
    def expires_at(self) -> datetime:
        """ The time the interaction expires. """
        return self.created_at + timedelta(minutes=15)

    def is_expired(self) -> bool:
        """ Returns whether the interaction is expired. """
        return utils.utcnow() >= self.expires_at

    def _warn_if_expired(self) -> None:
        if self.is_expired():
            _log.warning(
                f"Interaction {self.id} token expired at {self.expires_at} (15 minutes after creation). "
                "Discord will likely respond with 404 Unknown Webhook to this request."
            )

    @property
    def authorizing_integration_owners(self) -> dict[IntegrationType, int]:
        """
        Mapping of the installation contexts the interaction was authorized for, to the related guild or user ID.

        For `IntegrationType.guild`, the ID is `0` if the interaction was triggered from the bot's DM.
        """
        return {
            IntegrationType(int(k)): int(v)
            for k, v in self._raw_authorizing_integration_owners.items()
        }

    def is_bot_dm(self) -> bool:
        """ Returns a boolean of whether the interaction was in the bot's DM channel. """
        if self.context is not None:
            return self.context == InteractionContextType.bot_dm

        return (
            len(self.recipients) == 1 and
            self.bot.user.id in self.recipients
        )

    async def defer(
        self,
        *,
        thinking: bool = False,
        ephemeral: bool = False,
    ) -> WebhookMessage:
        """
        Defer the interaction after responding with an empty response in the initial interaction.

        Parameters
        ----------
        thinking
            Whether the deferred message should show the "thinking" status
        ephemeral
            Whether the deferred message should be ephemeral

        Returns
        -------
            Returns the deferred message
        """
        payload = self.response.defer(
            ephemeral=ephemeral,
            thinking=thinking
        )

        r = await self.bot.state.query(
            "POST",
            f"/interactions/{self.id}/{self._followup_token}/callback",
            params={"with_response": "true"},
            json=payload.to_dict()
        )

        return self.bot.create_webhook_message_from_data(
            r.response["resource"]["message"],
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
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
        type: ResponseType | int = 4,  # ruff: ignore[builtin-argument-shadowing]
        allowed_mentions: AllowedMentions | None = MISSING,
        poll: Poll | None = MISSING,
        flags: MessageFlags | None = MISSING,
        delete_after: float | None = None
    ) -> WebhookMessage:
        """
        Send a message after responding with an empty response in the initial interaction.

        Parameters
        ----------
        content
            Content of the message
        embed
            Embed of the message
        embeds
            Embeds of the message
        file
            File of the message
        files
            Files of the message
        ephemeral
            Whether the message should be sent as ephemeral
        view
            Components of the message
        type
            Which type of response should be sent
        allowed_mentions
            Allowed mentions of the message
        wait
            Whether to wait for the message to be sent
        thread_id
            Thread ID to send the message to
        poll
            Poll to send with the message
        tts
            Whether the message should be sent as TTS
        flags
            Flags of the message
        delete_after
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

        multidata = utils.MultipartData()

        if isinstance(payload.files, list):
            for i, file in enumerate(payload.files):
                multidata.attach(
                    f"file{i}",
                    file,
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

        msg = self.bot.create_webhook_message_from_data(
            r.response["resource"]["message"],
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
        )

        if delete_after is not None:
            await msg.delete(delay=float(delete_after))
        return msg

    async def send_modal(
        self,
        modal: Modal,
    ) -> None:
        """
        Send a modal after responding with an empty response in the initial interaction.

        Parameters
        ----------
        modal
            The modal to send

        Raises
        ------
        TypeError
            If `modal` is not a `Modal` instance
        """
        if not isinstance(modal, Modal):
            raise TypeError("modal must be a Modal instance")

        payload = ModalResponse(modal=modal)

        await self.bot.state.query(
            "POST",
            f"/interactions/{self.id}/{self._followup_token}/callback",
            json=payload.to_dict(),
            res_method="text"
        )

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
        type: ResponseType | int = 4,  # ruff: ignore[builtin-argument-shadowing]
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
        content
            Content of the message
        embed
            Embed of the message
        embeds
            Embeds of the message
        file
            File of the message
        files
            Files of the message
        ephemeral
            Whether the message should be sent as ephemeral
        view
            Components of the message
        type
            Which type of response should be sent
        allowed_mentions
            Allowed mentions of the message
        wait
            Whether to wait for the message to be sent
        thread_id
            Thread ID to send the message to
        poll
            Poll to send with the message
        tts
            Whether the message should be sent as TTS
        flags
            Flags of the message
        delete_after
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

        self._warn_if_expired()
        r = await self.bot.state.query(
            "POST",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}",
            **payload.to_request()
        )

        msg = self.bot.create_webhook_message_from_data(
            r.response,
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

        self._warn_if_expired()
        r = await self.bot.state.query(
            "GET",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}/messages/@original"
        )

        msg = self.bot.create_webhook_message_from_data(
            r.response,
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

        self._warn_if_expired()
        r = await self.bot.state.query(
            "PATCH",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}/messages/@original",
            **payload.to_request()
        )

        msg = self.bot.create_webhook_message_from_data(
            r.response,
            application_id=self.bot.application_id,  # type: ignore
            token=self._followup_token
        )

        self._original_response = msg
        return msg

    async def delete_original_response(self) -> None:
        """ Delete the original response to the interaction. """
        self._warn_if_expired()
        await self.bot.state.query(
            "DELETE",
            f"/webhooks/{self.bot.application_id}/{self._followup_token}/messages/@original",
            res_method="text"
        )

    async def _create_args(self) -> tuple[list[Member | User | Message | None], dict]:
        match self.command_type:
            case ApplicationCommandType.chat_input:
                return [], await self._create_args_chat_input()

            case ApplicationCommandType.user:
                if self._raw_resolved.get("members"):
                    first: dict | None = next(
                        iter(self._raw_resolved["members"].values()),
                        None
                    )

                    if not first:
                        raise ValueError("User command detected members, but was unable to parse it")
                    if not (guild := self.guild):
                        raise ValueError("While parsing members, guild was not available")

                    first["user"] = next(
                        iter(self._raw_resolved["users"].values()),
                        None
                    )

                    target = self.bot.create_member_from_data(
                        first, guild=guild
                    )

                elif self._raw_resolved.get("users", {}):
                    first: dict | None = next(
                        iter(self._raw_resolved["users"].values()),
                        None
                    )

                    if not first:
                        raise ValueError("User command detected users, but was unable to parse it")

                    target = self.bot.create_user_from_data(first)

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

                            if not (guild := self.guild):
                                raise ValueError("Guild somehow was not available while parsing Member")

                            kwargs[option["name"]] = self.bot.create_member_from_data(
                                member_data,
                                guild=guild
                            )

                        else:
                            kwargs[option["name"]] = self.bot.create_user_from_data(
                                resolved["users"][option["value"]]
                            )

                    case CommandOptionType.channel:
                        type_id = resolved["channels"][option["value"]]["type"]
                        kwargs[option["name"]] = channel_types.get(type_id, BaseChannel)(
                            state=self.bot.state,
                            data=resolved["channels"][option["value"]]
                        )

                    case CommandOptionType.attachment:
                        kwargs[option["name"]] = Attachment(
                            state=self.bot.state,
                            data=resolved["attachments"][option["value"]]
                        )

                    case CommandOptionType.role:
                        if not (guild := self.guild):
                            raise ValueError("Guild somehow was not available while parsing Role")

                        kwargs[option["name"]] = self.bot.create_role_from_data(
                            resolved["roles"][option["value"]],
                            guild=guild
                        )

                    case CommandOptionType.string:
                        kwargs[option["name"]] = option["value"]

                        if has_converter := self.command._converters.get(option["name"], None):
                            conv_type, conv_is_coro = has_converter
                            conv_class = conv_type()
                            if conv_is_coro:
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

    def _parse_user(self, data: dict, guild: "Guild | PartialGuild | None") -> Member | User:
        if data.get("member"):
            return self.bot.create_member_from_data(
                data["member"],
                guild=guild  # type: ignore
            )
        if data.get("user"):
            return self.bot.create_user_from_data(data["user"])
        raise ValueError(
            "Neither member nor user was detected while parsing user"
        )
