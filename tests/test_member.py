import unittest

from datetime import timedelta

from discord_http import Guild, Role, Member, Permissions, VoiceState, utils

from _fake_client import FakeBot


class FakeCache:
    def __init__(self):
        self.guild = None

    def get_guild(self, guild_id):
        return self.guild

    def intern_role_ids(self, guild_id, raw_role_ids):
        return tuple(int(r) for r in raw_role_ids)

    def intern_features(self, raw_features):
        return tuple(raw_features or ())


class FakeState:
    def __init__(self):
        self.cache = FakeCache()
        self.bot = FakeBot(self)


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


class TestJoinedAt(unittest.TestCase):
    def test_parsed_to_aware_datetime(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        ts = "2021-05-06T07:08:09.123456+00:00"
        member = _make_member(state, guild, joined_at=ts)

        # Packed as epoch milliseconds, so sub-millisecond precision is dropped
        self.assertEqual(member.joined_at, utils.parse_time("2021-05-06T07:08:09.123+00:00"))
        self.assertIsNotNone(member.joined_at.tzinfo)

    def test_missing_is_none(self) -> None:
        state = FakeState()
        member = _make_member(state, _make_guild(state))
        self.assertIsNone(member.joined_at)

    def test_setter(self) -> None:
        state = FakeState()
        member = _make_member(state, _make_guild(state))
        when = utils.parse_time("2020-01-01T00:00:00+00:00")
        member.joined_at = when
        self.assertEqual(member.joined_at, when)
        member.joined_at = None
        self.assertIsNone(member.joined_at)

    def test_setter_leaves_other_timestamps(self) -> None:
        state = FakeState()
        member = _make_member(
            state, _make_guild(state),
            joined_at="2020-01-01T00:00:00+00:00",
            premium_since="2021-01-01T00:00:00+00:00",
            communication_disabled_until="2022-01-01T00:00:00+00:00",
        )
        member.joined_at = None

        self.assertIsNone(member.joined_at)
        self.assertEqual(member.premium_since, utils.parse_time("2021-01-01T00:00:00+00:00"))
        self.assertEqual(member.communication_disabled_until, utils.parse_time("2022-01-01T00:00:00+00:00"))

    def test_other_timestamps_missing_are_none(self) -> None:
        state = FakeState()
        member = _make_member(state, _make_guild(state), joined_at="2020-01-01T00:00:00+00:00")
        self.assertIsNone(member.premium_since)
        self.assertIsNone(member.communication_disabled_until)


class TestTimeout(unittest.TestCase):
    def test_is_timed_out(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        future = utils.add_to_datetime(timedelta(hours=1)).isoformat()
        past = (utils.utcnow() - timedelta(hours=1)).isoformat()

        self.assertTrue(_make_member(state, guild, communication_disabled_until=future).is_timed_out())
        self.assertFalse(_make_member(state, guild, communication_disabled_until=past).is_timed_out())
        self.assertFalse(_make_member(state, guild).is_timed_out())

    def test_timeout_keeps_only_view_and_history(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, 5, ["view_channel", "send_messages", "read_message_history"])
        member = _make_member(
            state, guild, role_ids=[5],
            communication_disabled_until=utils.add_to_datetime(timedelta(hours=1)).isoformat(),
        )
        self.assertEqual(
            sorted(member.guild_permissions.to_names()),
            ["read_message_history", "view_channel"],
        )


class TestResolvedPermissionsStorage(unittest.TestCase):
    def test_raw_permissions_parsed(self) -> None:
        state = FakeState()
        member = _make_member(state, _make_guild(state), permissions="8")
        self.assertEqual(member._raw_permissions, 8)
        self.assertEqual(member.resolved_permissions, Permissions.administrator)

    def test_no_permissions_no_extra(self) -> None:
        state = FakeState()
        member = _make_member(state, _make_guild(state))
        self.assertIsNone(member._extra)
        self.assertIsNone(member._raw_permissions)
        self.assertEqual(member.resolved_permissions, Permissions.none())


class TestMemberExtras(unittest.TestCase):
    def test_guild_nameplate_and_style(self) -> None:
        state = FakeState()
        member = _make_member(
            state, _make_guild(state),
            collectibles={"nameplate": {"sku_id": "1", "label": "L", "palette": "p", "asset": "a/"}},
            display_name_styles={"colors": [5], "font_id": 3, "effect_id": 2},
            avatar_decoration_data={"asset": "deco", "sku_id": "9"},
        )
        self.assertEqual(member.nameplate.label, "L")
        self.assertEqual(member.name_style.to_dict()["colors"], [5])
        self.assertEqual(member.avatar_decoration.sku_id, 9)


class TestTopRole(unittest.TestCase):
    def test_highest_position_of_member_roles(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        low = _make_role(state, guild, 5)
        high = _make_role(state, guild, 6)
        other = _make_role(state, guild, 7)
        low.position, high.position, other.position = 1, 3, 10

        member = _make_member(state, guild, role_ids=[5, 6, 999])
        self.assertIs(guild.get_member_top_role(member), high)
        self.assertIsNone(guild.get_member_top_role(_make_member(state, guild)))


class _VoiceCache(FakeCache):
    def get_user(self, user_id):
        return None


class _VoiceState(FakeState):
    def __init__(self):
        self.cache = _VoiceCache()
        self.bot = FakeBot(self)


def _voice_data(**overrides):
    data = {
        "user_id": "1", "guild_id": "100", "session_id": "s", "channel_id": "9",
        "deaf": True, "mute": False, "self_deaf": False, "self_mute": True,
        "self_video": False, "suppress": True,
    }
    data.update(overrides)
    return data


class TestVoiceState(unittest.TestCase):
    def test_bools(self) -> None:
        state = _VoiceState()
        _make_guild(state)
        vs = VoiceState(state=state, data=_voice_data(self_stream=True))
        self.assertEqual(
            (vs.deaf, vs.mute, vs.self_deaf, vs.self_mute, vs.self_stream, vs.self_video, vs.suppress),
            (True, False, False, True, True, False, True),
        )
        vs.mute = True
        vs.deaf = False
        self.assertTrue(vs.mute)
        self.assertFalse(vs.deaf)

    def test_member_built_from_payload_when_not_cached(self) -> None:
        state = _VoiceState()
        _make_guild(state)
        vs = VoiceState(state=state, data=_voice_data(member={
            "user": {"id": "1", "username": "u", "discriminator": "0"},
            "roles": [], "flags": 0,
        }))
        self.assertIsInstance(vs._member_data, Member)
        self.assertEqual(vs.member.id, 1)

    def test_prefers_cached_member(self) -> None:
        state = _VoiceState()
        guild = _make_guild(state)
        cached = _make_member(state, guild, member_id=1)
        guild._cache_members[1] = cached

        vs = VoiceState(state=state, data=_voice_data(member={
            "user": {"id": "1", "username": "u", "discriminator": "0"},
            "roles": [], "flags": 0,
        }))
        self.assertIsNone(vs._member_data)  # nothing extra held when already cached
        self.assertIs(vs.member, cached)

    def test_no_member_payload(self) -> None:
        state = _VoiceState()
        _make_guild(state)
        self.assertIsNone(VoiceState(state=state, data=_voice_data()).member)


if __name__ == "__main__":
    unittest.main()
