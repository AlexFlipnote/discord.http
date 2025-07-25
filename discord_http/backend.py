import asyncio
import copy
import inspect
import logging
import orjson
import signal

from datetime import datetime
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from quart import Quart, request, abort
from quart import Response as QuartResponse
from quart.logging import default_handler
from quart.utils import MustReloadError, restart
from typing import Any, TYPE_CHECKING
from collections.abc import Coroutine

from . import utils
from .commands import Command, SubGroup
from .enums import InteractionType
from .errors import CheckFailed
from .response import BaseResponse, Ping, MessageResponse, EmptyResponse

if TYPE_CHECKING:
    from .client import Client
    from .context import Context

_log = logging.getLogger(__name__)

__all__ = (
    "DiscordHTTP",
)


def _cancel_all_tasks(loop: asyncio.AbstractEventLoop) -> None:
    """ Used by Quart to cancel all tasks on shutdown. """
    tasks = [
        task for task in asyncio.all_tasks(loop)
        if not task.done()
    ]

    if not tasks:
        return

    for task in list(tasks):
        task.cancel()

        if task.get_coro().__name__ == "_windows_signal_support":  # type: ignore
            tasks.remove(task)

    loop.run_until_complete(
        asyncio.gather(*tasks, return_exceptions=True)
    )

    for task in tasks:
        if not task.cancelled() and task.exception() is not None:
            loop.call_exception_handler({
                "message": "unhandled exception during shutdown",
                "exception": task.exception(),
                "task": task
            })


class DiscordHTTP(Quart):
    def __init__(self, *, client: "Client"):
        """
        Serves as the fundemental HTTP server for Discord Interactions.

        We recommend to not touch this class, unless you know what you're doing
        """
        self.uptime: datetime = utils.utcnow()

        self.bot: "Client" = client

        # Aliases
        self.loop = self.bot.loop
        self.debug_events = self.bot.debug_events

        super().__init__(__name__)

        # Change some of the default settings
        self.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
        self.config["JSON_SORT_KEYS"] = False

        # Remove Quart's default logging handler
        quart_log = logging.getLogger("quart.app")
        quart_log.removeHandler(default_handler)
        quart_log.setLevel(logging.CRITICAL)

    async def _validate_request(self) -> None:
        """
        Used to validate requests sent by Discord Webhooks.

        This should NOT be modified, unless you know what you're doing
        """
        if not self.bot.public_key:
            return abort(401, "invalid public key")

        verify_key = VerifyKey(bytes.fromhex(self.bot.public_key))
        signature: str = request.headers.get("X-Signature-Ed25519", "")
        timestamp: str = request.headers.get("X-Signature-Timestamp", "")

        try:
            data = await request.data
            body = data.decode("utf-8")
            verify_key.verify(
                f"{timestamp}{body}".encode(),
                bytes.fromhex(signature)
            )
        except BadSignatureError:
            abort(401, "invalid request signature")
        except Exception:
            abort(400, "invalid request body")

    def _dig_subcommand(
        self,
        cmd: Command | SubGroup,
        data: dict
    ) -> tuple[Command | None, list[dict]]:
        """ Used to dig through subcommands to execute correct command/autocomplete. """
        data_options: list[dict] = data["data"].get("options", [])

        while isinstance(cmd, SubGroup):
            find_next_step = next((
                g for g in data_options
                if g.get("name", None) and not g.get("value", None)
            ), None)

            if not find_next_step:
                return abort(400, "invalid command")

            cmd = cmd.subcommands.get(find_next_step["name"], None)  # type: ignore

            if not cmd:
                _log.warning(
                    f"Unhandled subcommand: {find_next_step['name']} "
                    "(not found in local command list)"
                )
                return abort(404, "command not found")

            data_options = find_next_step.get("options", [])

        return cmd, data_options

    def _handle_ack_ping(
        self,
        ctx: "Context",
        data: dict
    ) -> dict:
        """ Used to handle ACK ping. """
        ping = Ping(state=self.bot.state, data=data)

        if self.bot.has_any_dispatch("ping"):
            self.bot.dispatch("ping", ping)

        _log.debug(f"Discord Interactions ACK recieved ({ping.id})")

        return ctx.response.pong()

    async def _run_before_invoke(self, ctx: "Context") -> bool:
        if self.bot._before_invoke is None:
            return True

        if inspect.iscoroutinefunction(self.bot._before_invoke):
            result = await self.bot._before_invoke(ctx)
        else:
            result = self.bot._before_invoke(ctx)

        if result is not True:
            raise CheckFailed("Global before invoke failed.")

        return True

    async def _run_after_invoke(self, ctx: "Context") -> None:
        if self.bot._after_invoke is None:
            return

        async def _run_background() -> None:
            if inspect.iscoroutinefunction(self.bot._after_invoke):
                await self.bot._after_invoke(ctx)
            else:
                self.bot._after_invoke(ctx)  # type: ignore

        self.bot.loop.create_task(
            _run_background()
        )

    async def _handle_application_command(
        self,
        ctx: "Context",
        data: dict
    ) -> QuartResponse | dict:
        """ Used to handle application commands. """
        await self._run_before_invoke(ctx)

        _log.debug("Received slash command, processing...")

        command_name = data["data"]["name"]
        cmd = self.bot.commands.get(command_name, None)

        if not cmd:
            _log.warning(
                f"Unhandeled command: {command_name} "
                "(not found in local command list)"
            )
            return QuartResponse(
                "command not found",
                status=404
            )

        cmd, _ = self._dig_subcommand(cmd, data)

        # Now that the command is found, let context know about it
        ctx.command = cmd

        try:
            # But first, check global checks
            await self.bot._run_global_checks(ctx)

            # Now run the command itself
            payload = await cmd._make_context_and_run(
                context=ctx
            )

            await self._run_after_invoke(ctx)

            if isinstance(payload, EmptyResponse):
                return QuartResponse("", status=202)

            return QuartResponse(
                payload.to_multipart(),
                content_type=payload.content_type
            )

        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", ctx, e)
            else:
                _log.error(
                    f"Error while running command {cmd.name}",
                    exc_info=e
                )

            send_error = self.error_messages(ctx, e)
            if send_error and isinstance(send_error, BaseResponse):
                return send_error.to_dict()

            return abort(500)

    async def _handle_interaction(
        self,
        ctx: "Context",
        data: dict
    ) -> QuartResponse | dict:
        """ Used to handle interactions. """
        await self._run_before_invoke(ctx)

        _log.debug("Received interaction, processing...")
        custom_id = data["data"]["custom_id"]

        try:
            local_view = None

            if (
                local_view is None and
                ctx.custom_id
            ):
                local_view = self.bot._view_storage.get(
                    ctx.custom_id, None
                )

            if (
                local_view is None and
                ctx.message
            ):
                local_view = self.bot._view_storage.get(
                    ctx.message.id, None
                )

                if not local_view and ctx.message.interaction:
                    local_view = self.bot._view_storage.get(
                        ctx.message.interaction.id, None
                    )

            if local_view:
                payload = await local_view.callback(ctx)
                return QuartResponse(
                    payload.to_multipart(),
                    content_type=payload.content_type
                )

            intreact = self.bot.find_interaction(custom_id)
            if not intreact:
                _log.debug(
                    "Unhandled interaction recieved "
                    f"(custom_id: {custom_id})"
                )
                return QuartResponse(
                    "interaction not found",
                    status=404
                )

            payload = await intreact.run(ctx)

            await self._run_after_invoke(ctx)

            return QuartResponse(
                payload.to_multipart(),
                content_type=payload.content_type
            )

        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", ctx, e)
            else:
                _log.error(
                    f"Error while running interaction {custom_id}",
                    exc_info=e
                )

            return abort(500)

    async def _handle_autocomplete(
        self,
        ctx: "Context",
        data: dict
    ) -> QuartResponse | dict:
        """ Used to handle autocomplete interactions. """
        _log.debug("Received autocomplete interaction, processing...")

        command_name = data.get("data", {}).get("name", None)
        cmd = self.bot.commands.get(command_name)

        try:
            if not cmd:
                _log.warning(f"Unhandled autocomplete recieved (name: {command_name})")
                return QuartResponse(
                    "command not found",
                    status=404
                )

            cmd, data_options = self._dig_subcommand(cmd, data)

            find_focused = next((
                x for x in data_options
                if x.get("focused", False)
            ), None)

            if not find_focused:
                _log.warning(
                    "Failed to find focused option in autocomplete "
                    f"(cmd name: {command_name})"
                )
                return QuartResponse(
                    "focused option not found",
                    status=400
                )

            return await cmd.run_autocomplete(
                ctx, find_focused["name"], find_focused["value"]
            )
        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", ctx, e)
            else:
                _log.error(
                    f"Error while running autocomplete {cmd.name}",
                    exc_info=e
                )
            return abort(500)

    async def _index_interactions_endpoint(
        self
    ) -> QuartResponse | dict:
        """
        The main function to handle all HTTP requests sent by Discord.

        Please do not touch this function, unless you know what you're doing
        """
        await self._validate_request()
        data = await request.json

        if self.debug_events:
            self.bot.dispatch(
                "raw_interaction",
                copy.deepcopy(data)
            )

        context = self.bot._context(self.bot, data)
        data_type = data.get("type", -1)

        match data_type:
            case InteractionType.ping:
                return self._handle_ack_ping(context, data)

            case InteractionType.application_command:
                return await self._handle_application_command(
                    context, data
                )

            case x if x in (
                InteractionType.message_component,
                InteractionType.modal_submit
            ):
                return await self._handle_interaction(
                    context, data
                )

            case InteractionType.application_command_autocomplete:
                return await self._handle_autocomplete(
                    context, data
                )

            case _:  # Unknown
                _log.debug(f"Unhandled interaction recieved (type: {data_type})")
                return abort(400, "invalid request body")

    def error_messages(
        self,
        ctx: "Context",
        e: Exception
    ) -> MessageResponse | None:
        """
        Used to return error messages to Discord.

        By default, it will only cover CheckFailed errors.
        You can overwrite this function to return your own error messages.

        Parameters
        ----------
        ctx: `Context`
            The context of the command
        e: `Exception`
            The exception that was raised

        Returns
        -------
            The message response provided by the library error handler
        """
        if isinstance(e, CheckFailed):
            return ctx.response.send_message(
                content=str(e),
                ephemeral=True
            )

        return None

    async def index_ping(self) -> tuple[dict, int] | dict:
        """
        Used to ping the interaction url, to check if it's working.

        You can overwrite this function to return your own data as well.
        Remember that it must return `dict`
        """
        if not self.bot.is_ready():
            return {"error": "bot is not ready yet"}, 503

        return {
            "@me": {
                "id": self.bot.user.id,
                "username": self.bot.user.name,
                "discriminator": self.bot.user.discriminator,
                "created_at": str(self.bot.user.created_at.isoformat()),
            },
            "last_reboot": {
                "datetime": str(self.uptime.astimezone().isoformat()),
                "timedelta": str(utils.utcnow() - self.uptime),
                "unix": int(self.uptime.timestamp()),
            }
        }

    def jsonify(
        self,
        data: dict,
        *,
        status: int = 200
    ) -> QuartResponse:
        """
        Force Quart to respond with JSON the way you like it.

        Parameters
        ----------
        data: `dict`
            The data to respond with
        status: `int`
            The status code to respond with

        Returns
        -------
            The response object
        """
        return QuartResponse(
            orjson.dumps(data),
            headers={"Content-Type": "application/json"},
            status=status,
        )

    def start(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8080
    ) -> None:
        """
        Start the HTTP server.

        Parameters
        ----------
        host:
            The IP address to bind to, by default 127.0.0.1
        port:
            The port to bind to, by default 8080
        """
        int_path = str(self.bot.interaction_path)
        if not int_path.startswith("/"):
            _log.warning(
                "Interaction path should start with a slash ( / ), "
                f'adding it automatically for you, your path is now "/{int_path}"'
            )
            int_path = f"/{int_path}"

        if not self.bot.disable_default_get_path:
            self.add_url_rule(
                int_path,
                "ping",
                self.index_ping,
                methods=["GET"]
            )

        self.add_url_rule(
            int_path,
            "index",
            self._index_interactions_endpoint,
            methods=["POST"]
        )

        try:
            _log.info(f"Serving on http://{host}:{port}")
            self.run(host=host, port=port, loop=self.loop)
        except KeyboardInterrupt:
            pass  # Just don't bother showing errors...

    def run(
        self,
        host: str,
        port: int,
        loop: asyncio.AbstractEventLoop
    ) -> None:
        """ ## Do NOT use this function, use `start` instead. """
        loop.set_debug(False)
        shutdown_event = asyncio.Event()

        def _signal_handler(*_: Any) -> None:  # noqa: ANN401
            shutdown_event.set()

        for signal_name in {"SIGINT", "SIGTERM", "SIGBREAK"}:
            if hasattr(signal, signal_name):
                try:
                    loop.add_signal_handler(
                        getattr(signal, signal_name),
                        _signal_handler
                    )
                except NotImplementedError:
                    # Add signal handler may not be implemented on Windows
                    signal.signal(
                        getattr(signal, signal_name),
                        _signal_handler
                    )

        server_name = self.config.get("SERVER_NAME")
        sn_host = None
        sn_port = None
        if server_name is not None:
            sn_host, _, sn_port = server_name.partition(":")

        if host is None:
            host = sn_host or "127.0.0.1"

        if port is None:
            port = int(sn_port or "8080")

        task = self.run_task(
            host=host,
            port=port,
            shutdown_trigger=shutdown_event.wait,
        )

        tasks = [loop.create_task(task)]
        reload_ = False

        try:
            loop.run_until_complete(asyncio.gather(*tasks))
        except MustReloadError:
            reload_ = True
        except KeyboardInterrupt:
            pass
        finally:
            try:
                _cancel_all_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()

        if reload_:
            restart()

    def run_task(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        shutdown_trigger: Any = None  # noqa: ANN401
    ) -> Coroutine[None, None, None]:
        """ ## Do NOT use this function, use `start` instead. """
        config = HyperConfig()
        config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s"
        config.accesslog = None
        config.bind = [f"{host}:{port}"]
        config.ca_certs = None
        config.certfile = None
        config.debug = False
        config.errorlog = None
        config.keyfile = None

        return serve(
            self,
            config,
            shutdown_trigger=shutdown_trigger
        )
