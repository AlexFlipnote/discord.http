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
        resp = self.client.loop.run_until_complete(self.client.backend._handle_interaction(ctx, data))
        return ctx, resp

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


if __name__ == "__main__":
    unittest.main()
