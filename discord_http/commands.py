import inspect
import itertools
import logging
import re

from types import UnionType
from typing import (
    TYPE_CHECKING, Union, Protocol,
    Generic, TypeVar, Literal, Any,
    runtime_checkable, get_origin, get_args
)
from collections.abc import Callable, Coroutine

from . import utils
from .channel import (
    TextChannel, VoiceChannel,
    CategoryChannel, NewsThread,
    PublicThread, PrivateThread, StageChannel,
    DirectoryChannel, ForumChannel, StoreChannel,
    NewsChannel, BaseChannel, Thread
)
from .cooldowns import BucketType, Cooldown, CooldownCache
from .enums import ApplicationCommandType, CommandOptionType, ChannelType
from .errors import (
    UserMissingPermissions, BotMissingPermissions, CheckFailed,
    InvalidMember, CommandOnCooldown
)
from .flags import Permissions
from .member import Member
from .message import Attachment
from .object import PartialBase, Snowflake
from .response import BaseResponse, AutocompleteResponse
from .role import Role
from .user import User
import builtins

if TYPE_CHECKING:
    from .client import Client
    from .context import Context

ChoiceT = TypeVar("ChoiceT", str, int, float)
ConverterT = TypeVar("ConverterT", covariant=True)

LocaleTypes = Literal[
    "id", "da", "de", "en-GB", "en-US", "es-ES", "fr",
    "es-419", "hr", "fr", "it", "lt", "hu", "nl", "no", "pl", "pt-BR",
    "ro", "fi", "sv-SE", "vi", "tr", "cs", "el", "bg",
    "ru", "uk", "hi", "th", "zh-CN", "ja", "zh-TW", "ko"
]
ValidLocalesList = get_args(LocaleTypes)

channel_types = {
    BaseChannel: [g for g in ChannelType],
    TextChannel: [ChannelType.guild_text],
    VoiceChannel: [ChannelType.guild_voice],
    CategoryChannel: [ChannelType.guild_category],
    NewsChannel: [ChannelType.guild_news],
    StoreChannel: [ChannelType.guild_store],
    NewsThread: [ChannelType.guild_news_thread],
    PublicThread: [ChannelType.guild_public_thread],
    PrivateThread: [ChannelType.guild_private_thread],
    StageChannel: [ChannelType.guild_stage_voice],
    DirectoryChannel: [ChannelType.guild_directory],
    ForumChannel: [ChannelType.guild_forum],
    Thread: [
        ChannelType.guild_news_thread,
        ChannelType.guild_public_thread,
        ChannelType.guild_private_thread
    ]
}

_log = logging.getLogger(__name__)

__all__ = (
    "Choice",
    "Cog",
    "Command",
    "Converter",
    "Interaction",
    "Listener",
    "PartialCommand",
    "Range",
    "SubGroup",
)


class Cog:
    def __new__(cls, *args, **kwargs):  # noqa: ANN002, ARG004
        """ Create a new cog. """
        commands = {}
        listeners = {}
        interactions = {}

        for base in reversed(cls.__mro__):
            for _, value in base.__dict__.items():
                match value:
                    case x if isinstance(x, SubCommand):
                        continue  # Do not overwrite commands just in case

                    case x if isinstance(x, Command):
                        commands[value.name] = value

                    case x if isinstance(x, SubGroup):
                        commands[value.name] = value

                    case x if isinstance(x, Interaction):
                        interactions[value.custom_id] = value

                    case x if isinstance(x, Listener):
                        listeners[value.name] = value

        cls._cog_commands: dict[str, "Command"] = commands
        cls._cog_interactions: dict[str, "Interaction"] = interactions
        cls._cog_listeners: dict[str, "Listener"] = listeners

        return super().__new__(cls)

    async def _inject(self, bot: "Client") -> None:
        await self.cog_load()

        module_name = self.__class__.__module__

        if module_name not in bot._cogs:
            bot._cogs[module_name] = []
        bot._cogs[module_name].append(self)

        for cmd in self._cog_commands.values():
            cmd.cog = self
            bot.add_command(cmd)

            if isinstance(cmd, SubGroup):
                for subcmd in cmd.subcommands.values():
                    subcmd.cog = self

        for listener in self._cog_listeners.values():
            listener.cog = self
            bot.add_listener(listener)

        for interaction in self._cog_interactions.values():
            interaction.cog = self
            bot.add_interaction(interaction)

    async def _eject(self, bot: "Client") -> None:
        await self.cog_unload()

        module_name = self.__class__.__module__
        if module_name in bot._cogs:
            bot._cogs[module_name].remove(self)

        for cmd in self._cog_commands.values():
            bot.remove_command(cmd)

        for listener in self._cog_listeners.values():
            bot.remove_listener(listener)

        for interaction in self._cog_interactions.values():
            bot.remove_interaction(interaction)

    async def cog_load(self) -> None:
        """ Called before the cog is loaded. """

    async def cog_unload(self) -> None:
        """ Called before the cog is unloaded. """


class PartialCommand(PartialBase):
    def __init__(self, data: dict):
        super().__init__(id=int(data["id"]))
        self.name: str = data["name"]
        self.guild_id: int | None = utils.get_int(data, "guild_id")

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return f"<PartialCommand id={self.id} name={self.name}>"


class LocaleContainer:
    def __init__(
        self,
        key: str,
        name: str,
        description: str | None = None
    ):
        self.key = key
        self.name = name
        self.description = description or "..."


@runtime_checkable
class Converter(Protocol[ConverterT]):
    """
    The base class of converting strings to whatever you desire.

    Instead of needing to implement checks inside the command, you can
    use this to convert the value on runtime, both in sync and async mode.
    """
    async def convert(self, ctx: "Context", value: str) -> ConverterT:
        """
        The function where you implement the logic of converting the value into whatever you need to be outputted in command.

        Parameters
        ----------
        ctx:
            Context of the bot
        value:
            The value returned by the argument in command

        Returns
        -------
            Your converted value
        """
        raise NotImplementedError("convert not implemented")


class Command:
    def __init__(
        self,
        command: Callable,
        name: str,
        description: str | None = None,
        guild_ids: list[Snowflake | int] | None = None,
        guild_install: bool = True,
        user_install: bool = False,
        cmd_type: ApplicationCommandType = ApplicationCommandType.chat_input,
        parent: "SubGroup | None" = None
    ):
        self.id: int | None = None
        self.command = command
        self.cog: "Cog | None" = None
        self.type: int = int(cmd_type)
        self.name = name
        self.description = description
        self.options = []
        self.parent = parent

        self.guild_install = guild_install
        self.user_install = user_install

        self.list_autocompletes: dict[str, Callable] = {}
        self.guild_ids: list[Snowflake | int] = guild_ids or []

        self._converters: dict[str, builtins.type[Converter]] = {}

        self.__list_choices: list[str] = []
        self.__user_objects: dict[str, builtins.type[Member | User]] = {}
        self.__user_member_objects: list[str] = []

        if self.type == ApplicationCommandType.chat_input:
            if self.description is None:
                self.description = command.__doc__ or "No description provided."
            if self.name != self.name.lower():
                raise ValueError("Command names must be lowercase.")
            if not 1 <= len(self.description) <= 100:
                raise ValueError("Command descriptions must be between 1 and 100 characters.")
        else:
            self.description = None

        if (
            self.type is ApplicationCommandType.chat_input.value and
            not self.options
        ):
            sig = inspect.signature(self.command)
            self.options = []

            slicer = 1
            if sig.parameters.get("self", None):
                slicer = 2

            for parameter in itertools.islice(sig.parameters.values(), slicer, None):
                # I am not proud of this, but it works...

                raw_annotation = parameter.annotation
                annotation = utils.unwrap_optional(parameter.annotation)
                origin = get_origin(annotation) or annotation
                args = get_args(annotation)

                option: dict[str, Any] = {}
                channel_options: list[ChannelType] = []

                # Check if there are multiple types, looking for:
                # - Union[Any, ...] / Optional[Any] / type | None  # noqa: ERA001

                if get_origin(annotation) is Union:
                    # Example: Optional[int] -> Union[int, NoneType]
                    # or Union[TextChannel, VoiceChannel]
                    non_none_args = [a for a in args if a is not type(None)]

                    # If it's Optional[T], unwrap to T
                    if len(non_none_args) == 1:
                        annotation = non_none_args[0]
                        origin = get_origin(annotation) or annotation
                        args = get_args(annotation)

                # If it's a union of channel types, handle accordingly
                if get_origin(raw_annotation) in (Union, UnionType) and all(
                    isinstance(a, type) and
                    a in channel_types for a in get_args(raw_annotation)
                ):
                    origin = get_args(raw_annotation)[0]  # Just pick the first one, does not matter
                    for a in get_args(raw_annotation):
                        channel_options.extend(channel_types[a])

                # If it's a union, and first arg is User, then second is Member
                if (
                    get_origin(raw_annotation) in (Union, UnionType) and
                    2 <= len(get_args(raw_annotation)) <= 3 and  # No more than 3 args, no less than 2
                    (
                        # Allow "Member | User" and "User | Member"
                        # But strictly only these two ways
                        (
                            get_args(raw_annotation)[0] is User and
                            get_args(raw_annotation)[1] is Member
                        ) or
                        (
                            get_args(raw_annotation)[1] is User and
                            get_args(raw_annotation)[0] is Member
                        )
                    )
                ):
                    origin = get_args(raw_annotation)[0]
                    self.__user_member_objects.append(parameter.name)

                if origin is User or origin is Member:
                    ptype = CommandOptionType.user
                    self.__user_objects[parameter.name] = origin

                elif origin in channel_types:
                    ptype = CommandOptionType.channel

                    if channel_options:
                        # Union[] was used for channels
                        option.update({
                            "channel_types": [int(i) for i in channel_options]
                        })
                    else:
                        # Just a regular channel type
                        option.update({
                            "channel_types": [
                                int(i) for i in channel_types[origin]
                            ]
                        })

                elif origin == Attachment:
                    ptype = CommandOptionType.attachment

                elif origin == Role:
                    ptype = CommandOptionType.role

                elif isinstance(annotation, type) and issubclass(annotation, Choice):
                    self.__list_choices.append(parameter.name)

                    ptype = {
                        str: CommandOptionType.string,
                        int: CommandOptionType.integer,
                        float: CommandOptionType.number
                    }.get(
                        getattr(annotation, "__choice_type__", str),
                        CommandOptionType.string
                    )

                # If literal, replicate Choice
                elif get_origin(annotation) is Literal:
                    ptype = CommandOptionType.string

                    if not getattr(self.command, "__choices_params__", {}):
                        self.command.__choices_params__ = {}

                    self.command.__choices_params__[parameter.name] = {
                        str(g): str(g) for g in parameter.annotation.__args__
                    }

                # PyRight may not recognize 'Range' due to dynamic typing.
                # Assuming 'origin' is a Range object.
                elif isinstance(annotation, type) and issubclass(annotation, Range):  # type: ignore[arg-type]
                    typ = getattr(annotation, "__range_type__", str)
                    min_val = getattr(annotation, "__range_min__", None)
                    max_val = getattr(annotation, "__range_max__", None)

                    if typ is str:
                        ptype = CommandOptionType.string
                        option.update({
                            "min_length": min_val,
                            "max_length": max_val
                        })

                    elif typ is int or typ is float:
                        ptype = CommandOptionType.integer if typ is int else CommandOptionType.number
                        option.update({
                            "min_value": min_val,
                            "max_value": max_val
                        })

                    else:
                        raise TypeError(
                            f"Range type must be str, int, or float, not {typ}"
                        )

                elif origin is int:
                    ptype = CommandOptionType.integer

                elif origin is bool:
                    ptype = CommandOptionType.boolean

                elif origin is float:
                    ptype = CommandOptionType.number

                elif origin is str:
                    ptype = CommandOptionType.string

                elif isinstance(origin, Converter):
                    self._converters[parameter.name] = origin  # type: ignore
                    ptype = CommandOptionType.string

                else:
                    ptype = CommandOptionType.string

                option.update({
                    "name": parameter.name,
                    "description": "…",
                    "type": ptype.value,
                    "required": (parameter.default == parameter.empty),
                    "autocomplete": False,
                    "name_localizations": {},
                    "description_localizations": {},
                })

                self.options.append(option)

    def __repr__(self) -> str:
        return f"<Command name='{self.name}'>"

    @property
    def mention(self) -> str:
        """ Returns a mentionable string for the command. """
        if self.id:
            return f"</{self.name}:{self.id}>"
        return f"`/{self.name}`"

    @property
    def cooldown(self) -> CooldownCache | None:
        """ Returns the cooldown rule of the command if available. """
        return getattr(self.command, "__cooldown__", None)

    def mention_sub(self, suffix: str) -> str:
        """
        Returns a mentionable string for a subcommand.

        Parameters
        ----------
        suffix:
            The subcommand name.

        Returns
        -------
            The mentionable string.
        """
        if self.id:
            return f"</{self.name} {suffix}:{self.id}>"
        return f"`/{self.name} {suffix}`"

    async def _make_context_and_run(
        self,
        context: "Context"
    ) -> BaseResponse:
        args, kwargs = await context._create_args()

        for name, values in getattr(self.command, "__choices_params__", {}).items():
            if name not in kwargs:
                continue
            if name not in self.__list_choices:
                continue
            kwargs[name] = Choice(
                kwargs[name], values[kwargs[name]]
            )

        for name, value in self.__user_objects.items():
            if name not in kwargs:
                continue

            if name in self.__user_member_objects:
                # Take whatever was first, go for it
                # Can be either Member or User
                continue

            if (
                isinstance(kwargs[name], Member) and
                value is User
            ):
                # Force User if command is expecting a User, but got a Member
                kwargs[name] = kwargs[name]._user

            if not isinstance(kwargs[name], value):
                raise InvalidMember(
                    f"User given by the command `(parameter: {name})` "
                    "is not a member of a guild."
                )

        result = await self.run(context, *args, **kwargs)

        if not isinstance(result, BaseResponse):
            raise TypeError(
                f"Command {self.name} must return a "
                f"Response object, not {type(result)}."
            )

        return result

    def _has_permissions(self, ctx: "Context") -> Permissions:
        perms: Permissions | None = getattr(
            self.command, "__has_permissions__", None
        )

        if perms is None:
            return Permissions(0)

        resolved_perms: Permissions | None = getattr(
            ctx.user, "resolved_permissions", None
        )

        if resolved_perms is None:
            return Permissions(0)

        if Permissions.administrator in resolved_perms:
            return Permissions(0)

        return Permissions(sum([
            flag.value for flag in perms
            if flag not in resolved_perms
        ]))

    def _bot_has_permissions(self, ctx: "Context") -> Permissions:
        perms: Permissions | None = getattr(
            self.command, "__bot_has_permissions__", None
        )

        if perms is None:
            return Permissions(0)
        if Permissions.administrator in ctx.app_permissions:
            return Permissions(0)

        return Permissions(sum([
            flag.value for flag in perms
            if flag not in ctx.app_permissions
        ]))

    async def _command_checks(self, ctx: "Context") -> bool:
        checks: list[Callable] = getattr(
            self.command, "__checks__", []
        )

        for g in checks:
            if inspect.iscoroutinefunction(g):
                result = await g(ctx)
            else:
                result = g(ctx)

            if result is not True:
                raise CheckFailed(f"Check {g.__name__} failed.")

        return True

    async def _before_invoke(self, ctx: "Context") -> bool:
        before = getattr(self.command, "__before_invoke__", None)
        if before is None:
            return True

        if inspect.iscoroutinefunction(before):
            result = await before(ctx)
        else:
            result = before(ctx)

        if result is not True:
            raise CheckFailed("Before invoke failed.")

        return True

    async def _after_invoke(self, ctx: "Context") -> None:
        after = getattr(self.command, "__after_invoke__", None)
        if after is None:
            return

        async def _run_background() -> None:
            if inspect.iscoroutinefunction(after):
                await after(ctx)
            else:
                after(ctx)

        ctx.bot.loop.create_task(
            _run_background()
        )

    def _cooldown_checker(self, ctx: "Context") -> None:
        if self.cooldown is None:
            return

        current = ctx.created_at.timestamp()
        bucket = self.cooldown.get_bucket(ctx, current)
        retry_after = bucket.update_rate_limit(current)

        if not retry_after:
            return  # Not rate limited, good to go
        raise CommandOnCooldown(bucket, retry_after)

    async def run(
        self,
        context: "Context",
        *args,  # noqa: ANN002
        **kwargs
    ) -> BaseResponse:
        """
        Runs the command.

        Parameters
        ----------
        context:
            The context of the command.
        *args:
            The arguments of the command.
        **kwargs:
            The keyword arguments of the command.

        Returns
        -------
            The return type of the command, used by backend.py (Quart)

        Raises
        ------
        `UserMissingPermissions`
            User that ran the command is missing permissions.
        `BotMissingPermissions`
            Bot is missing permissions.
        """
        # Check before invoke
        await self._before_invoke(context)

        # Check custom checks
        await self._command_checks(context)

        # Check user permissions
        perms_user = self._has_permissions(context)
        if perms_user != Permissions(0):
            raise UserMissingPermissions(perms_user)

        # Check bot permissions
        perms_bot = self._bot_has_permissions(context)
        if perms_bot != Permissions(0):
            raise BotMissingPermissions(perms_bot)

        # Check cooldown
        self._cooldown_checker(context)

        if self.cog is not None:
            response = await self.command(self.cog, context, *args, **kwargs)
        else:
            response = await self.command(context, *args, **kwargs)

        # Execute after invoke
        if getattr(self.command, "__after_invoke__", None):
            context.bot.loop.create_task(
                self._after_invoke(context)
            )

        return response

    async def run_autocomplete(
        self,
        context: "Context",
        name: str,
        current: str
    ) -> dict:
        """
        Runs the autocomplete.

        Parameters
        ----------
        context:
            Context object for the command
        name:
            Name of the option
        current:
            Current value of the option

        Returns
        -------
            The return type of the command, used by backend.py (Quart)

        Raises
        ------
        `TypeError`
            Autocomplete must return an AutocompleteResponse object
        """
        if self.cog is not None:
            result = await self.list_autocompletes[name](self.cog, context, current)
        else:
            result = await self.list_autocompletes[name](context, current)

        if isinstance(result, AutocompleteResponse):
            return result.to_dict()
        raise TypeError("Autocomplete must return an AutocompleteResponse object.")

    def _find_option(self, name: str) -> dict | None:
        return next((g for g in self.options if g["name"] == name), None)

    def to_dict(self) -> dict:
        """
        Converts the Discord command to a dict.

        Returns
        -------
            The dict of the command.
        """
        extra_locale = getattr(self.command, "__locales__", {})
        extra_params = getattr(self.command, "__describe_params__", {})
        extra_choices = getattr(self.command, "__choices_params__", {})
        default_permissions_: Permissions | None = getattr(
            self.command, "__default_permissions__", None
        )

        integration_types = []
        if self.guild_install:
            integration_types.append(0)
        if self.user_install:
            integration_types.append(1)

        integration_contexts = getattr(self.command, "__integration_contexts__", [0, 1, 2])

        # Types
        extra_locale: dict[LocaleTypes, list[LocaleContainer]]

        data = {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "options": self.options,
            "nsfw": getattr(self.command, "__nsfw__", False),
            "name_localizations": {},
            "description_localizations": {},
            "contexts": integration_contexts
        }

        if integration_types:
            data["integration_types"] = integration_types

        for key, value in extra_locale.items():
            for loc in value:
                if loc.key == "_":
                    data["name_localizations"][key] = loc.name
                    data["description_localizations"][key] = loc.description
                    continue

                opt = self._find_option(loc.key)
                if not opt:
                    _log.warning(
                        f"{self.name} -> {loc.key}: "
                        "Option not found in command, skipping..."
                    )
                    continue

                opt["name_localizations"][key] = loc.name
                opt["description_localizations"][key] = loc.description

        if default_permissions_:
            data["default_member_permissions"] = str(default_permissions_.value)

        for key, value in extra_params.items():
            opt = self._find_option(key)
            if not opt:
                continue

            opt["description"] = value

        for key, value in extra_choices.items():
            opt = self._find_option(key)
            if not opt:
                continue

            opt["choices"] = [
                {"name": v, "value": k}
                for k, v in value.items()
            ]

        return data

    def autocomplete(self, name: str) -> Callable[[Callable], Callable]:
        """
        Decorator to set an option as an autocomplete.

        The function must at the end, return a `Response.send_autocomplete()` object.

        Example usage

        .. code-block:: python

            @commands.command()
            async def ping(ctx, options: str):
                await ctx.send(f"You chose {options}")

            @ping.autocomplete("options")
            async def search_autocomplete(ctx, current: str):
                return ctx.response.send_autocomplete({
                    "key": "Value shown to user",
                    "feeling_lucky_tm": "I'm feeling lucky!"
                })

        Parameters
        ----------
        name:
            Name of the option to set as an autocomplete.
        """
        def wrapper(func: Callable) -> Callable:
            find_option = next((
                option for option in self.options
                if option["name"] == name
            ), None)

            if not find_option:
                raise ValueError(f"Option {name} in command {self.name} not found.")

            find_option["autocomplete"] = True
            self.list_autocompletes[name] = func
            return func

        return wrapper


class SubCommand(Command):
    def __init__(
        self,
        func: Callable,
        *,
        name: str,
        description: str | None = None,
        guild_install: bool = True,
        user_install: bool = False,
        guild_ids: list[Snowflake | int] | None = None,
        parent: "SubGroup | None " = None
    ):
        super().__init__(
            func,
            name=name,
            description=description,
            guild_install=guild_install,
            user_install=user_install,
            guild_ids=guild_ids,
            parent=parent
        )

    def __repr__(self) -> str:
        return f"<SubCommand name='{self.name}'>"


class SubGroup(Command):
    def __init__(
        self,
        *,
        name: str,
        description: str | None = None,
        guild_ids: list[Snowflake | int] | None = None,
        guild_install: bool = True,
        user_install: bool = False,
        parent: "SubGroup | None" = None
    ):
        self.name = name
        self.description = description or "..."  # Only used to make Discord happy
        self.guild_ids: list[Snowflake | int] = guild_ids or []
        self.type = int(ApplicationCommandType.chat_input)
        self.cog: "Cog | None" = None
        self.subcommands: dict[str, SubCommand | SubGroup] = {}
        self.guild_install = guild_install
        self.user_install = user_install
        self.parent: "SubGroup | None" = parent

    def __repr__(self) -> str:
        subs = [g for g in self.subcommands.values()]
        return f"<SubGroup name='{self.name}', subcommands={subs}>"

    def command(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        guild_ids: list[Snowflake | int] | None = None,
        guild_install: bool = True,
        user_install: bool = False,
    ) -> Callable[[Callable], SubCommand]:
        """
        Decorator to add a subcommand to a subcommand group.

        Parameters
        ----------
        name:
            Name of the command (defaults to the function name)
        description:
            Description of the command (defaults to the function docstring)
        guild_ids:
            List of guild IDs to register the command in
        user_install:
            Whether the command can be installed by users or not
        guild_install:
            Whether the command can be installed by guilds or not
        """
        def decorator(func: Callable) -> SubCommand:
            subcommand = SubCommand(
                func,
                name=name or func.__name__,
                description=description,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install,
                parent=self
            )
            self.subcommands[subcommand.name] = subcommand
            return subcommand

        return decorator

    def group(
        self,
        name: str | None = None,
        *,
        description: str | None = None
    ) -> Callable[[Callable], "SubGroup"]:
        """
        Decorator to add a subcommand group to a subcommand group.

        Parameters
        ----------
        name:
            Name of the subcommand group (defaults to the function name)
        description:
            Description of the subcommand group (defaults to the function docstring)
        """
        def decorator(func: Callable) -> "SubGroup":
            subgroup = SubGroup(
                name=name or func.__name__,
                description=description,
                parent=self
            )
            self.subcommands[subgroup.name] = subgroup
            return subgroup

        return decorator

    def add_group(self, name: str) -> "SubGroup":
        """
        Adds a subcommand group to a subcommand group.

        Parameters
        ----------
        name:
            Name of the subcommand group

        Returns
        -------
            The subcommand group
        """
        subgroup = SubGroup(name=name)
        self.subcommands[subgroup.name] = subgroup
        return subgroup

    @property
    def options(self) -> list[dict]:
        """ Returns the options of the subcommand group. """
        def build_options(subcommands: dict) -> list[dict]:
            options = []
            for cmd in subcommands.values():
                data = cmd.to_dict()
                if isinstance(cmd, SubGroup):
                    data["type"] = int(CommandOptionType.sub_command_group)
                    # Recursively build options for nested subcommand groups
                    data["options"] = build_options(cmd.subcommands)
                else:
                    data["type"] = int(CommandOptionType.sub_command)

                options.append(data)
            return options

        return build_options(self.subcommands)


class Interaction:
    def __init__(
        self,
        func: Callable,
        custom_id: str,
        *,
        regex: bool = False
    ):
        self.func: Callable = func
        self.custom_id: str = custom_id
        self.regex: bool = regex

        self.cog: "Cog | None" = None

        self._pattern: re.Pattern | None = (
            re.compile(custom_id)
            if self.regex else None
        )

    def __repr__(self) -> str:
        return (
            f"<Interaction custom_id='{self.custom_id}' "
            f"regex={self.regex}>"
        )

    def match(self, custom_id: str) -> bool:
        """
        Matches the custom ID with the interaction.

        Will always return False if the interaction is not a regex.

        Parameters
        ----------
        custom_id:
            The custom ID to match.

        Returns
        -------
            Whether the custom ID matched or not.
        """
        if not self.regex:
            return False
        return bool(self._pattern.match(custom_id))

    async def run(self, context: "Context") -> BaseResponse:
        """
        Runs the interaction.

        Parameters
        ----------
        context:
            The context of the interaction.

        Returns
        -------
            The return type of the interaction, used by backend.py (Quart)

        Raises
        ------
        `TypeError`
            Interaction must be a Response object
        """
        if self.cog is not None:
            result = await self.func(self.cog, context)
        else:
            result = await self.func(context)

        if not isinstance(result, BaseResponse):
            raise TypeError("Interaction must be a Response object")

        return result


class Listener:
    def __init__(
        self,
        *,
        name: str,
        coro: Callable
    ):
        self.name = name
        self.coro = coro
        self.cog: "Cog | None" = None

    def __repr__(self) -> str:
        return f"<Listener name='{self.name}'>"

    async def run(self, *args, **kwargs) -> None:  # noqa: ANN002
        """ Runs the listener. """
        if self.cog is not None:
            await self.coro(self.cog, *args, **kwargs)
        else:
            await self.coro(*args, **kwargs)


class ChoiceMeta(type):
    def __getitem__(cls, item_type: type):
        if item_type not in (str, int, float):
            raise TypeError("Choice type must be str, int, or float")

        class _Choice(cls, metaclass=ChoiceMeta):
            __choice_type__ = item_type
            __origin__ = Choice

            def __init__(self, key: ChoiceT, value: ChoiceT):
                super().__init__(key, value)

        _Choice.__name__ = f"Choice[{item_type.__name__}]"
        return _Choice


class Choice(Generic[ChoiceT], metaclass=ChoiceMeta):
    """
    Makes it possible to access both the name and value of a choice.

    Defaults to a string type

    Paramaters
    ----------
    key:
        The key of the choice from your dict.
    value:
        The value of your choice (the one that is shown to public)
    """
    def __init__(self, key: ChoiceT, value: ChoiceT):
        self.key: ChoiceT = key
        self.value: ChoiceT = value
        self.type: CommandOptionType = CommandOptionType.string

        if isinstance(key, str):
            self.type = CommandOptionType.string
        elif isinstance(key, int):
            self.type = CommandOptionType.integer
        elif isinstance(key, float):
            self.type = CommandOptionType.number
        else:
            raise TypeError(f"Invalid key type: {type(key)}")

    def __str__(self) -> str:
        return str(self.key)


# Making it so pyright understands that the range type is a normal type
if TYPE_CHECKING:
    from typing import Annotated as Range

else:
    class RangeMeta(type):
        def __getitem__(cls, item: tuple[str | int | float, ...]):
            if not isinstance(item, tuple):
                raise TypeError("Range[...] must be a tuple of (type, min, max)")

            if len(item) == 2:
                item = (*item, None)
            elif len(item) != 3:
                raise TypeError("Range must be a tuple of length 2 or 3")

            obj_type, min_val, max_val = item

            if min_val is None and max_val is None:
                raise TypeError("Range must have a minimum or maximum value")

            if min_val is not None and max_val is not None and type(min_val) is not type(max_val):
                raise TypeError("Range min and max must be the same type")

            if obj_type not in (str, int, float):
                raise TypeError("Range type must be str, int, or float")

            class _Range(cls, metaclass=RangeMeta):
                __range_type__ = obj_type
                __range_min__ = min_val
                __range_max__ = max_val
                __origin__ = Range

            return _Range

    class Range(metaclass=RangeMeta):
        pass


def command(
    name: str | None = None,
    *,
    description: str | None = None,
    guild_ids: list[Snowflake | int] | None = None,
    guild_install: bool = True,
    user_install: bool = False,
) -> Callable[[Callable], Command]:
    """
    Decorator to register a command.

    Parameters
    ----------
    name:
        Name of the command (defaults to the function name)
    description:
        Description of the command (defaults to the function docstring)
    guild_ids:
        List of guild IDs to register the command in
    user_install:
        Whether the command can be installed by users or not
    guild_install:
        Whether the command can be installed by guilds or not
    """
    def decorator(func: Callable) -> Command:
        return Command(
            func,
            name=name or func.__name__,
            description=description,
            guild_ids=guild_ids,
            guild_install=guild_install,
            user_install=user_install
        )

    return decorator


def user_command(
    name: str | None = None,
    *,
    guild_ids: list[Snowflake | int] | None = None,
    guild_install: bool = True,
    user_install: bool = False,
) -> Callable[[Callable], Command]:
    """
    Decorator to register a user command.

    Example usage

    .. code-block:: python

        @user_command()
        async def content(ctx, user: Union[Member, User]):
            await ctx.send(f"Target: {user.name}")

    Parameters
    ----------
    name:
        Name of the command (defaults to the function name)
    guild_ids:
        List of guild IDs to register the command in
    user_install:
        Whether the command can be installed by users or not
    guild_install:
        Whether the command can be installed by guilds or not
    """
    def decorator(func: Callable) -> Command:
        return Command(
            func,
            name=name or func.__name__,
            cmd_type=ApplicationCommandType.user,
            guild_ids=guild_ids,
            guild_install=guild_install,
            user_install=user_install
        )

    return decorator


def cooldown(
    rate: int,
    per: float,
    *,
    type: BucketType | None = None  # noqa: A002
) -> Callable[[Callable], Callable]:
    """
    Decorator to set a cooldown for a command.

    Example usage

    .. code-block:: python

        @commands.command()
        @commands.cooldown(1, 5.0)
        async def ping(ctx):
            await ctx.send("Pong!")

    Parameters
    ----------
    rate:
        The number of times the command can be used within the cooldown period
    per:
        The cooldown period in seconds
    type:
        The bucket type to use for the cooldown
        If not set, it will be using default, which is a global cooldown
    """
    if type is None:
        type = BucketType.default  # noqa: A001
    if not isinstance(type, BucketType):
        raise TypeError("Key must be a BucketType")

    def decorator(func: Callable) -> Callable:
        func.__cooldown__ = CooldownCache(
            Cooldown(rate, per), type
        )
        return func

    return decorator


def message_command(
    name: str | None = None,
    *,
    guild_ids: list[Snowflake | int] | None = None,
    guild_install: bool = True,
    user_install: bool = False,
) -> Callable[[Callable], Command]:
    """
    Decorator to register a message command.

    Example usage

    .. code-block:: python

        @message_command()
        async def content(ctx, msg: Message):
            await ctx.send(f"Content: {msg.content}")

    Parameters
    ----------
    name:
        Name of the command (defaults to the function name)
    guild_ids:
        List of guild IDs to register the command in
    user_install:
        Whether the command can be installed by users or not
    guild_install:
        Whether the command can be installed by guilds or not
    """
    def decorator(func: Callable) -> Command:
        return Command(
            func,
            name=name or func.__name__,
            cmd_type=ApplicationCommandType.message,
            guild_ids=guild_ids,
            guild_install=guild_install,
            user_install=user_install
        )

    return decorator


def before_invoke(invoke: Callable) -> Callable:
    """
    Decorator to register a function to be called before the command is invoked.

    If it returns anything other than `True`, the command will not be invoked.
    However if you raise a `CheckFailure` exception, it will fail and you can add a message to it.

    Parameters
    ----------
    invoke: Callable
        The function to be called before the command is invoked.
    """
    def decorator(func: Callable) -> Callable:
        func.__before_invoke__ = invoke
        return func

    return decorator


def after_invoke(invoke: Callable) -> Callable:
    """
    Decorator to register a function to be called after the command is invoked.

    This acts like before_invoke, however it only runs after the command has been invoked successfully.

    Parameters
    ----------
    invoke: Callable
        The function to be called after the command is invoked.
    """
    def decorator(func: Callable) -> Callable:
        func.__after_invoke__ = invoke
        return func

    return decorator


def locales(
    translations: dict[
        LocaleTypes,
        dict[
            str,
            list[str] | tuple[str] | tuple[str, str]
        ]
    ]
) -> Callable[[Callable], Callable]:
    """
    Decorator to set translations for a command.

    _ = Reserved for the root command name and description.

    Example usage:

    .. code-block:: python

        @commands.command(name="ping")
        @commands.locales({
            # Norwegian
            "no": {
                "_": ("ping", "Sender en 'pong' melding")
                "funny": ("morsomt", "Morsomt svar")
            }
        })
        async def ping(ctx, funny: str):
            await ctx.send(f"pong {funny}")

    Parameters
    ----------
    translations:
        The translations for the command name, description, and options.
    """
    def decorator(func: Callable) -> Callable:
        name = func.__name__
        container = {}

        for key, value in translations.items():
            temp_value: list[LocaleContainer] = []

            if not isinstance(key, str):
                _log.error(f"{name}: Translation key must be a string, not a {type(key)}")
                continue

            if key not in ValidLocalesList:
                _log.warning(f"{name}: Unsupported locale {key} skipped (might be a typo)")
                continue

            if not isinstance(value, dict):
                _log.error(f"{name} -> {key}: Translation value must be a dict, not a {type(value)}")
                continue

            for tname, tvalues in value.items():
                if not isinstance(tname, str):
                    _log.error(f"{name} -> {key}: Translation option must be a string, not a {type(tname)}")
                    continue

                if not isinstance(tvalues, list | tuple):
                    _log.error(f"{name} -> {key} -> {tname}: Translation values must be a list or tuple, not a {type(tvalues)}")
                    continue

                if len(tvalues) < 1:
                    _log.error(f"{name} -> {key} -> {tname}: Translation values must have a minimum of 1 value")
                    continue

                temp_value.append(
                    LocaleContainer(
                        tname,
                        *tvalues[:2]  # Only use the first 2 values, ignore the rest
                    )
                )

            if not temp_value:
                _log.warning(f"{name} -> {key}: Found an empty translation dict, skipping...")
                continue

            container[key] = temp_value

        func.__locales__ = container
        return func

    return decorator


def group(
    name: str | None = None,
    *,
    description: str | None = None,
    guild_ids: list[Snowflake | int] | None = None,
    guild_install: bool = True,
    user_install: bool = False,
) -> Callable[[Callable], SubGroup]:
    """
    Decorator to register a command group.

    Parameters
    ----------
    name:
        Name of the command group (defaults to the function name)
    description:
        Description of the command group (defaults to the function docstring)
    guild_ids:
        List of guild IDs to register the command group in
    user_install:
        Whether the command group can be installed by users or not
    guild_install:
        Whether the command group can be installed by guilds or not
    """
    def decorator(func: Callable) -> SubGroup:
        return SubGroup(
            name=name or func.__name__,
            description=description,
            guild_ids=guild_ids,
            guild_install=guild_install,
            user_install=user_install
        )

    return decorator


def describe(**kwargs: str) -> Callable:
    """
    Decorator to set descriptions for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.describe(user="User to ping")
        async def ping(ctx, user: Member):
            await ctx.send(f"Pinged {user.mention}")
    """
    def decorator(func: Callable) -> Callable:
        func.__describe_params__ = kwargs
        return func

    return decorator


def allow_contexts(
    *,
    guild: bool = True,
    bot_dm: bool = True,
    private_dm: bool = True
) -> Callable:
    """
    Decorator to set the places you are allowed to use the command.

    Can only be used if the Command has user_install set to True.

    Parameters
    ----------
    guild:
        Weather the command can be used in guilds.
    bot_dm:
        Weather the command can be used in bot DMs.
    private_dm:
        Weather the command can be used in private DMs.
    """
    def decorator(func: Callable) -> Callable:
        func.__integration_contexts__ = []

        if guild:
            func.__integration_contexts__.append(0)
        if bot_dm:
            func.__integration_contexts__.append(1)
        if private_dm:
            func.__integration_contexts__.append(2)

        return func
    return decorator


def choices(
    **kwargs: dict[
        str | int | float,
        str | int | float
    ]
) -> Callable:
    """
    Decorator to set choices for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.choices(
            options={
                "opt1": "Choice 1",
                "opt2": "Choice 2",
                ...
            }
        )
        async def ping(ctx, options: Choice[str]):
            await ctx.send(f"You chose {choice.value}")
    """
    def decorator(func: Callable) -> Callable:
        for k, v in kwargs.items():
            if not isinstance(v, dict):
                raise TypeError(
                    f"Choice {k} must be a dict, not a {type(v)}"
                )

        func.__choices_params__ = kwargs
        return func

    return decorator


def guild_only() -> Callable:
    """
    Decorator to set a command as guild only.

    This is a alias to two particular functions:
    - `commands.allow_contexts(guild=True, bot_dm=False, private_dm=False)`
    - `commands.check(...)` (which checks for Context.guild to be available)
    """
    def _guild_only_check(ctx: "Context") -> bool:
        if not ctx.guild:
            raise CheckFailed("Command can only be used in servers")
        return True

    def decorator(func: Callable) -> Callable:
        check_list = getattr(func, "__checks__", [])
        check_list.append(_guild_only_check)
        func.__checks__ = check_list
        func.__integration_contexts__ = [0]
        return func

    return decorator


def is_nsfw() -> Callable:
    """ Decorator to set a command as NSFW. """
    def decorator(func: Callable) -> Callable:
        func.__nsfw__ = True
        return func

    return decorator


def default_permissions(*args: Permissions | str) -> Callable:
    """ Decorator to set default permissions for a command. """
    def decorator(func: Callable) -> Callable:
        if not args:
            return func

        if isinstance(args[0], Permissions):
            func.__default_permissions__ = args[0]
        else:
            if any(not isinstance(arg, str) for arg in args):
                raise TypeError(
                    "All permissions must be strings "
                    "or only 1 Permissions object"
                )

            func.__default_permissions__ = Permissions.from_names(
                *args  # type: ignore
            )

        return func

    return decorator


def has_permissions(*args: Permissions | str) -> Callable:
    """
    Decorator to set permissions for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.has_permissions("manage_messages")
        async def ban(ctx, user: Member):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if not args:
            return func

        if isinstance(args[0], Permissions):
            func.__has_permissions__ = args[0]
        else:
            if any(not isinstance(arg, str) for arg in args):
                raise TypeError(
                    "All permissions must be strings "
                    "or only 1 Permissions object"
                )

            func.__has_permissions__ = Permissions.from_names(
                *args  # type: ignore
            )

        return func

    return decorator


def bot_has_permissions(*args: Permissions | str) -> Callable:
    """
    Decorator to set permissions for a command.

    Example usage:

    .. code-block:: python

        @commands.command()
        @commands.bot_has_permissions("embed_links")
        async def cat(ctx):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if not args:
            return func

        if isinstance(args[0], Permissions):
            func.__bot_has_permissions__ = args[0]
        else:
            if any(not isinstance(arg, str) for arg in args):
                raise TypeError(
                    "All permissions must be strings "
                    "or only 1 Permissions object"
                )

            func.__bot_has_permissions__ = Permissions.from_names(
                *args  # type: ignore
            )

        return func

    return decorator


def check(predicate: Callable | Coroutine) -> Callable:
    """
    Decorator to set a check for a command.

    Example usage:

    .. code-block:: python

        def is_owner(ctx):
            return ctx.author.id == 123456789

        @commands.command()
        @commands.check(is_owner)
        async def foo(ctx):
            ...
    """
    def decorator(func: Callable) -> Callable:
        check_list = getattr(func, "__checks__", [])
        check_list.append(predicate)
        func.__checks__ = check_list
        return func

    return decorator


def interaction(
    custom_id: str,
    *,
    regex: bool = False
) -> Callable:
    """
    Decorator to register an interaction.

    This supports the usage of regex to match multiple custom IDs.

    Parameters
    ----------
    custom_id:
        The custom ID of the interaction. (can be partial, aka. regex)
    regex:
        Whether the custom_id is a regex or not
    """
    def decorator(func: Callable) -> Interaction:
        return Interaction(
            func,
            custom_id=custom_id,
            regex=regex
        )

    return decorator


def listener(name: str | None = None) -> Callable:
    """
    Decorator to register a listener.

    Parameters
    ----------
    name:
        Name of the listener (defaults to the function name)

    Raises
    ------
    `TypeError`
        - If name was not a string
        - If the listener was not a coroutine function
    """
    if name is not None and not isinstance(name, str):
        raise TypeError(f"Listener name must be a string, not {type(name)}")

    def decorator(func: Callable) -> Listener:
        actual = func
        if isinstance(actual, staticmethod):
            actual = actual.__func__
        if not inspect.iscoroutinefunction(actual):
            raise TypeError("Listeners has to be coroutine functions")
        return Listener(
            name=name or actual.__name__,
            coro=func
        )

    return decorator
