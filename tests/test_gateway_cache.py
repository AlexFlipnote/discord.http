import unittest

from types import SimpleNamespace

from discord_http.gateway.cache import Cache
from discord_http.gateway.flags import GatewayCacheFlags


class FakeGuild:
    def __init__(self, id=1):
        self.id = id
        self.member_count = 10
        self._cache_members = {}
        self._cache_channels = {}
        self._cache_threads = {}
        self._cache_roles = {}
        self._cache_emojis = {}
        self._cache_stickers = {}
        self._cache_voice_states = {}
        self._updated_with = None
        self._channel_lookup = {}
        self._thread_lookup = {}

    def _update(self, data):
        self._updated_with = data

    def get_channel(self, channel_id):
        return self._channel_lookup.get(channel_id)

    def get_thread(self, channel_id):
        return self._thread_lookup.get(channel_id)

    def get_member(self, user_id):
        return self._cache_members.get(user_id)


class FakeClient:
    def __init__(self, cache_flags=None, bot_user_id=999):
        self._gateway_cache = cache_flags
        self.user = SimpleNamespace(id=bot_user_id)

    def get_partial_guild(self, guild_id):
        return SimpleNamespace(kind="partial_guild", id=guild_id)

    def get_partial_member(self, user_id, guild_id):
        return SimpleNamespace(kind="partial_member", id=user_id, guild_id=guild_id)

    def get_partial_channel(self, channel_id, *, guild_id=None):
        return SimpleNamespace(kind="partial_channel", id=channel_id, guild_id=guild_id)

    def get_partial_role(self, role_id, guild_id):
        return SimpleNamespace(kind="partial_role", id=role_id, guild_id=guild_id)

    def get_partial_emoji(self, emoji_id, *, guild_id=None):
        return SimpleNamespace(kind="partial_emoji", id=emoji_id, guild_id=guild_id)

    def get_partial_sticker(self, sticker_id, *, guild_id=None):
        return SimpleNamespace(kind="partial_sticker", id=sticker_id, guild_id=guild_id)

    def get_partial_voice_state(self, member_id, *, guild_id=None, channel_id=None):
        return SimpleNamespace(
            kind="partial_voice_state", id=member_id,
            guild_id=guild_id, channel_id=channel_id,
        )


def _cache_with_guild(cache_flags, guild=None):
    # Seeds the cache's private guild dict directly rather than going through
    # add_guild(), since add_guild() only stores a guild when the guilds/
    # partial_guilds flag is set - and most tests here exercise flags for
    # other resource types (members, channels, roles, ...) with a guild
    # that must still be resolvable via get_guild().
    bot = FakeClient(cache_flags=cache_flags)
    cache = Cache(client=bot)
    guild = guild or FakeGuild()
    cache._Cache__guilds[guild.id] = guild
    return cache, bot, guild


class TestAddGuild(unittest.TestCase):
    def test_none_cache_flags_stores_nothing(self) -> None:
        bot = FakeClient(cache_flags=None)
        cache = Cache(client=bot)
        result = cache.add_guild(1, FakeGuild())
        self.assertIsNone(result)
        self.assertIsNone(cache.get_guild(1))

    def test_guilds_flag_stores_full_guild(self) -> None:
        bot = FakeClient(cache_flags=GatewayCacheFlags.guilds)
        cache = Cache(client=bot)
        guild = FakeGuild()
        result = cache.add_guild(1, guild)
        self.assertIs(result, guild)
        self.assertIs(cache.get_guild(1), guild)

    def test_partial_guilds_flag_stores_partial_guild_instead(self) -> None:
        bot = FakeClient(cache_flags=GatewayCacheFlags.partial_guilds)
        cache = Cache(client=bot)
        cache.add_guild(1, FakeGuild())
        stored = cache.get_guild(1)
        self.assertEqual(stored.kind, "partial_guild")

    def test_no_relevant_flag_stores_nothing(self) -> None:
        bot = FakeClient(cache_flags=GatewayCacheFlags.members)
        cache = Cache(client=bot)
        result = cache.add_guild(1, FakeGuild())
        self.assertIsNone(result)
        self.assertIsNone(cache.get_guild(1))


class TestGetGuild(unittest.TestCase):
    def test_none_guild_id_returns_none(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.guilds))
        self.assertIsNone(cache.get_guild(None))

    def test_unknown_guild_id_returns_none(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.guilds))
        self.assertIsNone(cache.get_guild(999))


class TestUpdateGuild(unittest.TestCase):
    def test_none_cache_flags_is_noop(self) -> None:
        cache, _, guild = _cache_with_guild(None)
        cache.update_guild(guild.id, {"name": "x"})
        self.assertIsNone(guild._updated_with)

    def test_unknown_guild_is_noop(self) -> None:
        cache, _, _ = _cache_with_guild(GatewayCacheFlags.guilds)
        cache.update_guild(999, {"name": "x"})  # should not raise

    def test_guilds_flag_absent_does_not_update(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_guilds)
        cache.update_guild(guild.id, {"name": "x"})
        self.assertIsNone(guild._updated_with)

    def test_guilds_flag_present_updates(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.guilds)
        cache.update_guild(guild.id, {"name": "x"})
        self.assertEqual(guild._updated_with, {"name": "x"})


class TestRemoveGuild(unittest.TestCase):
    def test_none_cache_flags_returns_none(self) -> None:
        cache, _, guild = _cache_with_guild(None)
        self.assertIsNone(cache.remove_guild(guild.id))

    def test_removes_and_returns_the_guild(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.guilds)
        removed = cache.remove_guild(guild.id)
        self.assertIs(removed, guild)
        self.assertIsNone(cache.get_guild(guild.id))


class TestAddMember(unittest.TestCase):
    def test_none_cache_flags_is_noop(self) -> None:
        cache, _, guild = _cache_with_guild(None)
        member = SimpleNamespace(id=5, guild_id=guild.id)
        cache.add_member(member)
        self.assertEqual(guild._cache_members, {})

    def test_unknown_guild_is_noop(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.members))
        member = SimpleNamespace(id=5, guild_id=999)
        cache.add_member(member)  # should not raise

    def test_members_flag_stores_full_member_and_counts(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        member = SimpleNamespace(id=5, guild_id=guild.id)
        cache.add_member(member)
        self.assertIs(guild._cache_members[5], member)
        self.assertEqual(guild.member_count, 11)

    def test_count_member_false_does_not_increment(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        member = SimpleNamespace(id=5, guild_id=guild.id)
        cache.add_member(member, count_member=False)
        self.assertEqual(guild.member_count, 10)

    def test_partial_members_flag_stores_partial_instead(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_members)
        member = SimpleNamespace(id=5, guild_id=guild.id)
        cache.add_member(member)
        self.assertEqual(guild._cache_members[5].kind, "partial_member")

    def test_bot_own_member_is_always_cached_regardless_of_flags(self) -> None:
        cache, bot, guild = _cache_with_guild(GatewayCacheFlags.roles)  # unrelated flag
        member = SimpleNamespace(id=bot.user.id, guild_id=guild.id)
        cache.add_member(member)
        self.assertIs(guild._cache_members[bot.user.id], member)

    def test_non_bot_member_not_cached_without_relevant_flags(self) -> None:
        cache, bot, guild = _cache_with_guild(GatewayCacheFlags.roles)
        member = SimpleNamespace(id=bot.user.id + 1, guild_id=guild.id)
        cache.add_member(member)
        self.assertNotIn(bot.user.id + 1, guild._cache_members)


class TestUpdateMember(unittest.TestCase):
    def test_delegates_to_add_member_without_counting(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        member = SimpleNamespace(id=5, guild_id=guild.id, presence=None)
        cache.update_member(member)
        self.assertIs(guild._cache_members[5], member)
        self.assertEqual(guild.member_count, 10)

    def test_preserves_existing_presence_when_replacement_has_none(self) -> None:
        """ Regression test: GUILD_MEMBER_UPDATE never carries presence data, so the
        freshly built Member always has presence=None. Replacing the cached member
        wholesale used to silently drop whatever PRESENCE_UPDATE had already set. """
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        presence = SimpleNamespace(status="online")
        guild._cache_members[5] = SimpleNamespace(id=5, guild_id=guild.id, presence=presence)

        updated_member = SimpleNamespace(id=5, guild_id=guild.id, presence=None)
        cache.update_member(updated_member)

        self.assertIs(guild._cache_members[5], updated_member)
        self.assertIs(updated_member.presence, presence)

    def test_does_not_overwrite_presence_already_set_on_replacement(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        old_presence = SimpleNamespace(status="online")
        new_presence = SimpleNamespace(status="idle")
        guild._cache_members[5] = SimpleNamespace(id=5, guild_id=guild.id, presence=old_presence)

        updated_member = SimpleNamespace(id=5, guild_id=guild.id, presence=new_presence)
        cache.update_member(updated_member)

        self.assertIs(updated_member.presence, new_presence)


class TestRemoveMember(unittest.TestCase):
    def test_none_cache_flags_returns_none(self) -> None:
        cache, _, guild = _cache_with_guild(None)
        self.assertIsNone(cache.remove_member(guild.id, 5))

    def test_unknown_guild_returns_none(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.members))
        self.assertIsNone(cache.remove_member(999, 5))

    def test_decrements_member_count_and_pops(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        member = SimpleNamespace(id=5, guild_id=guild.id)
        cache.add_member(member)
        removed = cache.remove_member(guild.id, 5)
        self.assertIs(removed, member)
        self.assertEqual(guild.member_count, 10)
        self.assertNotIn(5, guild._cache_members)

    def test_missing_member_returns_none(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.members)
        self.assertIsNone(cache.remove_member(guild.id, 999))


class TestUpdatePresence(unittest.TestCase):
    def test_none_cache_flags_is_noop(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=None))
        cache.update_presence(None)  # should not raise

    def test_missing_presences_flag_is_noop(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.guilds)
        presence = SimpleNamespace(guild=SimpleNamespace(id=guild.id), user=SimpleNamespace(id=5))
        cache.update_presence(presence)  # should not raise, no member touched

    def test_unknown_guild_is_noop(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.presences))
        presence = SimpleNamespace(guild=SimpleNamespace(id=999), user=SimpleNamespace(id=5))
        cache.update_presence(presence)  # should not raise

    def test_updates_cached_member_presence(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.presences)
        calls = []
        member = SimpleNamespace(id=5, _update_presence=lambda p: calls.append(p))
        guild._cache_members[5] = member
        presence = SimpleNamespace(guild=SimpleNamespace(id=guild.id), user=SimpleNamespace(id=5))
        cache.update_presence(presence)
        self.assertEqual(calls, [presence])

    def test_member_not_cached_is_noop(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.presences)
        presence = SimpleNamespace(guild=SimpleNamespace(id=guild.id), user=SimpleNamespace(id=999))
        cache.update_presence(presence)  # should not raise


class TestGetChannel(unittest.TestCase):
    def test_unknown_guild_returns_none(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.channels))
        self.assertIsNone(cache.get_channel(999, 1))

    def test_delegates_to_guild_get_channel(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.channels)
        guild._channel_lookup[1] = "the-channel"
        self.assertEqual(cache.get_channel(guild.id, 1), "the-channel")


class TestGetChannelThread(unittest.TestCase):
    """ Precedence: a match from get_thread() always wins over get_channel(),
    even if both return something for the same ID. """

    def test_unknown_guild_returns_none(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.channels))
        self.assertIsNone(cache.get_channel_thread(999, 1))

    def test_neither_found_returns_none(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.channels)
        self.assertIsNone(cache.get_channel_thread(guild.id, 1))

    def test_only_channel_found(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.channels)
        guild._channel_lookup[1] = "the-channel"
        self.assertEqual(cache.get_channel_thread(guild.id, 1), "the-channel")

    def test_thread_takes_precedence_over_channel(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.channels)
        guild._channel_lookup[1] = "the-channel"
        guild._thread_lookup[1] = "the-thread"
        self.assertEqual(cache.get_channel_thread(guild.id, 1), "the-thread")


class TestAddRemoveChannel(unittest.TestCase):
    def test_none_cache_flags_is_noop(self) -> None:
        cache, _, guild = _cache_with_guild(None)
        channel = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_channel(channel)
        self.assertEqual(guild._cache_channels, {})

    def test_no_guild_id_is_noop(self) -> None:
        cache, _, _ = _cache_with_guild(GatewayCacheFlags.channels)
        channel = SimpleNamespace(id=1, guild_id=None)
        cache.add_channel(channel)  # should not raise

    def test_channels_flag_stores_full_channel(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.channels)
        channel = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_channel(channel)
        self.assertIs(guild._cache_channels[1], channel)

    def test_partial_channels_flag_stores_partial_instead(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_channels)
        channel = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_channel(channel)
        self.assertEqual(guild._cache_channels[1].kind, "partial_channel")

    def test_remove_channel_pops_from_cache(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.channels)
        channel = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_channel(channel)
        cache.remove_channel(channel)
        self.assertNotIn(1, guild._cache_channels)


class TestAddRemoveThread(unittest.TestCase):
    def test_threads_flag_stores_full_thread(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.threads)
        thread = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_thread(thread)
        self.assertIs(guild._cache_threads[1], thread)

    def test_partial_threads_flag_stores_partial_instead(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_threads)
        thread = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_thread(thread)
        self.assertEqual(guild._cache_threads[1].kind, "partial_channel")

    def test_remove_thread_pops_from_cache(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.threads)
        thread = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_thread(thread)
        cache.remove_thread(thread)
        self.assertNotIn(1, guild._cache_threads)


class TestAddRemoveRole(unittest.TestCase):
    def test_roles_flag_stores_full_role(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.roles)
        role = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_role(role)
        self.assertIs(guild._cache_roles[1], role)

    def test_partial_roles_flag_stores_partial_instead(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_roles)
        role = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_role(role)
        self.assertEqual(guild._cache_roles[1].kind, "partial_role")

    def test_remove_role_pops_from_cache(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.roles)
        role = SimpleNamespace(id=1, guild_id=guild.id)
        cache.add_role(role)
        cache.remove_role(role)
        self.assertNotIn(1, guild._cache_roles)


class TestUpdateEmojis(unittest.TestCase):
    def test_emojis_flag_stores_full_objects(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.emojis)
        emoji = SimpleNamespace(id=1)
        cache.update_emojis(guild.id, [emoji])
        self.assertIs(guild._cache_emojis[1], emoji)

    def test_partial_emojis_flag_stores_partials(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_emojis)
        emoji = SimpleNamespace(id=1)
        cache.update_emojis(guild.id, [emoji])
        self.assertEqual(guild._cache_emojis[1].kind, "partial_emoji")

    def test_unknown_guild_is_noop(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.emojis))
        cache.update_emojis(999, [SimpleNamespace(id=1)])  # should not raise


class TestUpdateStickers(unittest.TestCase):
    def test_stickers_flag_stores_full_objects(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.stickers)
        sticker = SimpleNamespace(id=1)
        cache.update_stickers(guild.id, [sticker])
        self.assertIs(guild._cache_stickers[1], sticker)

    def test_partial_stickers_flag_stores_partials(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_stickers)
        sticker = SimpleNamespace(id=1)
        cache.update_stickers(guild.id, [sticker])
        self.assertEqual(guild._cache_stickers[1].kind, "partial_sticker")


class TestUpdateVoiceState(unittest.TestCase):
    def test_none_cache_flags_is_noop(self) -> None:
        cache, _, guild = _cache_with_guild(None)
        vs = SimpleNamespace(id=5, guild_id=guild.id, channel_id=10)
        cache.update_voice_state(vs)
        self.assertEqual(guild._cache_voice_states, {})

    def test_no_guild_id_is_noop(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.voice_states))
        vs = SimpleNamespace(id=5, guild_id=None, channel_id=10)
        cache.update_voice_state(vs)  # should not raise

    def test_unknown_guild_is_noop(self) -> None:
        cache = Cache(client=FakeClient(cache_flags=GatewayCacheFlags.voice_states))
        vs = SimpleNamespace(id=5, guild_id=999, channel_id=10)
        cache.update_voice_state(vs)  # should not raise

    def test_voice_states_flag_caches_full_state_when_channel_present(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.voice_states)
        vs = SimpleNamespace(id=5, guild_id=guild.id, channel_id=10)
        cache.update_voice_state(vs)
        self.assertIs(guild._cache_voice_states[5], vs)

    def test_channel_id_none_removes_from_cache(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.voice_states)
        vs = SimpleNamespace(id=5, guild_id=guild.id, channel_id=10)
        cache.update_voice_state(vs)
        left = SimpleNamespace(id=5, guild_id=guild.id, channel_id=None)
        cache.update_voice_state(left)
        self.assertNotIn(5, guild._cache_voice_states)

    def test_partial_voice_states_flag_caches_partial_instead(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_voice_states)
        vs = SimpleNamespace(id=5, guild_id=guild.id, channel_id=10)
        cache.update_voice_state(vs)
        self.assertEqual(guild._cache_voice_states[5].kind, "partial_voice_state")

    def test_partial_voice_state_with_no_channel_is_removed(self) -> None:
        cache, _, guild = _cache_with_guild(GatewayCacheFlags.partial_voice_states)
        vs = SimpleNamespace(id=5, guild_id=guild.id, channel_id=None)
        guild._cache_voice_states[5] = "stale"
        cache.update_voice_state(vs)
        self.assertNotIn(5, guild._cache_voice_states)


if __name__ == "__main__":
    unittest.main()
