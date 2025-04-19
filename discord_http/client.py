import asyncio
import importlib
import inspect
import logging

from datetime import datetime
from typing import (
    Optional, Any,
    TYPE_CHECKING, TypeVar
)
from collections.abc import Callable, AsyncIterator, Coroutine

from . import utils, __version__
from .automod import PartialAutoModRule, AutoModRule
from .backend import DiscordHTTP
from .channel import PartialChannel, BaseChannel
from .commands import Command, Interaction, Listener, Cog, SubGroup
from .context import Context
from .emoji import PartialEmoji, Emoji
from .entitlements import PartialSKU, SKU, PartialEntitlements, Entitlements
from .enums import ApplicationCommandType
from .errors import CheckFailed
from .file import File
from .gateway.cache import Cache
from .guild import PartialGuild, Guild, PartialScheduledEvent, ScheduledEvent
from .http import DiscordAPI, HTTPResponse
from .invite import PartialInvite, Invite
from .member import PartialMember, Member
from .mentions import AllowedMentions
from .message import PartialMessage, Message
from .object import Snowflake
from .role import PartialRole
from .soundboard import SoundboardSound, PartialSoundboardSound
from .sticker import PartialSticker, Sticker
from .user import User, PartialUser, UserClient
from .view import InteractionStorage
from .voice import PartialVoiceState, VoiceState
from .webhook import PartialWebhook, Webhook

if TYPE_CHECKING:
    from .gateway.client import GatewayClient
    from .gateway.flags import GatewayCacheFlags, Intents
    from .gateway.object import PlayingStatus

_log = logging.getLogger(__name__)

T = TypeVar("T")
Coro = Coroutine[Any, Any, T]

__all__ = (
    "Client",
)


class Client:
    def __init__(
        self,
        *,
        token: str,
        application_id: int | None = None,
        public_key: str | None = None,
        guild_id: int | None = None,
        sync: bool = False,
        api_version: int = 10,
        loop: asyncio.AbstractEventLoop | None = None,
        allowed_mentions: AllowedMentions | None = None,
        enable_gateway: bool = False,
        automatic_shards: bool = True,
        playing_status: "PlayingStatus | None" = None,
        chunk_guilds_on_startup: bool = False,
        guild_ready_timeout: float = 2.0,
        gateway_cache: Optional["GatewayCacheFlags"] = None,
        intents: Optional["Intents"] = None,
        logging_level: int = logging.INFO,
        call_after_delay: float | int = 0.1,
        disable_default_get_path: bool = False,
        debug_events: bool = False
    ):
        """
        The main client class for discord.http.

        Parameters
        ----------
        token:
            Discord bot token
        application_id:
            Application ID of the bot, not the User ID
        public_key:
            Public key of the bot, used for validating interactions
        guild_id:
            Guild ID to sync commands to, if not provided, it will sync to global
        sync:
            Whether to sync commands on boot or not
        api_version:
            API version to use for both HTTP and WS, if not provided, it will use the default (10)
        loop:
            Event loop to use, if not provided, it will use `asyncio.get_running_loop()`
        allowed_mentions:
            Allowed mentions to use, if not provided, it will use `AllowedMentions.all()`
        enable_gateway:
            Whether to enable the gateway or not, which runs in the background
        automatic_shards:
            Whether to automatically shard the bot or not
        playing_status:
            The playing status to use, if not provided, it will use `None`.
            This is only used if `enable_gateway` is `True`.
        chunk_guilds_on_startup:
            Whether to chunk guilds or not when booting, which will reduce the amount of requests
        guild_ready_timeout:
            **Gateway**: How long to wait for last GUILD_CREATE to be recieved
            before triggering shard ready
        gateway_cache:
            How the gateway should cache, only used if `enable_gateway` is `True`.
            Leave empty to use no cache.
        intents:
            Intents to use, only used if `enable_gateway` is `True`
        logging_level:
            Logging level to use, if not provided, it will use `logging.INFO`
        call_after_delay:
            How long to wait before calling the `call_after` coroutine
        debug_events:
            Whether to log events or not, if not provided, `on_raw_*` events will not be useable
        disable_default_get_path:
            Whether to disable the default GET path or not, if not provided, it will use `False`.
            The default GET path only provides information about the bot and when it was last rebooted.
            Usually a great tool to just validate that your bot is online.
        """
        self.application_id: int | None = application_id
        self.api_version: int = int(api_version)
        self.public_key: str | None = public_key
        self.token: str = token
        self.automatic_shards: bool = automatic_shards
        self.guild_id: int | None = guild_id
        self.sync: bool = sync
        self.logging_level: int = logging_level
        self.debug_events: bool = debug_events
        self.enable_gateway: bool = enable_gateway
        self.playing_status: "PlayingStatus | None" = playing_status
        self.guild_ready_timeout: float = guild_ready_timeout
        self.chunk_guilds_on_startup: bool = chunk_guilds_on_startup
        self.call_after_delay: float | int = call_after_delay
        self.intents: Intents | None = intents

        self.gateway: "GatewayClient | None" = None
        self.disable_default_get_path: bool = disable_default_get_path

        try:
            self.loop: asyncio.AbstractEventLoop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.commands: dict[str, Command] = {}
        self.listeners: list[Listener] = []
        self.interactions: dict[str, Interaction] = {}
        self.interactions_regex: dict[str, Interaction] = {}

        self._global_cmd_checks: list[Callable] = []

        self._gateway_cache: "GatewayCacheFlags | None" = gateway_cache
        self._ready: asyncio.Event | None = asyncio.Event()
        self._shards_ready: asyncio.Event | None = asyncio.Event()
        self._user_object: UserClient | None = None

        self._context: Callable = Context

        self.cache: Cache = Cache(client=self)
        self.state: DiscordAPI = DiscordAPI(client=self)
        self.backend: DiscordHTTP = DiscordHTTP(client=self)

        self._view_storage: dict[str | int, InteractionStorage] = {}
        self._default_allowed_mentions = allowed_mentions or AllowedMentions.all()

        self._cogs: dict[str, list[Cog]] = {}

        utils.setup_logger(level=self.logging_level)

    async def _run_global_checks(self, ctx: Context) -> bool:
        for g in self._global_cmd_checks:
            if inspect.iscoroutinefunction(g):
                result = await g(ctx)
            else:
                result = g(ctx)

            if result is not True:
                raise CheckFailed(f"Check {g.__name__} failed.")

        return True

    async def _run_event(
        self,
        listener: "Listener",
        event_name: str,
        *args, **kwargs,  # noqa: ANN002
    ) -> None:
        try:
            if listener.cog is not None:
                await listener.coro(listener.cog, *args, **kwargs)
            else:
                await listener.coro(*args, **kwargs)

        except asyncio.CancelledError:
            pass

        except Exception as e:

            try:
                if self.has_any_dispatch("event_error"):
                    self.dispatch("event_error", self, e)
                else:
                    _log.error(
                        f"Error in {event_name} event",
                        exc_info=e
                    )
            except asyncio.CancelledError:
                pass

    async def _prepare_bot(self) -> None:
        """ Run prepare_setup() before boot to make the user set up needed vars. """
        await self.state.http._create_session()

        try:
            client_object = await self._prepare_me()
        except RuntimeError as e:
            # Make sure the error is readable and stop HTTP server here
            _log.error(e)
            await self.backend.shutdown()
            return

        await self.setup_hook()
        await self._prepare_commands()

        self._ready.set()

        if self.has_any_dispatch("ready"):
            self.dispatch("ready", client_object)
        else:
            _log.info(f"discord.http v{__version__} is now ready")

        if self.enable_gateway:
            # To avoid circular import, import here
            from .gateway import GatewayClient
            self.gateway = GatewayClient(
                bot=self,
                intents=self.intents,
                automatic_shards=self.automatic_shards,
                cache_flags=self._gateway_cache
            )
            self.gateway.start()
            _log.info("Starting discord.http/gateway client")

    async def __cleanup(self) -> None:
        """ Called when the bot is shutting down. """
        await self.state.http._close_session()

        if self.gateway:
            await self.gateway.close()

    def _update_ids(self, data: dict) -> None:
        for g in data:
            cmd = self.commands.get(g["name"], None)
            if not cmd:
                continue
            cmd.id = int(g["id"])

    def _schedule_event(
        self,
        listener: "Listener",
        event_name: str,
        *args, **kwargs  # noqa: ANN002
    ) -> asyncio.Task:
        """ Schedules an event to be dispatched. """
        wrapped = self._run_event(
            listener, event_name,
            *args, **kwargs
        )

        return self.loop.create_task(
            wrapped, name=f"discord.quart: {event_name}"
        )

    async def _prepare_me(self) -> UserClient:
        """ Gets the bot's user data, mostly used to validate token. """
        self._user_object = await self.state.me()
        _log.debug(f"/users/@me verified: {self.user} ({self.user.id})")

        return self.user

    async def _prepare_commands(self) -> None:
        """ Only used to sync commands on boot. """
        if self.sync:
            await self.sync_commands()

        else:
            data = await self.state.fetch_commands(
                guild_id=self.guild_id
            )
            self._update_ids(data)

    def get_shard_by_guild_id(
        self,
        guild_id: Snowflake | int
    ) -> int | None:
        """
        Returns the shard ID of the shard that the guild is in.

        Parameters
        ----------
        guild_id:
            The ID of the guild to get the shard ID of

        Returns
        -------
            The shard ID of the guild, or `None` if not found

        Raises
        ------
        `NotImplementedError`
            If the gateway is not available
        """
        if not self.gateway:
            raise NotImplementedError("gateway is not available")

        return self.gateway.shard_by_guild_id(
            int(guild_id)
        )

    async def query_members(
        self,
        guild_id: Snowflake | int,
        *,
        query: str | None = None,
        limit: int = 0,
        presences: bool = False,
        user_ids: list[Snowflake | int] | None = None,
        shard_id: int | None = None
    ) -> list[Member]:
        """
        Query members in a guild.

        Parameters
        ----------
        guild_id:
            The ID of the guild to query members in
        query:
            The query to search for
        limit:
            The maximum amount of members to return
        presences:
            Whether to include presences in the response
        user_ids:
            The user IDs to fetch members for
        shard_id:
            The shard ID to query the members from

        Returns
        -------
            The members that matched the query

        Raises
        ------
        `ValueError`
            - If `shard_id` is not provided
            - If `shard_id` is not valid
        """
        if not self.gateway:
            raise NotImplementedError("gateway is not available")

        if shard_id is None:
            shard_id = self.get_shard_by_guild_id(guild_id)
            if shard_id is None:  # Just double check
                raise ValueError("shard_id must be provided")

        shard = self.gateway.get_shard(shard_id)
        if not shard:
            raise ValueError("shard_id is not valid")

        return await shard.query_members(
            guild_id=guild_id,
            query=query,
            limit=limit,
            presences=presences,
            user_ids=user_ids
        )

    async def sync_commands(self) -> None:
        """ Make the bot fetch all current commands, to then sync them all to Discord API. """
        data = await self.state.update_commands(
            data=[
                v.to_dict()
                for v in self.commands.values()
                if not v.guild_ids and
                v.parent is None
            ],
            guild_id=self.guild_id
        )

        guild_ids = []
        for cmd in self.commands.values():
            if cmd.guild_ids:
                guild_ids.extend([
                    int(gid) for gid in cmd.guild_ids
                ])

        guild_ids: list[int] = list(set(guild_ids))

        for g in guild_ids:
            await self.state.update_commands(
                data=[
                    v.to_dict()
                    for v in self.commands.values()
                    if g in v.guild_ids and
                    v.parent is None
                ],
                guild_id=g
            )

        self._update_ids(data)

    @property
    def user(self) -> UserClient:
        """
        Returns the bot's user object.

        Returns
        -------
            The bot's user object

        Raises
        ------
        `AttributeError`
            If used before the bot is ready
        """
        if not self._user_object:
            raise AttributeError(
                "User object is not available yet "
                "(bot is not ready)"
            )

        return self._user_object

    @property
    def guilds(self) -> list[Guild | PartialGuild]:
        """
        Returns a list of all the guilds the bot is in.

        Only useable if you are using gateway and caching
        """
        return self.cache.guilds

    def get_guild(self, guild_id: int) -> Guild | PartialGuild | None:
        """
        Get a guild object from the cache.

        Parameters
        ----------
        guild_id:
            The ID of the guild to get.

        Returns
        -------
            The guild object with the specified ID, or `None` if not found.
        """
        return self.cache.get_guild(guild_id)

    def is_ready(self) -> bool:
        """ Indicates if the client is ready. """
        return (
            self._ready is not None and
            self._ready.is_set()
        )

    def is_shards_ready(self) -> bool:
        """ Indicates if the client is shards ready. """
        return (
            self._shards_ready is not None and
            self._shards_ready.is_set()
        )

    def set_context(
        self,
        *,
        cls: Callable | None = None
    ) -> None:
        """
        Get the context for a command, while allowing custom context as well.

        Example of making one:

        .. code-block:: python

            from discord_http import Context

            class CustomContext(Context):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

            Client.set_context(cls=CustomContext)

        Parameters
        ----------
        cls:
            The context to use for commands.
            Leave empty to use the default context.
        """
        if cls is None:
            cls = Context

        self._context = cls

    def set_backend(
        self,
        *,
        cls: Callable | None = None
    ) -> None:
        """
        Set the backend to use for the bot.

        Example of making one:

        .. code-block:: python

            from discord_http import DiscordHTTP

            class CustomBackend(DiscordHTTP):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)

            Client.set_backend(cls=CustomBackend)

        Parameters
        ----------
        cls:
            The backend to use for everything.
            Leave empty to use the default backend.
        """
        if cls is None:
            cls = DiscordHTTP

        self.backend = cls(client=self)

    async def setup_hook(self) -> None:
        """
        Runs before the bot is ready, to get variables set up.

        You can overwrite this function to do your own setup

        Example:

        .. code-block:: python

            async def setup_hook(self) -> None:
                # Making database connection available through the bot
                self.pool = SQLite.Database()
        """

    def start(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8080
    ) -> None:
        """
        Boot up the bot and start the HTTP server.

        Parameters
        ----------
        host: Optional[:class:`str`]
            Host to use, if not provided, it will use `127.0.0.1`
        port: Optional[:class:`int`]
            Port to use, if not provided, it will use `8080`
        """
        if not self.application_id or not self.public_key:
            raise RuntimeError(
                "Application ID or/and Public Key is not provided, "
                "please provide them when initializing the client server."
            )

        self.backend.before_serving(self._prepare_bot)
        self.backend.after_serving(self.__cleanup)
        self.backend.start(host=host, port=port)

    async def wait_until_ready(self) -> None:
        """ Waits until the client is ready using `asyncio.Event.wait()`. """
        if self._ready is None:
            raise RuntimeError(
                "Client has not been initialized yet, "
                "please use Client.start() to initialize the client."
            )

        await self._ready.wait()

    async def wait_until_shards_ready(self) -> None:
        """ Waits until the client is ready using `asyncio.Event.wait()`. """
        if self._shards_ready is None:
            raise RuntimeError(
                "Client has not been initialized yet, "
                "please use Client.start() to initialize the client."
            )

        await self._shards_ready.wait()

    def dispatch(
        self,
        event_name: str,
        /,
        *args, **kwargs  # noqa: ANN002
    ) -> None:
        """
        Dispatches an event to all listeners of that event.

        Parameters
        ----------
        event_name:
            The name of the event to dispatch.
        *args:
            The arguments to pass to the event.
        **kwargs:
            The keyword arguments to pass to the event.
        """
        for listener in self.listeners:
            if listener.name != f"on_{event_name}":
                continue

            self._schedule_event(
                listener,
                event_name,
                *args, **kwargs
            )

    def has_any_dispatch(
        self,
        event_name: str
    ) -> bool:
        """
        Checks if the bot has any listeners for the event.

        Parameters
        ----------
        event_name:
            The name of the event to check for.

        Returns
        -------
            Whether the bot has any listeners for the event.
        """
        event = next((
            x for x in self.listeners
            if x.name == f"on_{event_name}"
        ), None)

        return event is not None

    async def load_extension(
        self,
        package: str
    ) -> None:
        """
        Loads an extension.

        Parameters
        ----------
        package:
            The package to load the extension from.
        """
        if package in self._cogs:
            raise RuntimeError(f"Cog {package} is already loaded")

        lib = importlib.import_module(package)
        setup = getattr(lib, "setup", None)

        if not setup:
            raise RuntimeError(f"Cog {package} does not have a setup function")

        await setup(self)

    async def unload_extension(
        self,
        package: str
    ) -> None:
        """
        Unloads an extension.

        Parameters
        ----------
        package:
            The package to unload the extension from.
        """
        if package not in self._cogs:
            raise RuntimeError(f"Cog {package} is not loaded")

        for cog in self._cogs[package]:
            await self.remove_cog(cog)

        del self._cogs[package]

    async def add_cog(self, cog: "Cog") -> None:
        """
        Adds a cog to the bot.

        Parameters
        ----------
        cog:
            The cog to add to the bot.
        """
        await cog._inject(self)

    async def remove_cog(self, cog: "Cog") -> None:
        """
        Removes a cog from the bot.

        Parameters
        ----------
        cog:
            The cog to remove from the bot.
        """
        await cog._eject(self)

    def command(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        guild_ids: list[Snowflake | int] | None = None,
        guild_install: bool = True,
        user_install: bool = False,
    ) -> Callable:
        """
        Used to register a command.

        Parameters
        ----------
        name:
            Name of the command, if not provided, it will use the function name
        description:
            Description of the command, if not provided, it will use the function docstring
        guild_ids:
            List of guild IDs to register the command in
        user_install:
            Whether the command can be installed by users or not
        guild_install:
            Whether the command can be installed by guilds or not
        """
        def decorator(func: Callable) -> Command:
            command = Command(
                func,
                name=name or func.__name__,
                description=description,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install
            )
            self.add_command(command)
            return command

        return decorator

    def user_command(
        self,
        name: str | None = None,
        *,
        guild_ids: list[Snowflake | int] | None = None,
        guild_install: bool = True,
        user_install: bool = False,
    ) -> Callable:
        """
        Used to register a user command.

        Example usage

        .. code-block:: python

            @user_command()
            async def content(ctx, user: Union[Member, User]):
                await ctx.send(f"Target: {user.name}")

        Parameters
        ----------
        name:
            Name of the command, if not provided, it will use the function name
        guild_ids:
            List of guild IDs to register the command in
        user_install:
            Whether the command can be installed by users or not
        guild_install:
            Whether the command can be installed by guilds or not
        """
        def decorator(func: Callable) -> Command:
            command = Command(
                func,
                name=name or func.__name__,
                type=ApplicationCommandType.user,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install
            )
            self.add_command(command)
            return command

        return decorator

    def message_command(
        self,
        name: str | None = None,
        *,
        guild_ids: list[Snowflake | int] | None = None,
        guild_install: bool = True,
        user_install: bool = False,
    ) -> Callable:
        """
        Used to register a message command.

        Example usage

        .. code-block:: python

            @message_command()
            async def content(ctx, msg: Message):
                await ctx.send(f"Content: {msg.content}")

        Parameters
        ----------
        name:
            Name of the command, if not provided, it will use the function name
        guild_ids:
            List of guild IDs to register the command in
        user_install:
            Whether the command can be installed by users or not
        guild_install:
            Whether the command can be installed by guilds or not
        """
        def decorator(func: Callable) -> Command:
            command = Command(
                func,
                name=name or func.__name__,
                type=ApplicationCommandType.message,
                guild_ids=guild_ids,
                guild_install=guild_install,
                user_install=user_install
            )
            self.add_command(command)
            return command

        return decorator

    def group(
        self,
        name: str | None = None,
        *,
        description: str | None = None
    ) -> Callable:
        """
        Used to register a sub-command group.

        Parameters
        ----------
        name:
            Name of the group, if not provided, it will use the function name
        description:
            Description of the group, if not provided, it will use the function docstring
        """
        def decorator(func: Callable) -> SubGroup:
            subgroup = SubGroup(
                name=name or func.__name__,
                description=description
            )
            self.add_command(subgroup)
            return subgroup

        return decorator

    def add_group(self, name: str) -> SubGroup:
        """
        Used to add a sub-command group.

        Parameters
        ----------
        name:
            Name of the group

        Returns
        -------
            The created group
        """
        subgroup = SubGroup(name=name)
        self.add_command(subgroup)
        return subgroup

    def interaction(
        self,
        custom_id: str,
        *,
        regex: bool = False
    ) -> Callable:
        """
        Used to register an interaction.

        This does support regex, so you can use `r"regex here"` as the custom_id

        Parameters
        ----------
        custom_id:
            Custom ID of the interaction
        regex:
            Whether the custom_id is a regex or not
        """
        def decorator(func: Callable) -> Interaction:
            return self.add_interaction(Interaction(
                func,
                custom_id=custom_id,
                regex=regex
            ))

        return decorator

    def listener(
        self,
        name: str | None = None
    ) -> Callable:
        """
        Used to register a listener.

        Parameters
        ----------
        name:
            Name of the listener, if not provided, it will use the function name

        Raises
        ------
        `TypeError`
            - If the listener name is not a string
            - If the listener is not a coroutine function
        """
        if not isinstance(name, str | type(None)):
            raise TypeError(f"Listener name must be a string, not {type(name)}")

        def decorator(func: Callable) -> None:
            actual = func
            if isinstance(actual, staticmethod):
                actual = actual.__func__
            if not inspect.iscoroutinefunction(actual):
                raise TypeError("Listeners has to be coroutine functions")
            self.add_listener(Listener(
                name=name or actual.__name__,
                coro=func
            ))

        return decorator

    def get_channel(
        self,
        channel_id: int | None
    ) -> BaseChannel | PartialChannel | None:
        """
        Get a channel object from the cache.

        Parameters
        ----------
        channel_id:
            The ID of the channel to get.

        Returns
        -------
            The channel object with the specified ID, or `None` if not found.
        """
        if channel_id is None:
            return None

        for guild in self.guilds:
            channel = guild.get_channel(channel_id)
            if channel:
                return channel

        return None

    def get_partial_channel(
        self,
        channel_id: int,
        *,
        guild_id: int | None = None
    ) -> PartialChannel:
        """
        Creates a partial channel object.

        Parameters
        ----------
        channel_id:
            Channel ID to create the partial channel object with.
        guild_id:
            Guild ID to create the partial channel object with.

        Returns
        -------
            The partial channel object.
        """
        return PartialChannel(
            state=self.state,
            id=channel_id,
            guild_id=guild_id
        )

    async def fetch_channel(
        self,
        channel_id: int,
        *,
        guild_id: int | None = None
    ) -> BaseChannel:
        """
        Fetches a channel object.

        Parameters
        ----------
        channel_id:
            Channel ID to fetch the channel object with.
        guild_id:
            Guild ID to fetch the channel object with.

        Returns
        -------
            The channel object.
        """
        c = self.get_partial_channel(channel_id, guild_id=guild_id)
        return await c.fetch()

    def get_partial_automod_rule(
        self,
        rule_id: int,
        guild_id: int
    ) -> PartialAutoModRule:
        """
        Creates a partial automod object.

        Parameters
        ----------
        rule_id:
            The ID of the automod rule
        guild_id:
            The Guild ID where it comes from

        Returns
        -------
            The partial automod object
        """
        return PartialAutoModRule(
            state=self.state,
            id=rule_id,
            guild_id=guild_id
        )

    async def fetch_automod_rule(
        self,
        rule_id: int,
        guild_id: int
    ) -> AutoModRule:
        """
        Fetches a automod object.

        Parameters
        ----------
        rule_id:
            The ID of the automod rule
        guild_id:
            The Guild ID where it comes from

        Returns
        -------
            The automod object
        """
        automod = self.get_partial_automod_rule(
            rule_id=rule_id,
            guild_id=guild_id
        )

        return await automod.fetch()

    def get_partial_invite(
        self,
        invite_code: str,
        *,
        channel_id: int | None = None,
        guild_id: int | None = None
    ) -> PartialInvite:
        """
        Creates a partial invite object.

        Parameters
        ----------
        invite_code:
            Invite code to create the partial invite object with.
        channel_id:
            Channel ID to create the partial invite object with.
        guild_id:
            Guild ID to create the partial invite object with.

        Returns
        -------
            The partial invite object.
        """
        return PartialInvite(
            state=self.state,
            code=invite_code,
            channel_id=channel_id,
            guild_id=guild_id
        )

    def get_partial_voice_state(
        self,
        member_id: int,
        *,
        guild_id: int | None = None,
        channel_id: int | None = None
    ) -> PartialVoiceState:
        """
        Creates a partial voice state object.

        Parameters
        ----------
        member_id:
            The ID of the member to create the partial voice state from
        guild_id:
            Guild ID to create the partial voice state from
        channel_id:
            Channel ID to create the partial voice state from

        Returns
        -------
            The partial voice state object.
        """
        return PartialVoiceState(
            state=self.state,
            id=member_id,
            guild_id=guild_id,
            channel_id=channel_id
        )

    async def fetch_voice_state(
        self,
        member_id: int,
        guild_id: int | None = None
    ) -> VoiceState:
        """
        Fetches a voice state object.

        Parameters
        ----------
        member_id:
            The ID of the member to fetch the voice state from
        guild_id:
            Guild ID to fetch the voice state from

        Returns
        -------
            The voice state object.
        """
        vs = self.get_partial_voice_state(
            member_id,
            guild_id=guild_id
        )

        return await vs.fetch()

    def get_partial_emoji(
        self,
        emoji_id: int,
        *,
        guild_id: int | None = None
    ) -> PartialEmoji:
        """
        Creates a partial emoji object.

        Parameters
        ----------
        emoji_id:
            Emoji ID to create the partial emoji object with.
        guild_id:
            Guild ID of where the emoji comes from.
            If None, it will get the emoji from the application.

        Returns
        -------
            The partial emoji object.
        """
        return PartialEmoji(
            state=self.state,
            id=emoji_id,
            guild_id=guild_id
        )

    async def fetch_emoji(
        self,
        emoji_id: int,
        *,
        guild_id: int | None = None
    ) -> Emoji:
        """
        Fetches an emoji object.

        Parameters
        ----------
        emoji_id:
            The ID of the emoji in question
        guild_id:
            Guild ID of the emoji.
            If None, it will fetch the emoji from the application

        Returns
        -------
            The emoji object
        """
        e = self.get_partial_emoji(
            emoji_id,
            guild_id=guild_id
        )

        return await e.fetch()

    def get_partial_sticker(
        self,
        sticker_id: int,
        *,
        guild_id: int | None = None
    ) -> PartialSticker:
        """
        Creates a partial sticker object.

        Parameters
        ----------
        sticker_id:
            Sticker ID to create the partial sticker object with.
        guild_id:
            Guild ID to create the partial sticker object with.

        Returns
        -------
            The partial sticker object.
        """
        return PartialSticker(
            state=self.state,
            id=sticker_id,
            guild_id=guild_id
        )

    async def fetch_sticker(
        self,
        sticker_id: int,
        *,
        guild_id: int | None = None
    ) -> Sticker:
        """
        Fetches a sticker object.

        Parameters
        ----------
        sticker_id:
            Sticker ID to fetch the sticker object with.
        guild_id:
            Guild ID to fetch the sticker object from.

        Returns
        -------
            The sticker object.
        """
        sticker = self.get_partial_sticker(
            sticker_id,
            guild_id=guild_id
        )

        return await sticker.fetch()

    def get_partial_soundboard_sound(
        self,
        sound_id: int,
        *,
        guild_id: int | None = None
    ) -> PartialSoundboardSound:
        """
        Creates a partial sticker object.

        Parameters
        ----------
        sound_id:
            Sound ID to create the partial soundboard sound object with.
        guild_id:
            Guild ID to create the partial soundboard sound object with.

        Returns
        -------
            The partial soundboard sound object.
        """
        return PartialSoundboardSound(
            state=self.state,
            id=sound_id,
            guild_id=guild_id
        )

    async def fetch_soundboard_sound(
        self,
        sound_id: int,
        guild_id: int
    ) -> SoundboardSound:
        """
        Fetches a soundboard sound object.

        Parameters
        ----------
        sound_id:
            Sound ID to fetch the soundboard sound object with.
        guild_id:
            Guild ID to fetch the soundboard sound object from.

        Returns
        -------
            The soundboard sound object.
        """
        sound = self.get_partial_soundboard_sound(
            sound_id,
            guild_id=guild_id
        )

        return await sound.fetch()

    async def fetch_invite(
        self,
        invite_code: str
    ) -> Invite:
        """
        Fetches an invite object.

        Parameters
        ----------
        invite_code:
            Invite code to fetch the invite object with.

        Returns
        -------
            The invite object.
        """
        invite = self.get_partial_invite(invite_code)
        return await invite.fetch()

    def get_partial_message(
        self,
        message_id: int,
        channel_id: int,
        guild_id: int | None = None
    ) -> PartialMessage:
        """
        Creates a partial message object.

        Parameters
        ----------
        message_id:
            Message ID to create the partial message object with.
        channel_id:
            Channel ID to create the partial message object with.
        guild_id:
            Guild ID to create the partial message object with.

        Returns
        -------
            The partial message object.
        """
        return PartialMessage(
            state=self.state,
            id=message_id,
            channel_id=channel_id,
            guild_id=guild_id
        )

    async def fetch_message(
        self,
        message_id: int,
        channel_id: int,
        guild_id: int | None = None
    ) -> Message:
        """
        Fetches a message object.

        Parameters
        ----------
        message_id:
            Message ID to fetch the message object with.
        channel_id:
            Channel ID to fetch the message object with.
        guild_id:
            Guild ID to fetch the message object from.

        Returns
        -------
            The message object
        """
        msg = self.get_partial_message(message_id, channel_id, guild_id)
        return await msg.fetch()

    def get_partial_webhook(
        self,
        webhook_id: int,
        *,
        webhook_token: str | None = None
    ) -> PartialWebhook:
        """
        Creates a partial webhook object.

        Parameters
        ----------
        webhook_id:
            Webhook ID to create the partial webhook object with.
        webhook_token:
            Webhook token to create the partial webhook object with.

        Returns
        -------
            The partial webhook object.
        """
        return PartialWebhook(
            state=self.state,
            id=webhook_id,
            token=webhook_token
        )

    async def fetch_webhook(
        self,
        webhook_id: int,
        *,
        webhook_token: str | None = None
    ) -> Webhook:
        """
        Fetches a webhook object.

        Parameters
        ----------
        webhook_id:
            Webhook ID to fetch the webhook object with.
        webhook_token:
            Webhook token to fetch the webhook object with.

        Returns
        -------
            The webhook object.
        """
        webhook = self.get_partial_webhook(
            webhook_id,
            webhook_token=webhook_token
        )

        return await webhook.fetch()

    def get_partial_user(
        self,
        user_id: int
    ) -> PartialUser:
        """
        Creates a partial user object.

        Parameters
        ----------
        user_id:
            User ID to create the partial user object with.

        Returns
        -------
            The partial user object.
        """
        return PartialUser(
            state=self.state,
            id=user_id
        )

    async def fetch_user(
        self,
        user_id: int
    ) -> User:
        """
        Fetches a user object.

        Parameters
        ----------
        user_id:
            User ID to fetch the user object with.

        Returns
        -------
            The user object.
        """
        user = self.get_partial_user(user_id)
        return await user.fetch()

    def get_partial_member(
        self,
        user_id: int,
        guild_id: int
    ) -> PartialMember:
        """
        Creates a partial member object.

        Parameters
        ----------
        user_id:
            User ID to create the partial member object with.
        guild_id:
            Guild ID that the member is in.

        Returns
        -------
            The partial member object.
        """
        return PartialMember(
            state=self.state,
            id=user_id,
            guild_id=guild_id,
        )

    async def fetch_member(
        self,
        user_id: int,
        guild_id: int
    ) -> Member:
        """
        Fetches a member object.

        Parameters
        ----------
        guild_id:
            Guild ID that the member is in.
        user_id:
            User ID to fetch the member object with.

        Returns
        -------
            The member object.
        """
        member = self.get_partial_member(user_id, guild_id)
        return await member.fetch()

    async def fetch_application_emojis(self) -> list[Emoji]:
        """ Fetches all emojis available to the application. """
        r = await self.state.query(
            "GET",
            f"/applications/{self.application_id}/emojis"
        )

        return [
            Emoji(state=self.state, data=g)
            for g in r.response.get("items", [])
        ]

    async def create_application_emoji(
        self,
        name: str,
        *,
        image: File | bytes
    ) -> Emoji:
        """
        Creates an emoji for the application.

        Parameters
        ----------
        name:
            Name of emoji
        image:
            The image data to use for the emoji.

        Returns
        -------
            The created emoji object.
        """
        r = await self.state.query(
            "POST",
            f"/applications/{self.application_id}/emojis",
            json={
                "name": name,
                "image": utils.bytes_to_base64(image)
            }
        )

        return Emoji(
            state=self.state,
            data=r.response
        )

    def get_partial_sku(
        self,
        sku_id: int
    ) -> PartialSKU:
        """
        Creates a partial SKU object.

        Returns
        -------
            The partial SKU object.
        """
        return PartialSKU(
            state=self.state,
            id=sku_id
        )

    async def fetch_skus(self) -> list[SKU]:
        """ Fetches all SKUs available to the bot. """
        r = await self.state.query(
            "GET",
            f"/applications/{self.application_id}/skus"
        )

        return [
            SKU(state=self.state, data=g)
            for g in r.response
        ]

    def get_partial_entitlement(
        self,
        entitlement_id: int
    ) -> PartialEntitlements:
        """
        Creates a partial entitlement object.

        Parameters
        ----------
        entitlement_id:
            Entitlement ID to create the partial entitlement object with.

        Returns
        -------
            The partial entitlement object.
        """
        return PartialEntitlements(
            state=self.state,
            id=entitlement_id
        )

    async def fetch_entitlement(
        self,
        entitlement_id: int
    ) -> Entitlements:
        """
        Fetches an entitlement object.

        Parameters
        ----------
        entitlement_id:
            Entitlement ID to fetch the entitlement object with.

        Returns
        -------
            The entitlement object.
        """
        ent = self.get_partial_entitlement(entitlement_id)
        return await ent.fetch()

    async def fetch_entitlement_list(
        self,
        *,
        user_id: int | None = None,
        sku_ids: list[int] | None = None,
        before: int | None = None,
        after: int | None = None,
        limit: int | None = 100,
        guild_id: int | None = None,
        exclude_ended: bool = False
    ) -> AsyncIterator[Entitlements]:
        """
        Fetches a list of entitlement objects with optional filters.

        Parameters
        ----------
        user_id:
            Show entitlements for a specific user ID.
        sku_ids:
            Show entitlements for a specific SKU ID.
        before:
            Only show entitlements before this entitlement ID.
        after:
            Only show entitlements after this entitlement ID.
        limit:
            Limit the amount of entitlements to fetch.
            Use `None` to fetch all entitlements.
        guild_id:
            Show entitlements for a specific guild ID.
        exclude_ended:
            Whether to exclude ended entitlements or not.

        Returns
        -------
            The entitlement objects.
        """
        params: dict[str, Any] = {
            "exclude_ended": "true" if exclude_ended else "false"
        }

        if user_id is not None:
            params["user_id"] = int(user_id)
        if sku_ids is not None:
            params["sku_ids"] = ",".join([str(int(g)) for g in sku_ids])
        if guild_id is not None:
            params["guild_id"] = int(guild_id)

        def _resolve_id(entry: str | int | Snowflake) -> int:
            match entry:
                case x if isinstance(x, Snowflake):
                    return int(x)

                case x if isinstance(x, int):
                    return x

                case x if isinstance(x, str):
                    if not x.isdigit():
                        raise TypeError("Got a string that was not a Snowflake ID for before/after")
                    return int(x)

                case x if isinstance(x, datetime):
                    return utils.time_snowflake(x)

                case _:
                    raise TypeError("Got an unknown type for before/after")

        async def _get_history(limit: int, **kwargs) -> HTTPResponse[dict]:
            params["limit"] = min(limit, 100)
            for key, value in kwargs.items():
                if value is None:
                    continue
                params[key] = _resolve_id(value)

            return await self.state.query(
                "GET",
                f"/applications/{self.application_id}/entitlements",
                params=params
            )

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

        if after:
            strategy, state = _after_http, _resolve_id(after)
        elif before:
            strategy, state = _before_http, _resolve_id(before)
        else:
            strategy, state = _before_http, None

        while True:
            http_limit: int = 100 if limit is None else min(limit, 100)
            if http_limit <= 0:
                break

            strategy: Callable
            messages, state, limit = await strategy(http_limit, state, limit)

            i = 0
            for ent in messages:
                yield Entitlements(state=self.state, data=ent)
                i += 1

            if i < 100:
                break

    def get_partial_scheduled_event(
        self,
        event_id: int,
        guild_id: int
    ) -> PartialScheduledEvent:
        """
        Creates a partial scheduled event object.

        Parameters
        ----------
        event_id:
            The ID of the scheduled event.
        guild_id:
            The guild ID of the scheduled event.

        Returns
        -------
            The partial scheduled event object.
        """
        return PartialScheduledEvent(
            state=self.state,
            id=event_id,
            guild_id=guild_id
        )

    async def fetch_scheduled_event(
        self,
        event_id: int,
        guild_id: int
    ) -> ScheduledEvent:
        """
        Fetches a scheduled event object.

        Parameters
        ----------
        event_id:
            The ID of the scheduled event.
        guild_id:
            The guild ID of the scheduled event.

        Returns
        -------
            The scheduled event object.
        """
        event = self.get_partial_scheduled_event(
            event_id, guild_id
        )
        return await event.fetch()

    def get_partial_guild(
        self,
        guild_id: int
    ) -> PartialGuild:
        """
        Creates a partial guild object.

        Parameters
        ----------
        guild_id:
            Guild ID to create the partial guild object with.

        Returns
        -------
            The partial guild object.
        """
        return PartialGuild(
            state=self.state,
            id=guild_id
        )

    async def fetch_guild(
        self,
        guild_id: int
    ) -> Guild:
        """
        Fetches a guild object.

        Parameters
        ----------
        guild_id:
            Guild ID to fetch the guild object with.

        Returns
        -------
            The guild object.
        """
        guild = self.get_partial_guild(guild_id)
        return await guild.fetch()

    async def create_guild(
        self,
        name: str,
        *,
        icon: File | bytes | None = None,
        reason: str | None = None
    ) -> "Guild":
        """
        Create a guild.

        Note that the bot must be in less than 10 guilds to use this endpoint

        Parameters
        ----------
        name:
            The name of the guild
        icon:
            The icon of the guild
        reason:
            The reason for creating the guild

        Returns
        -------
            The created guild
        """
        payload = {"name": name}

        if icon is not None:
            payload["icon"] = utils.bytes_to_base64(icon)

        r = await self.state.query(
            "POST",
            "/guilds",
            json=payload,
            reason=reason
        )

        return Guild(
            state=self.state,
            data=r.response
        )

    def get_partial_role(
        self,
        role_id: int,
        guild_id: int
    ) -> PartialRole:
        """
        Creates a partial role object.

        Parameters
        ----------
        role_id:
            Role ID to create the partial role object with.
        guild_id:
            Guild ID that the role is in.

        Returns
        -------
            The partial role object.
        """
        return PartialRole(
            state=self.state,
            id=role_id,
            guild_id=guild_id
        )

    def find_interaction(
        self,
        custom_id: str
    ) -> Optional["Interaction"]:
        """
        Finds an interaction by its Custom ID.

        Parameters
        ----------
        custom_id:
            The Custom ID to find the interaction with.
            Will automatically convert to regex matching
            if some interaction Custom IDs are regex.

        Returns
        -------
            The interaction that was found if any.
        """
        inter = self.interactions.get(custom_id, None)
        if inter:
            return inter

        for _, inter in self.interactions_regex.items():
            if inter.match(custom_id):
                return inter

        return None

    def add_listener(
        self,
        func: "Listener"
    ) -> "Listener":
        """
        Adds a listener to the bot.

        Parameters
        ----------
        func:
            The listener to add to the bot.
        """
        self.listeners.append(func)
        return func

    def remove_listener(
        self,
        func: "Listener"
    ) -> None:
        """
        Removes a listener from the bot.

        Parameters
        ----------
        func:
            The listener to remove from the bot.
        """
        self.listeners.remove(func)

    def add_command(
        self,
        func: "Command"
    ) -> "Command":
        """
        Adds a command to the bot.

        Parameters
        ----------
        func:
            The command to add to the bot.
        """
        self.commands[func.name] = func
        return func

    def remove_command(
        self,
        func: "Command"
    ) -> None:
        """
        Removes a command from the bot.

        Parameters
        ----------
        func:
            The command to remove from the bot.
        """
        self.commands.pop(func.name, None)

    def add_global_cmd_check(
        self,
        func: Callable
    ) -> Callable:
        """
        Add a check that will be run before every command.

        Parameters
        ----------
        func:
            The function to add
        """
        self._global_cmd_checks.append(func)

        return func

    def add_interaction(
        self,
        func: "Interaction"
    ) -> "Interaction":
        """
        Adds an interaction to the bot.

        Parameters
        ----------
        func:
            The interaction to add to the bot.
        """
        if func.regex:
            self.interactions_regex[func.custom_id] = func
        else:
            self.interactions[func.custom_id] = func

        return func

    def remove_interaction(
        self,
        func: "Interaction"
    ) -> None:
        """
        Removes an interaction from the bot.

        Parameters
        ----------
        func:
            The interaction to remove from the bot.
        """
        if func.regex:
            self.interactions_regex.pop(func.custom_id, None)
        else:
            self.interactions.pop(func.custom_id, None)
