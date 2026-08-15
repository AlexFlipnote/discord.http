import unittest

from discord_http import Role, PartialRole, Colour


class FakeState:
    pass


class FakeGuild:
    id = 100


def _role_data(**overrides):
    data = {
        "id": "1", "name": "role", "hoist": False, "color": 0, "position": 1,
        "permissions": "0",
    }
    data.update(overrides)
    return data


class TestPartialRoleIsDefaultRole(unittest.TestCase):
    def test_true_when_id_matches_guild_id(self) -> None:
        role = PartialRole(state=FakeState(), id=100, guild_id=100)
        self.assertTrue(role.is_default_role())

    def test_false_otherwise(self) -> None:
        role = PartialRole(state=FakeState(), id=1, guild_id=100)
        self.assertFalse(role.is_default_role())


class TestRoleTagFlags(unittest.TestCase):
    """ These are derived from key PRESENCE in the tags dict, not the value -
    a role with `{"premium_subscriber": None}` (Discord's actual documented
    shape, the value is always null) must still count as a premium role. """

    def test_flags_true_when_keys_present_with_null_values(self) -> None:
        role = Role(state=FakeState(), guild=FakeGuild(), data=_role_data(tags={
            "premium_subscriber": None,
            "available_for_purchase": None,
            "guild_connections": None,
        }))
        self.assertTrue(role.is_premium_subscriber())
        self.assertTrue(role.is_available_for_purchase())
        self.assertTrue(role.is_guild_connection())

    def test_flags_false_when_tags_absent(self) -> None:
        role = Role(state=FakeState(), guild=FakeGuild(), data=_role_data())
        self.assertFalse(role.is_premium_subscriber())
        self.assertFalse(role.is_available_for_purchase())
        self.assertFalse(role.is_guild_connection())

    def test_bot_and_integration_managed(self) -> None:
        role = Role(state=FakeState(), guild=FakeGuild(), data=_role_data(bot_id="5"))
        self.assertTrue(role.is_bot_managed())
        self.assertFalse(role.is_integration())


class TestRoleIcon(unittest.TestCase):
    def test_display_icon_falls_back_to_unicode_emoji(self) -> None:
        role = Role(state=FakeState(), guild=FakeGuild(), data=_role_data(
            icon=None, unicode_emoji="wave"
        ))
        self.assertIsNone(role.icon)
        self.assertEqual(role.display_icon, "wave")

    def test_display_icon_prefers_custom_icon(self) -> None:
        role = Role(state=FakeState(), guild=FakeGuild(), data=_role_data(
            icon="abc123", unicode_emoji="wave"
        ))
        self.assertIsNotNone(role.icon)
        # Asset has no __eq__, so `icon` builds a fresh instance each access -
        # compare the url rather than object identity/equality.
        self.assertEqual(role.display_icon.url, role.icon.url)


class TestRoleEditValidation(unittest.IsolatedAsyncioTestCase):
    """ These validations run before any network call, so they're testable
    without mocking `_state.query`. """

    async def test_invalid_colour_type_raises_type_error(self) -> None:
        role = PartialRole(state=FakeState(), id=1, guild_id=100)
        with self.assertRaises(TypeError):
            await role.edit(colour="not-a-colour")  # type: ignore[arg-type]

    async def test_unicode_emoji_and_icon_together_raises_value_error(self) -> None:
        role = PartialRole(state=FakeState(), id=1, guild_id=100)
        with self.assertRaises(ValueError):
            await role.edit(unicode_emoji="wave", icon=b"data")


if __name__ == "__main__":
    unittest.main()
