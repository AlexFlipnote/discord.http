import copy
import inspect
import logging
import orjson

from datetime import datetime
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPUnauthorized, HTTPBadRequest,
    HTTPInternalServerError
)

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


class DiscordHTTP(web.Application):
    """
    Serves as the fundemental HTTP server for Discord Interactions.

    We recommend to not touch this class, unless you know what you're doing
    """
    def __init__(self, *, client: "Client"):
        self.uptime: datetime = utils.utcnow()
        self.bot: "Client" = client
        self.debug_events = self.bot.debug_events

        super().__init__(client_max_size=10 * 1024 * 1024)

        # Silence aiohttp access logs
        logging.getLogger("aiohttp.server").setLevel(logging.ERROR)
        logging.getLogger("aiohttp.access").setLevel(logging.ERROR)

    async def _validate_request(self, request: web.Request) -> None:
        """
        Used to validate requests sent by Discord Webhooks.

        This should NOT be modified, unless you know what you're doing
        """
        if not self.bot.public_key:
            raise HTTPUnauthorized(text="invalid public key")

        verify_key = VerifyKey(bytes.fromhex(self.bot.public_key))
        signature: str = request.headers.get("X-Signature-Ed25519", "")
        timestamp: str = request.headers.get("X-Signature-Timestamp", "")

        try:
            data = await request.read()
            body = data.decode("utf-8")
            verify_key.verify(
                f"{timestamp}{body}".encode(),
                bytes.fromhex(signature)
            )
        except BadSignatureError:
            raise HTTPUnauthorized(text="invalid request signature")
        except Exception:
            raise HTTPBadRequest(text="invalid request body")

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
                raise HTTPBadRequest(text="invalid command")

            cmd = cmd.subcommands.get(find_next_step["name"], None)  # type: ignore

            if not cmd:
                _log.warning(
                    f"Unhandled subcommand: {find_next_step['name']} "
                    "(not found in local command list)"
                )
                return self.jsonify({"error": "command not found"}, status=404)

            data_options = find_next_step.get("options", [])

        return cmd, data_options

    def _handle_ack_ping(
        self,
        ctx: "Context",
        data: dict
    ) -> web.Response:
        """ Used to handle ACK ping. """
        ping = Ping(state=self.bot.state, data=data)

        if self.bot.has_any_dispatch("ping"):
            self.bot.dispatch("ping", ping)

        _log.debug(f"Discord Interactions ACK received ({ping.id})")
        return self.jsonify(ctx.response.pong())

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
            with ctx.benchmark.measure("global:after_invoke"):
                if inspect.iscoroutinefunction(self.bot._after_invoke):
                    await self.bot._after_invoke(ctx)
                else:
                    self.bot._after_invoke(ctx)  # type: ignore

        self.bot.loop.create_task(_run_background())

    async def _handle_application_command(
        self,
        ctx: "Context",
        data: dict
    ) -> web.Response:
        """ Used to handle application commands. """
        await self._run_before_invoke(ctx)

        _log.debug("Received slash command, processing...")

        command_name = data["data"]["name"]
        cmd = self.bot.commands.get(command_name, None)

        if not cmd:
            _log.warning(f"Unhandled command: {command_name}")
            return self.jsonify({"error": "command not found"}, status=404)

        cmd, _ = self._dig_subcommand(cmd, data)
        ctx.command = cmd

        try:
            await self.bot._run_global_checks(ctx)

            payload = await cmd._make_context_and_run(context=ctx)

            await self._run_after_invoke(ctx)

            with ctx.benchmark.measure("backend:response", internal=True):
                if isinstance(payload, EmptyResponse):
                    return web.Response(status=202)

                return self.multipart_response(payload)

        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", ctx, e)
            else:
                _log.error(
                    f"Error while running command {getattr(cmd, 'name', None)}",
                    exc_info=e
                )

            send_error = self.error_messages(ctx, e)
            if send_error and isinstance(send_error, BaseResponse):
                return self.jsonify(send_error.to_dict())

            raise HTTPInternalServerError()

    async def _handle_interaction(
        self,
        ctx: "Context",
        data: dict
    ) -> web.Response:
        """ Used to handle interactions. """
        await self._run_before_invoke(ctx)

        _log.debug("Received interaction, processing...")
        custom_id = data["data"]["custom_id"]

        try:
            local_view = None

            if (local_view is None and ctx.custom_id):
                local_view = self.bot._view_storage.get(ctx.custom_id, None)

            if (local_view is None and ctx.message):
                local_view = self.bot._view_storage.get(ctx.message.id, None)

                if not local_view and ctx.message.interaction:
                    local_view = self.bot._view_storage.get(ctx.message.interaction.id, None)

            if local_view:
                with ctx.benchmark.measure("view:callback", internal=True):
                    payload = await local_view.callback(ctx)
                    return self.multipart_response(payload)

            with ctx.benchmark.measure("backend:find_interaction"):
                intreact = self.bot.find_interaction(custom_id)

            if not intreact:
                _log.debug(f"Unhandled interaction received (custom_id: {custom_id})")
                return self.jsonify({"error": "interaction not found"}, status=404)

            payload = await intreact.run(ctx)
            await self._run_after_invoke(ctx)
            return self.multipart_response(payload)

        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", ctx, e)
            else:
                _log.error(f"Error while running interaction {custom_id}", exc_info=e)

            return self.jsonify({"error": "internal server error"}, status=500)

    async def _handle_autocomplete(
        self,
        ctx: "Context",
        data: dict
    ) -> web.Response:
        """ Used to handle autocomplete interactions. """
        _log.debug("Received autocomplete interaction, processing...")

        command_name = data.get("data", {}).get("name", None)
        cmd = self.bot.commands.get(command_name)

        try:
            if not cmd:
                _log.warning(f"Unhandled autocomplete received (name: {command_name})")
                return self.jsonify({"error": "command not found"}, status=404)

            cmd, data_options = self._dig_subcommand(cmd, data)

            find_focused = next((x for x in data_options if x.get("focused", False)), None)

            if not find_focused:
                _log.warning("Failed to find focused option in autocomplete")
                return self.jsonify({"error": "focused option not found"}, status=400)

            result = await cmd.run_autocomplete(ctx, find_focused["name"], find_focused["value"])
            if isinstance(result, dict):
                return self.jsonify(result)
            return result

        except Exception as e:
            if self.bot.has_any_dispatch("interaction_error"):
                self.bot.dispatch("interaction_error", ctx, e)
            else:
                _log.error(f"Error while running autocomplete {getattr(cmd, 'name', None)}", exc_info=e)
            raise HTTPInternalServerError()

    async def _index_interactions_endpoint(self, request: web.Request) -> web.Response:
        """
        The main function to handle all HTTP requests sent by Discord.

        Please do not touch this function, unless you know what you're doing
        """
        # Validate signature
        await self._validate_request(request)

        try:
            data = await request.json(loads=orjson.loads)
        except Exception:
            return self.jsonify({"error": "invalid json"}, status=400)

        if self.debug_events:
            self.bot.dispatch("raw_interaction", copy.deepcopy(data))

        context = self.bot._context(self.bot, data)
        data_type = data.get("type", -1)

        match data_type:
            case InteractionType.ping:
                return self._handle_ack_ping(context, data)

            case InteractionType.application_command:
                with context.benchmark.measure("start_end:application_command"):
                    return await self._handle_application_command(
                        context, data
                    )

            case InteractionType.message_component | InteractionType.modal_submit:
                with context.benchmark.measure(f"start_end:{InteractionType(data_type).name}"):
                    return await self._handle_interaction(
                        context, data
                    )

            case InteractionType.application_command_autocomplete:
                with context.benchmark.measure("start_end:autocomplete"):
                    return await self._handle_autocomplete(
                        context, data
                    )

            case _:  # Unknown
                _log.debug(f"Unhandled interaction recieved (type: {data_type})")
                return self.jsonify({"error": "invalid request body"}, status=400)

    def error_messages(self, ctx: "Context", e: Exception) -> MessageResponse | None:
        """
        Used to return error messages to Discord.

        By default, it will only cover CheckFailed errors.
        You can overwrite this function to return your own error messages.

        Parameters
        ----------
        ctx:
            The context of the command
        e:
            The exception that was raised

        Returns
        -------
            The message response provided by the library error handler
        """
        if isinstance(e, CheckFailed):
            return ctx.response.send_message(content=str(e), ephemeral=True)
        return None

    async def index_ping(
        self,
        _request: web.Request
    ) -> web.Response:
        """
        Used to ping the interaction url, to check if it's working.

        You can overwrite this function to return your own data as well.
        Remember that it must return `dict`

        Parameters
        ----------
        request:
            The incoming request object (not used by default)
        """
        if not self.bot.is_ready():
            return self.jsonify({"error": "bot is not ready yet"}, status=503)

        return self.jsonify({
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
        })

    def jsonify(
        self,
        data: dict,
        *,
        status: int = 200
    ) -> web.Response:
        """
        Respond with JSON data in a standardized way using orjson.

        Serves as the replacement for aiohttp's built-in json response.

        Parameters
        ----------
        data:
            The data to respond with
        status:
            The status code to respond with

        Returns
        -------
            The response object
        """
        return web.Response(
            body=orjson.dumps(data),
            headers={"Content-Type": "application/json"},
            status=status
        )

    def multipart_response(
        self,
        body: BaseResponse | None,
        *,
        status: int = 200
    ) -> web.Response:
        """
        Respond with multipart data in a standardized way.

        Parameters
        ----------
        body:
            The body to respond with
        status:
            The status code to respond with

        Returns
        -------
            The response object
        """
        if body is None:
            raise ValueError("body cannot be None")

        return web.Response(
            body=body.to_multipart(),
            headers={"Content-Type": body.content_type},
            status=status
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
            Host to use, if not provided, it will use `127.0.0.1`
        port:
            Port to use, if not provided, it will use `8080`
        """
        int_path = str(self.bot.interaction_path)
        if not int_path.startswith("/"):
            _log.warning(
                "Interaction path should start with a slash ( / ), adding it automatically"
            )
            int_path = f"/{int_path}"

        if not self.bot.disable_default_get_path:
            self.router.add_get(int_path, self.index_ping)

        self.router.add_post(int_path, self._index_interactions_endpoint)

        try:
            _log.info(f"Serving on http://{host}:{port}")
            web.run_app(
                self,
                host=host,
                port=port,
                print=lambda *_, **__: None,
                loop=self.bot.loop,
                backlog=self.bot.max_pending_connections
            )
        except KeyboardInterrupt:
            pass
