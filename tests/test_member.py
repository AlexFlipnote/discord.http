import unittest

from datetime import timedelta

from discord_http import Guild, Role, Member, Permissions, utils


class FakeCache:
    def __init__(self):
        self.guild = None

    def get_guild(self, guild_id):
        return self.guild


class FakeState:
    def __init__(self):
        self.cache = FakeCache()


def _make_guild(state, owner_id=None):
    guild = Guild(state=state, data={"id": "100", "name": "g", "features": []})
    guild.owner_id = owner_id
    state.cache.guild = guild
    return guild


def _make_role(state, guild, role_id, permission_names=()):
    role = Role(state=state, guild=guild, data={
        "id": str(role_id), "name": f"role{role_id}", "hoist": False, "color": 0,
        "position": 1,
        "permissions": str(int(Permissions.from_names(*permission_names))) if permission_names else "0",
    })
    guild._cache_roles[role_id] = role
    return role


def _make_member(state, guild, member_id=1, role_ids=(), **overrides):
    data = {
        "user": {"id": str(member_id), "username": "u", "discriminator": "0001", "avatar": None},
        "roles": [str(r) for r in role_ids],
        "flags": 0,
    }
    data.update(overrides)
    return Member(state=state, guild=guild, data=data)


class TestGuildPermissionsOwner(unittest.TestCase):
    def test_owner_always_has_all_permissions(self) -> None:
        state = FakeState()
        guild = _make_guild(state, owner_id=1)
        member = _make_member(state, guild, member_id=1)
        self.assertEqual(member.guild_permissions, Permissions.all())


class TestGuildPermissionsRoles(unittest.TestCase):
    def test_permissions_are_the_union_of_all_roles(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5, ["send_messages"])
        _make_role(state, guild, 6, ["embed_links"])
        member = _make_member(state, guild, role_ids=[5, 6])

        self.assertIn("send_messages", member.guild_permissions.to_names())
        self.assertIn("embed_links", member.guild_permissions.to_names())

    def test_administrator_role_grants_everything(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5, ["administrator"])
        member = _make_member(state, guild, role_ids=[5])

        self.assertEqual(member.guild_permissions, Permissions.all())

    def test_roles_not_in_guild_cache_are_ignored(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(state, guild, role_ids=[999])
        self.assertEqual(member.guild_permissions, Permissions.none())


class TestGuildPermissionsTimeout(unittest.TestCase):
    """ Regression coverage for the "strip, never grant" timeout logic:
    a timed-out member keeps view_channel/read_message_history only if they
    already had them from their roles - timeout never adds permissions they
    didn't already have. """

    def test_timeout_strips_down_to_view_and_history_when_present(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5, [
            "send_messages", "view_channel", "read_message_history"
        ])
        member = _make_member(
            state, guild, role_ids=[5],
            communication_disabled_until=utils.add_to_datetime(timedelta(hours=1)).isoformat(),
        )

        perms = member.guild_permissions
        self.assertIn("view_channel", perms.to_names())
        self.assertIn("read_message_history", perms.to_names())
        self.assertNotIn("send_messages", perms.to_names())

    def test_timeout_does_not_grant_view_channel_if_never_had_it(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5, ["send_messages"])  # no view_channel
        member = _make_member(
            state, guild, role_ids=[5],
            communication_disabled_until=utils.add_to_datetime(timedelta(hours=1)).isoformat(),
        )

        perms = member.guild_permissions
        self.assertNotIn("view_channel", perms.to_names())
        self.assertNotIn("read_message_history", perms.to_names())

    def test_expired_timeout_is_not_timed_out(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(
            state, guild,
            communication_disabled_until=utils.add_to_datetime(timedelta(hours=-1)).isoformat(),
        )
        self.assertFalse(member.is_timed_out())

    def test_no_timeout_field_is_not_timed_out(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(state, guild)
        self.assertFalse(member.is_timed_out())


class TestGetRole(unittest.TestCase):
    def test_returns_none_if_role_id_not_assigned(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5)
        member = _make_member(state, guild, role_ids=[])
        self.assertIsNone(member.get_role(5))

    def test_returns_role_when_assigned_and_cached(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5)
        member = _make_member(state, guild, role_ids=[5])
        self.assertEqual(member.get_role(5).id, 5)


class TestHasPermissionsFromInteraction(unittest.TestCase):
    """ has_permissions() reads Member._raw_permissions, which is ONLY ever
    populated from an interaction payload's own `permissions` field - a
    member built via Member.fetch() (no such field) always resolves to
    Permissions.none() and therefore always fails has_permissions(). """

    def test_true_when_resolved_permissions_include_it(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(
            state, guild,
            permissions=str(int(Permissions.from_names("send_messages"))),
        )
        self.assertTrue(member.has_permissions("send_messages"))

    def test_administrator_resolved_permission_bypasses_everything(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(
            state, guild,
            permissions=str(int(Permissions.from_names("administrator"))),
        )
        self.assertTrue(member.has_permissions("ban_members"))

    def test_false_without_a_resolved_permissions_field(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(state, guild)
        self.assertFalse(member.has_permissions("send_messages"))


class TestDisplayName(unittest.TestCase):
    def test_nick_takes_priority(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(state, guild, nick="Nicky")
        self.assertEqual(member.display_name, "Nicky")

    def test_falls_back_to_username_without_nick(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        member = _make_member(state, guild)
        self.assertEqual(member.display_name, "u")


if __name__ == "__main__":
    unittest.main()
