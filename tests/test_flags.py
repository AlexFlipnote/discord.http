import unittest

from discord_http import (
    PermissionType, MessageFlags, PermissionOverwrite,
    Permissions, Snowflake
)


class DummyRoleTarget(Snowflake):
    _target_type = PermissionType.role


class TestFlags(unittest.TestCase):
    def test_from_names_add_remove_and_copy(self) -> None:
        flags = MessageFlags.from_names("ephemeral", "loading")
        self.assertIn("ephemeral", flags.to_names())
        self.assertIn("loading", flags.to_names())

        updated = flags.copy().remove_flags("loading")
        self.assertIn("ephemeral", updated.to_names())
        self.assertNotIn("loading", updated.to_names())

    def test_invalid_flag_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            MessageFlags.from_names("does_not_exist")

    def test_permissions_handle_overwrite(self) -> None:
        base = Permissions.from_names("send_messages", "embed_links")
        allow = int(Permissions.from_names("manage_messages"))
        deny = int(Permissions.from_names("embed_links"))

        overwritten = base.handle_overwrite(allow=allow, deny=deny)
        self.assertIn("send_messages", overwritten.to_names())
        self.assertIn("manage_messages", overwritten.to_names())
        self.assertNotIn("embed_links", overwritten.to_names())


class TestPermissionOverwrite(unittest.TestCase):
    def test_to_from_dict_roundtrip(self) -> None:
        original = PermissionOverwrite(
            target=123,
            allow=Permissions.from_names("send_messages"),
            deny=Permissions.from_names("manage_messages"),
            target_type=PermissionType.member,
        )
        data = original.to_dict()
        recreated = PermissionOverwrite.from_dict(data)

        self.assertEqual(int(recreated.target), 123)
        self.assertEqual(int(recreated.allow), int(original.allow))
        self.assertEqual(int(recreated.deny), int(original.deny))
        self.assertEqual(recreated.target_type, PermissionType.member)

    def test_target_type_can_be_inferred_as_role(self) -> None:
        overwrite = PermissionOverwrite(target=DummyRoleTarget(321))
        self.assertTrue(overwrite.is_role())
        self.assertFalse(overwrite.is_member())

    def test_invalid_allow_or_deny_type_raises(self) -> None:
        with self.assertRaises(TypeError):
            PermissionOverwrite(target=123, allow=123)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            PermissionOverwrite(target=123, deny=123)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
