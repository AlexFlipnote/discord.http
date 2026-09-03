import unittest

from datetime import timedelta

from discord_http import (
    Guild, Role, Member, PartialChannel, TextChannel, VoiceChannel,
    CategoryChannel, ForumTag, Permissions, PermissionOverwrite, PermissionType,
    utils,
)


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


def _make_channel(state, guild, channel_id=200):
    channel = TextChannel(state=state, data={
        "id": str(channel_id), "type": 0, "guild_id": str(guild.id),
    })
    return channel


class TestPartialChannelPermissionsFor(unittest.TestCase):
    def test_always_returns_none(self) -> None:
        channel = PartialChannel(state=FakeState(), id=1)
        self.assertEqual(channel.permissions_for(object()), Permissions.none())  # type: ignore[arg-type]


class TestBaseChannelPermissionsFor(unittest.TestCase):
    def test_owner_always_has_all_permissions(self) -> None:
        state = FakeState()
        guild = _make_guild(state, owner_id=1)
        _make_role(state, guild, guild.id)  # @everyone role required for default_role
        channel = _make_channel(state, guild)
        member = _make_member(state, guild, member_id=1)

        self.assertEqual(channel.permissions_for(member), Permissions.all())

    def test_everyone_role_provides_the_base(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, guild.id, ["view_channel"])
        channel = _make_channel(state, guild)
        member = _make_member(state, guild)

        self.assertIn("view_channel", channel.permissions_for(member).to_names())

    def test_administrator_role_grants_everything(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, guild.id)
        _make_role(state, guild, 5, ["administrator"])
        channel = _make_channel(state, guild)
        member = _make_member(state, guild, role_ids=[5])

        self.assertEqual(channel.permissions_for(member), Permissions.all())

    def test_overwrite_precedence_everyone_then_roles_then_member(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, guild.id, ["view_channel", "send_messages"])
        _make_role(state, guild, 5)
        channel = _make_channel(state, guild)
        member = _make_member(state, guild, role_ids=[5])

        # @everyone overwrite denies send_messages...
        everyone_ow = PermissionOverwrite(
            target=guild.id,
            deny=Permissions.from_names("send_messages"),
            target_type=PermissionType.role,
        )
        # ...but the member's role overwrite explicitly allows it back
        role_ow = PermissionOverwrite(
            target=5,
            allow=Permissions.from_names("send_messages"),
            target_type=PermissionType.role,
        )
        # ...and a member-specific overwrite denies view_channel, overriding everything above
        member_ow = PermissionOverwrite(
            target=member.id,
            deny=Permissions.from_names("view_channel"),
            target_type=PermissionType.member,
        )
        # `_permission_overwrites` isn't cached anymore (rebuilt fresh from
        # `_raw_overwrites` on every access), so inject fixtures at that level.
        channel._raw_overwrites = tuple(
            (int(ow.target), int(ow.target_type), int(ow.allow), int(ow.deny))
            for ow in (everyone_ow, role_ow, member_ow)
        )

        perms = channel.permissions_for(member)
        self.assertIn("send_messages", perms.to_names())
        self.assertNotIn("view_channel", perms.to_names())

    def test_timeout_does_not_grant_permissions_never_held(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        _make_role(state, guild, guild.id)  # no view_channel/read_message_history
        channel = _make_channel(state, guild)
        member = _make_member(
            state, guild,
            communication_disabled_until=utils.add_to_datetime(timedelta(hours=1)).isoformat(),
        )

        perms = channel.permissions_for(member)
        self.assertNotIn("view_channel", perms.to_names())
        self.assertNotIn("read_message_history", perms.to_names())


class TestForumTag(unittest.TestCase):
    def test_create_defaults_name(self) -> None:
        tag = ForumTag.create()
        self.assertEqual(tag.name, "New Tag")

    def test_create_rejects_both_emoji_id_and_name(self) -> None:
        with self.assertRaises(ValueError):
            ForumTag.create(emoji_id=1, emoji_name="wave")

    def test_to_dict_omits_falsy_optional_fields(self) -> None:
        tag = ForumTag.create(name="bugs")
        payload = tag.to_dict()
        self.assertNotIn("id", payload)
        self.assertNotIn("emoji_id", payload)
        self.assertNotIn("emoji_name", payload)

    def test_from_data_requires_name(self) -> None:
        tag = ForumTag(data={"id": "5", "name": "bugs", "moderated": True})
        self.assertEqual(tag.id, 5)
        self.assertTrue(tag.moderated)


class TestCategoryChannelSort(unittest.TestCase):
    def test_text_channels_always_sort_before_voice_regardless_of_position(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        category = CategoryChannel(state=state, data={
            "id": "1", "type": 4, "guild_id": str(guild.id),
        })

        voice = VoiceChannel(state=state, data={
            "id": "2", "type": 2, "guild_id": str(guild.id),
            "parent_id": "1", "position": 0, "bitrate": 64000, "user_limit": 0,
        })
        text = TextChannel(state=state, data={
            "id": "3", "type": 0, "guild_id": str(guild.id),
            "parent_id": "1", "position": 5,
        })
        guild._cache_channels = {2: voice, 3: text}

        ordered = category.channels
        self.assertEqual([c.id for c in ordered], [3, 2])


class TestVoiceChannelSetStatusValidation(unittest.IsolatedAsyncioTestCase):
    async def test_status_over_500_chars_raises(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        voice = VoiceChannel(state=state, data={
            "id": "2", "type": 2, "guild_id": str(guild.id),
            "bitrate": 64000, "user_limit": 0,
        })
        with self.assertRaises(ValueError):
            await voice.set_voice_status("x" * 501)


class TestCreateThreadValidation(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_auto_archive_duration_raises(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        channel = _make_channel(state, guild)
        with self.assertRaises(ValueError):
            await channel.create_thread("thread", auto_archive_duration=123)

    async def test_rate_limit_per_user_out_of_range_raises(self) -> None:
        state = FakeState()
        guild = _make_guild(state)
        channel = _make_channel(state, guild)
        with self.assertRaises(ValueError):
            await channel.create_thread("thread", rate_limit_per_user=99999)

    async def test_rate_limit_per_user_accepts_timedelta(self) -> None:
        # Validation only - this should get past the ValueError checks and
        # fail on the network call instead, proving the timedelta conversion worked.
        state = FakeState()
        guild = _make_guild(state)
        channel = _make_channel(state, guild)
        with self.assertRaises(AttributeError):
            # FakeState has no `query`, so this proves validation passed
            # and execution reached the actual HTTP call.
            await channel.create_thread("thread", rate_limit_per_user=timedelta(seconds=30))


if __name__ == "__main__":
    unittest.main()
