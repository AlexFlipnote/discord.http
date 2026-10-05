import io
import orjson
import unittest

from aiohttp.web_exceptions import HTTPBadRequest

from discord_http.backend import DiscordHTTP
from discord_http.commands import SubGroup
from discord_http.enums import CommandOptionType


class FakeCommand:
    """ Stand-in for a leaf Command - _dig_subcommand() never inspects it,
    it's only used as the return value once the walk reaches a non-SubGroup. """
    def __init__(self, name: str):
        self.name = name


def _data(options: list[dict]) -> dict:
    return {"data": {"options": options}}


def _dig(cmd, data):
    # _dig_subcommand() never touches `self`, so it's safe to call unbound.
    return DiscordHTTP._dig_subcommand(None, cmd, data)  # type: ignore[arg-type]


class TestDigSubcommandNoGroup(unittest.TestCase):
    def test_plain_command_returns_immediately_with_top_level_options(self) -> None:
        cmd = FakeCommand("leaf")
        options = [{"name": "value", "type": int(CommandOptionType.string)}]
        result_cmd, result_options = _dig(cmd, _data(options))
        self.assertIs(result_cmd, cmd)
        self.assertEqual(result_options, options)

    def test_none_command_returns_none(self) -> None:
        result_cmd, result_options = _dig(None, _data([]))
        self.assertIsNone(result_cmd)
        self.assertEqual(result_options, [])


class TestDigSubcommandOneLevel(unittest.TestCase):
    def test_digs_into_matching_subcommand(self) -> None:
        parent = SubGroup(name="parent", description="d")
        leaf = FakeCommand("sub1")
        parent.subcommands["sub1"] = leaf

        inner_options = [{"name": "value", "type": int(CommandOptionType.string)}]
        data = _data([{
            "name": "sub1", "type": int(CommandOptionType.sub_command),
            "options": inner_options,
        }])

        result_cmd, result_options = _dig(parent, data)
        self.assertIs(result_cmd, leaf)
        self.assertEqual(result_options, inner_options)

    def test_ignores_non_subcommand_options_when_searching(self) -> None:
        parent = SubGroup(name="parent", description="d")
        leaf = FakeCommand("sub1")
        parent.subcommands["sub1"] = leaf

        data = _data([
            {"name": "unrelated", "type": int(CommandOptionType.string)},
            {"name": "sub1", "type": int(CommandOptionType.sub_command), "options": []},
        ])

        result_cmd, _ = _dig(parent, data)
        self.assertIs(result_cmd, leaf)

    def test_no_subcommand_option_present_raises_bad_request(self) -> None:
        parent = SubGroup(name="parent", description="d")
        data = _data([{"name": "value", "type": int(CommandOptionType.string)}])
        with self.assertRaises(HTTPBadRequest):
            _dig(parent, data)

    def test_subcommand_name_not_registered_locally_raises_bad_request(self) -> None:
        parent = SubGroup(name="parent", description="d")
        data = _data([{
            "name": "ghost", "type": int(CommandOptionType.sub_command), "options": [],
        }])
        with self.assertLogs("discord_http", level="WARNING"), self.assertRaises(HTTPBadRequest):
            _dig(parent, data)


class TestDigSubcommandNestedGroups(unittest.TestCase):
    def test_digs_through_two_levels_of_subgroups(self) -> None:
        root = SubGroup(name="root", description="d")
        nested = SubGroup(name="nested", description="d2")
        leaf = FakeCommand("sub1")

        root.subcommands["nested"] = nested
        nested.subcommands["sub1"] = leaf

        deepest_options = [{"name": "value", "type": int(CommandOptionType.string)}]
        data = _data([{
            "name": "nested", "type": int(CommandOptionType.sub_command_group),
            "options": [{
                "name": "sub1", "type": int(CommandOptionType.sub_command),
                "options": deepest_options,
            }],
        }])

        result_cmd, result_options = _dig(root, data)
        self.assertIs(result_cmd, leaf)
        self.assertEqual(result_options, deepest_options)



class TestResponseEncoding(unittest.TestCase):
    """ Responses are JSON unless there are files to upload. """

    def setUp(self) -> None:
        from discord_http.response import MessageResponse, DeferResponse, EmptyResponse, AutocompleteResponse
        self.MessageResponse = MessageResponse
        self.DeferResponse = DeferResponse
        self.EmptyResponse = EmptyResponse
        self.AutocompleteResponse = AutocompleteResponse

    def _respond(self, body):
        return DiscordHTTP.multipart_response(None, body)  # type: ignore[arg-type]

    def test_message_without_files_is_json(self) -> None:
        resp = self._respond(self.MessageResponse(content="hello"))
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "application/json")
        payload = orjson.loads(resp.body)
        self.assertEqual(payload["type"], 4)
        self.assertEqual(payload["data"]["content"], "hello")

    def test_message_with_files_is_multipart(self) -> None:
        from discord_http.file import File
        resp = self._respond(self.MessageResponse(content="x", file=File(io.BytesIO(b"abc"), filename="a.txt")))
        self.assertTrue(resp.headers["Content-Type"].startswith("multipart/form-data"))

    def test_other_responses_are_json(self) -> None:
        resp = self._respond(self.DeferResponse())
        self.assertEqual(resp.headers["Content-Type"], "application/json")
        self.assertEqual(orjson.loads(resp.body)["type"], 6)

        resp = self._respond(self.AutocompleteResponse({"a": "A"}))
        self.assertEqual(orjson.loads(resp.body)["data"]["choices"], [{"name": "A", "value": "a"}])

    def test_empty_response_is_202(self) -> None:
        resp = self._respond(self.EmptyResponse())
        self.assertEqual(resp.status, 202)

    def test_none_still_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._respond(None)


class TestViewCallbackWithoutPayload(unittest.TestCase):
    """ A stored view whose callback returns None must not turn into a 500. """

    def setUp(self) -> None:
        from tests.test_context import _make_client
        self.client = _make_client()

    def tearDown(self) -> None:
        from tests.test_context import close_client
        close_client(self.client)

    def _run(self, storage_key, *, timed_out: bool, interaction_id: str | None = None):
        from discord_http.context import Context
        from discord_http.view import View
        from tests.test_context import _message, _payload

        view = View()
        view._timeout_bool = timed_out
        self.client._view_storage[storage_key] = view

        data = _payload(
            3, {"custom_id": "unregistered", "component_type": 2},
            message=_message("500", interaction_id=interaction_id)
        )
        ctx = Context(self.client, data)
        result = self.client.loop.run_until_complete(self.client.backend._handle_interaction(ctx, data))
        return ctx, self.client.backend._to_http_response(result)

    def test_timed_out_view_acks_with_deferred_update(self) -> None:
        _, resp = self._run(500, timed_out=True)
        self.assertEqual(resp.status, 200)
        self.assertEqual(orjson.loads(resp.body)["type"], 6)

    def test_view_without_call_after_returns_202(self) -> None:
        _, resp = self._run(500, timed_out=False)
        self.assertEqual(resp.status, 202)

    def test_view_found_by_message_interaction_id(self) -> None:
        _, resp = self._run(900, timed_out=False, interaction_id="900")
        self.assertEqual(resp.status, 202)


class TestGatewayInteractions(unittest.TestCase):
    """ Interactions over the gateway run like HTTP ones, but respond through the callback endpoint. """

    def setUp(self) -> None:
        from types import SimpleNamespace
        from tests.test_context import _make_client

        self.client = _make_client()
        self.calls: list[tuple[str, str, dict]] = []

        async def fake_query(method, path, **kwargs):
            self.calls.append((method, path, kwargs))
            return SimpleNamespace(response=None)

        self.client.state.query = fake_query

    def tearDown(self) -> None:
        from tests.test_context import close_client
        close_client(self.client)

    def _run(self, data: dict, *, replayed: bool = False) -> None:
        import asyncio

        self.client.loop.run_until_complete(
            self.client.backend.handle_gateway_interaction(data, replayed=replayed)
        )
        # Let any background tasks (like call_after) finish
        self.client.loop.run_until_complete(asyncio.sleep(0.05))

    @staticmethod
    def _fresh_id(seconds_ago: float = 0.0) -> str:
        """ An interaction ID created `seconds_ago`, old ones are skipped as stale. """
        import time
        from discord_http import utils

        return str((int((time.time() - seconds_ago) * 1000) - utils.DISCORD_EPOCH) << 22)

    def _command(self, name: str = "ping", *, seconds_ago: float = 0.0) -> dict:
        from tests.test_context import _payload

        data = _payload(2, {"id": "1", "name": name, "type": 1}, id=self._fresh_id(seconds_ago))
        self.callback_path = f"/interactions/{data['id']}/tok/callback"
        return data

    def test_reply_is_posted_to_callback_endpoint(self) -> None:
        @self.client.command()
        async def ping(ctx):
            return ctx.response.send_message("Pong!")

        self._run(self._command())

        self.assertEqual(len(self.calls), 1)
        method, path, kwargs = self.calls[0]
        self.assertEqual((method, path), ("POST", self.callback_path))
        self.assertEqual(kwargs["json"]["type"], 4)
        self.assertEqual(kwargs["json"]["data"]["content"], "Pong!")

    def test_files_are_sent_as_multipart(self) -> None:
        from discord_http.file import File

        @self.client.command()
        async def ping(ctx):
            return ctx.response.send_message("x", file=File(io.BytesIO(b"abc"), filename="a.txt"))

        self._run(self._command())

        _, _, kwargs = self.calls[0]
        self.assertNotIn("json", kwargs)
        self.assertTrue(kwargs["headers"]["Content-Type"].startswith("multipart/form-data"))

    def test_unknown_command_sends_nothing(self) -> None:
        self._run(self._command("does_not_exist"))
        self.assertEqual(self.calls, [])

    def test_empty_response_sends_nothing(self) -> None:
        from discord_http.view import View
        from tests.test_context import _message, _payload

        view = View()
        view._timeout_bool = False
        self.client._view_storage[500] = view

        self._run(_payload(
            3, {"custom_id": "unregistered", "component_type": 2},
            message=_message("500"), id=self._fresh_id()
        ))
        self.assertEqual(self.calls, [])

    def test_command_error_does_not_raise(self) -> None:
        @self.client.command()
        async def ping(ctx):
            raise RuntimeError("boom")

        self._run(self._command())  # Must not raise

    def test_call_after_runs_after_the_callback(self) -> None:
        order = []

        async def after():
            order.append("call_after")

        @self.client.command()
        async def ping(ctx):
            return ctx.response.send_message("hi", call_after=after)

        async def fake_query(method, path, **kwargs):
            order.append("callback")

        self.client.state.query = fake_query
        self._run(self._command())

        self.assertEqual(order, ["callback", "call_after"])

    def test_expired_interaction_logs_its_age(self) -> None:
        from types import SimpleNamespace
        from discord_http.errors import NotFound

        @self.client.command()
        async def ping(ctx):
            return ctx.response.send_message("Pong!")

        async def fake_query(method, path, **kwargs):
            raise NotFound(SimpleNamespace(
                status=404, reason="Not Found",
                response='{"message": "Unknown interaction", "code": 10062}'
            ))

        self.client.state.query = fake_query

        with self.assertLogs("discord_http.backend", level="WARNING") as logs:
            self._run(self._command())  # Must not raise

        self.assertIn("Discord only waits 3s", logs.output[0])

    def test_shard_marks_interactions_during_resume_as_replayed(self) -> None:
        from discord_http.gateway.shard import Shard

        received = []
        self.client._handle_gateway_interaction = lambda data, *, replayed: received.append(replayed)

        shard = Shard.__new__(Shard)
        shard.bot = self.client
        shard.shard_id = 0

        shard._replaying = True
        shard._parse_interaction_create(self._command())
        shard._replaying = False
        shard._parse_interaction_create(self._command())

        self.assertEqual(received, [True, False])

    def test_stale_interaction_is_skipped_without_running_the_command(self) -> None:
        ran = []

        @self.client.command()
        async def ping(ctx):
            ran.append(True)
            return ctx.response.send_message("Pong!")

        with self.assertLogs("discord_http.backend", level="WARNING") as logs:
            self._run(self._command(seconds_ago=10), replayed=True)

        self.assertEqual(ran, [])
        self.assertEqual(self.calls, [])
        self.assertIn("Skipped gateway interaction", logs.output[0])

    def test_old_looking_live_interaction_still_runs(self) -> None:
        """ A drifting system clock must never drop live interactions, only replays are age-checked. """
        ran = []

        @self.client.command()
        async def ping(ctx):
            ran.append(True)
            return ctx.response.send_message("Pong!")

        self._run(self._command(seconds_ago=10), replayed=False)

        self.assertEqual(ran, [True])
        self.assertEqual(len(self.calls), 1)

    def test_shard_schedules_interaction_create(self) -> None:
        import asyncio
        from discord_http.gateway.shard import Shard

        @self.client.command()
        async def ping(ctx):
            return ctx.response.send_message("Pong!")

        shard = Shard.__new__(Shard)
        shard.bot = self.client
        shard.shard_id = 0
        shard._replaying = False

        before = len(self.client._background_tasks)
        shard._parse_interaction_create(self._command())
        self.assertEqual(len(self.client._background_tasks), before + 1)
        self.client.loop.run_until_complete(asyncio.sleep(0.05))

        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], self.callback_path)


class TestConnectionMode(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_context import _make_client
        self.client = _make_client()

    def tearDown(self) -> None:
        from tests.test_context import close_client
        close_client(self.client)

    def _resolve(self, endpoint_url: str | None, *, gateway: bool, intents=None) -> str:
        from types import SimpleNamespace

        self.client.application = SimpleNamespace(interactions_endpoint_url=endpoint_url)
        self.client.enable_gateway = gateway
        self.client.intents = intents
        return self.client._resolve_connection_mode()

    def test_no_endpoint_with_intents_is_ws_plus(self) -> None:
        from discord_http.gateway import Intents

        self.assertEqual(self._resolve(None, gateway=True, intents=Intents.guild_messages), "WS+")

    def test_no_endpoint_with_empty_intents_is_ws(self) -> None:
        from discord_http.gateway import Intents

        self.assertEqual(self._resolve(None, gateway=True, intents=Intents.none()), "WS")

    def test_no_endpoint_enables_gateway(self) -> None:
        self.assertEqual(self._resolve(None, gateway=False), "WS")
        self.assertTrue(self.client.enable_gateway)

    def test_no_endpoint_warns_when_gateway_was_not_enabled(self) -> None:
        with self.assertLogs("discord_http.client", level="WARNING"):
            self._resolve(None, gateway=False)

    def test_explicit_gateway_without_endpoint_is_ws_without_warning(self) -> None:
        with self.assertNoLogs("discord_http.client", level="WARNING"):
            self.assertEqual(self._resolve(None, gateway=True), "WS")

        # Still nothing to serve over HTTP, so the HTTP server is skipped as well
        self.assertFalse(self.client._needs_http_server())

    def test_endpoint_without_gateway_is_http(self) -> None:
        self.assertEqual(self._resolve("https://example.com", gateway=False), "HTTP")
        self.assertFalse(self.client.enable_gateway)

    def test_endpoint_with_gateway_is_http_ws(self) -> None:
        self.assertEqual(self._resolve("https://example.com", gateway=True), "HTTP+WS")

    def _needs_http(self, endpoint_url: str | None, webhook_events_path: str | None = None) -> bool:
        from types import SimpleNamespace

        self.client.application = SimpleNamespace(interactions_endpoint_url=endpoint_url)
        self.client.webhook_events_path = webhook_events_path
        return self.client._needs_http_server()

    def test_ws_mode_skips_http_server(self) -> None:
        self.assertFalse(self._needs_http(None))

    def test_endpoint_needs_http_server(self) -> None:
        self.assertTrue(self._needs_http("https://example.com"))

    def test_webhook_events_still_need_http_server_in_ws_mode(self) -> None:
        self.assertTrue(self._needs_http(None, webhook_events_path="/events"))

    def test_ctrl_c_in_ws_mode_cancels_pending_tasks(self) -> None:
        import asyncio

        loop = self.client.loop
        pending: list[asyncio.Task] = []

        async def fake_prepare_bot():
            # Like the shard's background tasks, still running when the bot is stopped
            pending.append(loop.create_task(asyncio.sleep(3600)))

        def ctrl_c():
            raise KeyboardInterrupt

        self.client._prepare_bot = fake_prepare_bot
        loop.call_later(0.05, ctrl_c)

        self.client._run_without_http()  # Must not raise

        self.assertTrue(pending[0].cancelled())
        self.assertTrue(loop.is_closed())


if __name__ == "__main__":
    unittest.main()
