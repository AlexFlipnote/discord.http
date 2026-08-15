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


if __name__ == "__main__":
    unittest.main()
