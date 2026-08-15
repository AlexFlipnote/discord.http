import unittest

from types import SimpleNamespace

from discord_http import (
    Attachment, Member, Permissions, Role, TextChannel, User, VoiceChannel,
)
from discord_http.commands import (
    Choice, Command, Range, SubGroup, bot_has_permissions,
    default_permissions, has_permissions, locales,
)
from discord_http.enums import ChannelType, CommandOptionType


def _make_command(func, **overrides) -> Command:
    kwargs = {"command": func, "name": "test", "description": "d"}
    kwargs.update(overrides)
    return Command(**kwargs)


def _first_option(func, **overrides) -> dict:
    return _make_command(func, **overrides).options[0]


class TestCommandNameDescriptionValidation(unittest.TestCase):
    async def _f(self, ctx) -> None:
        pass

    def test_uppercase_name_raises(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertRaises(ValueError):
            Command(command=f, name="Test", description="d")

    def test_description_over_100_chars_raises(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertRaises(ValueError):
            Command(command=f, name="test", description="x" * 101)

    def test_empty_description_raises(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertRaises(ValueError):
            Command(command=f, name="test", description="")

    def test_missing_description_falls_back_to_docstring(self) -> None:
        async def f(ctx) -> None:
            """ A docstring description. """
        cmd = Command(command=f, name="test")
        self.assertEqual(cmd.description, "A docstring description.")


class TestCommandAnnotationInferenceBasicTypes(unittest.TestCase):
    def test_str_annotation(self) -> None:
        async def f(ctx, value: str) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.string))
        self.assertTrue(opt["required"])

    def test_int_annotation(self) -> None:
        async def f(ctx, value: int) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.integer))

    def test_float_annotation(self) -> None:
        async def f(ctx, value: float) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.number))

    def test_bool_annotation(self) -> None:
        async def f(ctx, value: bool) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.boolean))

    def test_default_value_marks_option_not_required(self) -> None:
        async def f(ctx, value: str = "x") -> None:
            pass
        opt = _first_option(f)
        self.assertFalse(opt["required"])

    def test_optional_type_still_required_without_default(self) -> None:
        # Optionality of the Discord option comes from having a default
        # value, not from an `int | None` annotation by itself.
        async def f(ctx, value: int | None) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.integer))
        self.assertTrue(opt["required"])

    def test_optional_type_with_default_is_not_required(self) -> None:
        async def f(ctx, value: int | None = None) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.integer))
        self.assertFalse(opt["required"])

    def test_unrecognized_annotation_falls_back_to_string(self) -> None:
        class Whatever:
            pass

        async def f(ctx, value: Whatever) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.string))

    def test_self_parameter_is_skipped_in_addition_to_ctx(self) -> None:
        async def f(self, ctx, value: str) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["name"], "value")


class TestCommandAnnotationInferenceDiscordTypes(unittest.TestCase):
    def test_member_annotation(self) -> None:
        async def f(ctx, value: Member) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.user))

    def test_user_annotation(self) -> None:
        async def f(ctx, value: User) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.user))

    def test_role_annotation(self) -> None:
        async def f(ctx, value: Role) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.role))

    def test_attachment_annotation(self) -> None:
        async def f(ctx, value: Attachment) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.attachment))

    def test_single_channel_type(self) -> None:
        async def f(ctx, value: TextChannel) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.channel))
        self.assertEqual(opt["channel_types"], [int(ChannelType.guild_text)])

    def test_union_of_channel_types_combines_channel_types(self) -> None:
        async def f(ctx, value: TextChannel | VoiceChannel) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.channel))
        self.assertCountEqual(
            opt["channel_types"],
            [int(ChannelType.guild_text), int(ChannelType.guild_voice)],
        )

    def test_user_then_member_union_resolves_to_user_type(self) -> None:
        async def f(ctx, value: User | Member) -> None:
            pass
        cmd = _make_command(f)
        self.assertEqual(cmd.options[0]["type"], int(CommandOptionType.user))
        self.assertIn("value", cmd._Command__user_member_objects)

    def test_member_then_user_union_resolves_to_user_type(self) -> None:
        async def f(ctx, value: Member | User) -> None:
            pass
        cmd = _make_command(f)
        self.assertEqual(cmd.options[0]["type"], int(CommandOptionType.user))
        self.assertIn("value", cmd._Command__user_member_objects)


class TestCommandAnnotationInferenceChoiceAndRange(unittest.TestCase):
    def test_choice_str_defaults_to_string_type(self) -> None:
        async def f(ctx, value: Choice[str]) -> None:
            pass
        cmd = _make_command(f)
        self.assertEqual(cmd.options[0]["type"], int(CommandOptionType.string))
        self.assertIn("value", cmd._Command__list_choices)

    def test_choice_int_uses_integer_type(self) -> None:
        async def f(ctx, value: Choice[int]) -> None:
            pass
        cmd = _make_command(f)
        self.assertEqual(cmd.options[0]["type"], int(CommandOptionType.integer))

    def test_choice_float_uses_number_type(self) -> None:
        async def f(ctx, value: Choice[float]) -> None:
            pass
        cmd = _make_command(f)
        self.assertEqual(cmd.options[0]["type"], int(CommandOptionType.number))

    def test_literal_annotation_replicates_choice_behaviour(self) -> None:
        from typing import Literal

        async def f(ctx, value: Literal["a", "b"]) -> None:
            pass
        cmd = _make_command(f)
        self.assertEqual(cmd.options[0]["type"], int(CommandOptionType.string))
        self.assertEqual(f.__choices_params__["value"], {"a": "a", "b": "b"})

    def test_range_str_sets_length_bounds(self) -> None:
        async def f(ctx, value: Range[str, 1, 50]) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.string))
        self.assertEqual(opt["min_length"], 1)
        self.assertEqual(opt["max_length"], 50)

    def test_range_int_sets_value_bounds(self) -> None:
        async def f(ctx, value: Range[int, 1, 10]) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.integer))
        self.assertEqual(opt["min_value"], 1)
        self.assertEqual(opt["max_value"], 10)

    def test_range_float_uses_number_type(self) -> None:
        async def f(ctx, value: Range[float, 0.0, 1.0]) -> None:
            pass
        opt = _first_option(f)
        self.assertEqual(opt["type"], int(CommandOptionType.number))


class TestCommandPermissionsChecks(unittest.TestCase):
    def _cmd(self, decorator=None) -> Command:
        async def f(ctx) -> None:
            pass
        if decorator is not None:
            f = decorator(f)
        return _make_command(f)

    def test_has_permissions_returns_zero_without_decorator(self) -> None:
        cmd = self._cmd()
        ctx = SimpleNamespace(user=SimpleNamespace(resolved_permissions=Permissions.none()))
        self.assertEqual(cmd._has_permissions(ctx), Permissions(0))

    def test_has_permissions_returns_zero_without_resolved_permissions(self) -> None:
        cmd = self._cmd(has_permissions("manage_messages"))
        ctx = SimpleNamespace(user=SimpleNamespace())
        self.assertEqual(cmd._has_permissions(ctx), Permissions(0))

    def test_has_permissions_administrator_bypasses_everything(self) -> None:
        cmd = self._cmd(has_permissions("manage_messages"))
        ctx = SimpleNamespace(
            user=SimpleNamespace(resolved_permissions=Permissions.from_names("administrator")),
        )
        self.assertEqual(cmd._has_permissions(ctx), Permissions(0))

    def test_has_permissions_returns_the_missing_permission(self) -> None:
        cmd = self._cmd(has_permissions("manage_messages"))
        ctx = SimpleNamespace(user=SimpleNamespace(resolved_permissions=Permissions.none()))
        missing = cmd._has_permissions(ctx)
        self.assertIn("manage_messages", missing.to_names())

    def test_bot_has_permissions_returns_zero_without_decorator(self) -> None:
        cmd = self._cmd()
        ctx = SimpleNamespace(app_permissions=Permissions.none())
        self.assertEqual(cmd._bot_has_permissions(ctx), Permissions(0))

    def test_bot_has_permissions_administrator_bypasses_everything(self) -> None:
        cmd = self._cmd(bot_has_permissions("embed_links"))
        ctx = SimpleNamespace(app_permissions=Permissions.from_names("administrator"))
        self.assertEqual(cmd._bot_has_permissions(ctx), Permissions(0))

    def test_bot_has_permissions_returns_the_missing_permission(self) -> None:
        cmd = self._cmd(bot_has_permissions("embed_links"))
        ctx = SimpleNamespace(app_permissions=Permissions.none())
        missing = cmd._bot_has_permissions(ctx)
        self.assertIn("embed_links", missing.to_names())


class TestPermissionDecoratorValidation(unittest.TestCase):
    def test_no_args_leaves_function_untouched(self) -> None:
        async def f(ctx) -> None:
            pass
        result = has_permissions()(f)
        self.assertFalse(hasattr(result, "__has_permissions__"))

    def test_mixed_permissions_object_and_string_raises(self) -> None:
        # Only args[0] is checked for being a Permissions instance - if it's
        # a string instead, every other arg (including a Permissions object)
        # must also be a string, or this raises.
        async def f(ctx) -> None:
            pass
        with self.assertRaises(TypeError):
            has_permissions("manage_messages", Permissions.none())(f)  # type: ignore[arg-type]

    def test_mixed_string_and_non_string_raises(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertRaises(TypeError):
            has_permissions("manage_messages", 123)(f)  # type: ignore[arg-type]

    def test_single_permissions_object_is_accepted(self) -> None:
        async def f(ctx) -> None:
            pass
        perms = Permissions.from_names("manage_messages")
        result = has_permissions(perms)(f)
        self.assertEqual(result.__has_permissions__, perms)

    def test_default_permissions_sets_attribute(self) -> None:
        async def f(ctx) -> None:
            pass
        result = default_permissions("manage_messages")(f)
        self.assertIn("manage_messages", result.__default_permissions__.to_names())

    def test_bot_has_permissions_sets_attribute(self) -> None:
        async def f(ctx) -> None:
            pass
        result = bot_has_permissions("embed_links")(f)
        self.assertIn("embed_links", result.__bot_has_permissions__.to_names())


class TestLocalesValidation(unittest.TestCase):
    def test_valid_locale_and_option_are_stored(self) -> None:
        async def f(ctx, value: str) -> None:
            pass
        result = locales({
            "no": {"_": ("ping", "beskrivelse"), "value": ("verdi",)},
        })(f)
        self.assertIn("no", result.__locales__)
        keys = {c.key: c for c in result.__locales__["no"]}
        self.assertEqual(keys["_"].name, "ping")
        self.assertEqual(keys["_"].description, "beskrivelse")
        self.assertEqual(keys["value"].name, "verdi")
        self.assertEqual(keys["value"].description, "...")  # defaulted, only 1 value given

    def test_unsupported_locale_is_skipped(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertLogs("discord_http", level="WARNING"):
            result = locales({"xx-not-real": {"_": ("a", "b")}})(f)
        self.assertNotIn("xx-not-real", result.__locales__)

    def test_non_dict_translation_value_is_skipped(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertLogs("discord_http", level="WARNING"):
            result = locales({"no": "not-a-dict"})(f)  # type: ignore[arg-type]
        self.assertNotIn("no", result.__locales__)

    def test_empty_values_tuple_is_skipped(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertLogs("discord_http", level="WARNING"):
            result = locales({"no": {"_": ()}})(f)
        self.assertNotIn("no", result.__locales__)

    def test_all_entries_skipped_means_locale_not_added(self) -> None:
        async def f(ctx) -> None:
            pass
        with self.assertLogs("discord_http", level="WARNING"):
            result = locales({"no": {"_": ()}})(f)
        self.assertEqual(result.__locales__, {})


class TestSubGroupOptionsRecursiveStripping(unittest.TestCase):
    def test_flat_subcommand_becomes_sub_command_type(self) -> None:
        parent = SubGroup(name="parent", description="d")

        async def sub1(ctx, value: str) -> None:
            pass
        parent.command(name="sub1", description="d1")(sub1)

        options = parent.options
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["type"], int(CommandOptionType.sub_command))
        self.assertEqual(options[0]["options"][0]["name"], "value")

    def test_nested_group_becomes_sub_command_group_type_recursively(self) -> None:
        parent = SubGroup(name="parent", description="d")

        async def group_func(ctx) -> None:
            pass
        nested = parent.group(name="nested", description="d2")(group_func)

        async def sub2(ctx) -> None:
            pass
        nested.command(name="sub2", description="d3")(sub2)

        options = parent.options
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["type"], int(CommandOptionType.sub_command_group))
        inner = options[0]["options"]
        self.assertEqual(inner[0]["name"], "sub2")
        self.assertEqual(inner[0]["type"], int(CommandOptionType.sub_command))

    def test_invalid_top_level_keys_are_stripped(self) -> None:
        parent = SubGroup(name="parent", description="d")

        async def sub1(ctx) -> None:
            pass
        parent.command(name="sub1", description="d1")(sub1)

        option = parent.options[0]
        for key in ("nsfw", "integration_types", "contexts", "default_member_permissions"):
            self.assertNotIn(key, option)


if __name__ == "__main__":
    unittest.main()
