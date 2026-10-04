import asyncio
import gc
import unittest

from types import SimpleNamespace

from discord_http.gateway.activity import Activity
from discord_http.gateway.cache import Cache
from discord_http.channel import StageChannel
from discord_http.gateway.enums import StatusType
from discord_http.gateway.flags import GatewayCacheFlags
from discord_http.gateway.object import ChannelInfo, Presence, Reaction
from discord_http.gateway.parser import Parser, GuildMembersChunk
from discord_http.guild import Guild, PartialGuild
from discord_http.member import Member, PartialMember

from _fake_client import FakeBot as _FakeBotBase


class FakeState:
    def __init__(self, bot):
        self.bot = bot
        self.cache = None


class FakeBot(_FakeBotBase):
    """ A FakeBot backed by a real `Cache`, with configurable listeners. """

    def __init__(self, cache_flags=None, listeners=(), bot_user_id=999):
        self.state = FakeState(self)
        self.application = None
        self._gateway_cache = cache_flags
        self.user = SimpleNamespace(id=bot_user_id)
        self.listeners = set(listeners)
        self.loop = None
        self.cache = Cache(client=self)
        self.state.cache = self.cache

    def has_any_dispatch(self, event_name):
        return event_name in self.listeners


def _cached_partial_guild(bot, guild_id=1):
    guild = PartialGuild(state=bot.state, id=guild_id)
    bot.cache._Cache__guilds[guild_id] = guild
    return guild


def _presence_data(user_id=5, guild_id=1, **overrides):
    data = {
        "user": {"id": str(user_id)},
        "guild_id": str(guild_id),
        "status": "online",
        "activities": [],
        "client_status": {"desktop": "online"},
    }
    data.update(overrides)
    return data


# An activity payload that blows up if anything tries to build it
_BROKEN_ACTIVITIES = [{"this": "is not an activity"}]


class TestPresenceObject(unittest.TestCase):
    def test_stores_ids_and_resolves_lazily(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.partial_guilds | GatewayCacheFlags.partial_members)
        guild = _cached_partial_guild(bot)
        member = PartialMember(state=bot.state, id=5, guild_id=1)
        guild._cache_members[5] = member

        presence = Presence(state=bot.state, data=_presence_data())
        self.assertEqual(presence.user_id, 5)
        self.assertEqual(presence.guild_id, 1)
        self.assertIs(presence.guild, guild)
        self.assertIs(presence.user, member)
        self.assertEqual(presence.desktop, StatusType.online)
        self.assertEqual(presence.activities, [])

    def test_falls_back_to_partial_member(self) -> None:
        bot = FakeBot()
        presence = Presence(state=bot.state, data=_presence_data())
        self.assertIsInstance(presence.user, PartialMember)
        self.assertEqual(presence.user.id, 5)
        self.assertIsInstance(presence.guild, PartialGuild)

    def test_does_not_keep_member_alive(self) -> None:
        """ Presence used to hold a strong ref to the member it was built for, so a
        presence copied onto a newer Member kept the old one alive and stale. """
        bot = FakeBot(cache_flags=GatewayCacheFlags.partial_guilds | GatewayCacheFlags.partial_members)
        guild = _cached_partial_guild(bot)
        old = PartialMember(state=bot.state, id=5, guild_id=1)
        guild._cache_members[5] = old
        presence = Presence(state=bot.state, data=_presence_data())
        old.presence = presence

        new = PartialMember(state=bot.state, id=5, guild_id=1)
        new.presence = presence
        guild._cache_members[5] = new

        self.assertFalse(any(r is old for r in gc.get_referents(presence)))
        self.assertIs(presence.user, new)


class TestActivityLazyFields(unittest.TestCase):
    def test_timestamps_and_created_at_are_lazy(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.presences)
        activity = Activity(state=bot.state, data={
            "type": 0, "name": "Some Game", "created_at": 1_700_000_000_000,
            "timestamps": {"start": 1_700_000_000_000},
        })
        self.assertEqual(activity.created_at.year, 2023)
        self.assertEqual(activity.timestamps.start.year, 2023)
        self.assertIsNone(activity.timestamps.end)
        self.assertEqual(activity.buttons, [])

    def test_name_is_interned_when_caching_presences(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.presences)
        name_a = "".join(["Spot", "ify-test"])
        name_b = "".join(["Spoti", "fy-test"])
        self.assertIsNot(name_a, name_b)
        a = Activity(state=bot.state, data={"type": 2, "name": name_a, "created_at": 1})
        b = Activity(state=bot.state, data={"type": 2, "name": name_b, "created_at": 1})
        self.assertIs(a.name, b.name)


class TestPresenceUpdate(unittest.TestCase):
    def test_no_listener_and_uncached_guild_skips_building(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.presences)
        parser = Parser(bot=bot)
        (result,) = parser.presence_update(_presence_data(activities=_BROKEN_ACTIVITIES))
        self.assertIsNone(result)

    def test_no_listener_and_uncached_member_skips_building(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.presences | GatewayCacheFlags.partial_guilds)
        _cached_partial_guild(bot)
        parser = Parser(bot=bot)
        (result,) = parser.presence_update(_presence_data(activities=_BROKEN_ACTIVITIES))
        self.assertIsNone(result)

    def test_no_listener_attaches_presence_to_cached_member(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.presences | GatewayCacheFlags.partial_guilds)
        guild = _cached_partial_guild(bot)
        member = PartialMember(state=bot.state, id=5, guild_id=1)
        guild._cache_members[5] = member
        parser = Parser(bot=bot)
        parser.presence_update(_presence_data())
        self.assertIsNotNone(member.presence)
        self.assertEqual(member.presence.status, StatusType.online)

    def test_listener_gets_presence_even_without_cache(self) -> None:
        bot = FakeBot(listeners={"presence_update"})
        parser = Parser(bot=bot)
        (result,) = parser.presence_update(_presence_data())
        self.assertIsInstance(result, Presence)
        self.assertEqual(result.user.id, 5)


class TestUpdateMemberPartialPresence(unittest.TestCase):
    def test_partial_members_keep_presence_across_member_update(self) -> None:
        bot = FakeBot(cache_flags=(
            GatewayCacheFlags.partial_guilds |
            GatewayCacheFlags.partial_members |
            GatewayCacheFlags.presences
        ))
        guild = _cached_partial_guild(bot)
        cached = PartialMember(state=bot.state, id=5, guild_id=1)
        guild._cache_members[5] = cached
        Parser(bot=bot).presence_update(_presence_data())
        presence = cached.presence
        self.assertIsNotNone(presence)

        updated = PartialMember(state=bot.state, id=5, guild_id=1)
        bot.cache.update_member(updated)
        self.assertIs(guild._cache_members[5].presence, presence)
        self.assertIs(updated.presence, presence)


class TestGuildMembersChunkPartial(unittest.IsolatedAsyncioTestCase):
    async def test_cache_only_request_builds_partial_members_from_ids(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.partial_guilds | GatewayCacheFlags.partial_members)
        bot.loop = asyncio.get_running_loop()
        guild = _cached_partial_guild(bot)
        parser = Parser(bot=bot)

        req = GuildMembersChunk(state=bot.state, guild_id=1, cache=True, collect=False)
        parser._chunk_requests[req.nonce] = req
        future = req.get_future()

        # Deliberately not full member payloads: building a Member would fail
        parser.guild_members_chunk({
            "guild_id": "1", "nonce": req.nonce,
            "chunk_index": 0, "chunk_count": 1,
            "members": [{"user": {"id": "5"}}, {"user": {"id": "6"}}],
            "presences": [_presence_data(user_id=5)],
        })

        self.assertEqual(set(guild._cache_members), {5, 6})
        self.assertIs(type(guild._cache_members[5]), PartialMember)
        self.assertIsNotNone(guild._cache_members[5].presence)
        self.assertIsNone(guild._cache_members[6].presence)
        self.assertTrue(future.done())
        self.assertEqual(future.result(), [])
        self.assertNotIn(req.nonce, parser._chunk_requests)

    async def test_no_request_and_no_listener_builds_nothing(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.members)
        parser = Parser(bot=bot)
        (result,) = parser.guild_members_chunk({
            "guild_id": "1", "nonce": "unknown",
            "members": [{"user": {"id": "5"}}],
        })
        self.assertIsNone(result)


def _guild_data(guild_id=1, **overrides):
    data = {
        "id": str(guild_id), "name": "g", "features": [], "member_count": 3,
        "roles": [{
            "id": str(guild_id), "name": "@everyone", "color": 0, "hoist": False,
            "position": 0, "permissions": "0", "managed": False, "mentionable": False,
        }],
        "emojis": [], "stickers": [],
    }
    data.update(overrides)
    return data


class TestGuildCreate(unittest.TestCase):
    def test_uncached_guild_without_listener_skips_roles(self) -> None:
        bot = FakeBot(cache_flags=None)
        (guild,) = Parser(bot=bot).guild_create(_guild_data())
        self.assertIsInstance(guild, Guild)
        self.assertEqual(guild.member_count, 3)
        self.assertEqual(guild.roles, [])

    def test_uncached_guild_with_listener_populates_roles(self) -> None:
        bot = FakeBot(cache_flags=None, listeners={"guild_create"})
        (guild,) = Parser(bot=bot).guild_create(_guild_data())
        self.assertEqual(len(guild.roles), 1)

    def test_guild_available_listener_populates_roles(self) -> None:
        bot = FakeBot(cache_flags=None, listeners={"guild_available"})
        (guild,) = Parser(bot=bot).guild_available(_guild_data())
        self.assertIsInstance(guild, Guild)
        self.assertEqual(len(guild.roles), 1)

    def test_partial_guilds_stores_the_same_partial_guild(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.partial_guilds)
        (guild,) = Parser(bot=bot).guild_create(_guild_data())
        self.assertIs(type(guild), PartialGuild)
        self.assertIs(bot.cache.get_guild(1), guild)


class TestGuildUpdate(unittest.TestCase):
    def test_cached_guild_is_updated_in_place(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.guilds)
        parser = Parser(bot=bot)
        (cached,) = parser.guild_create(_guild_data())
        (updated,) = parser.guild_update(_guild_data(name="renamed"))
        self.assertIs(updated, cached)
        self.assertEqual(cached.name, "renamed")

    def test_uncached_without_listener_builds_nothing(self) -> None:
        bot = FakeBot(cache_flags=None)
        (result,) = Parser(bot=bot).guild_update(_guild_data())
        self.assertIsNone(result)

    def test_uncached_with_listener_builds_guild(self) -> None:
        bot = FakeBot(cache_flags=None, listeners={"guild_update"})
        (result,) = Parser(bot=bot).guild_update(_guild_data(name="x"))
        self.assertIsInstance(result, Guild)
        self.assertEqual(result.name, "x")


class TestReactionMember(unittest.TestCase):
    def _data(self):
        return {
            "user_id": "5", "channel_id": "2", "message_id": "3", "guild_id": "1",
            "emoji": {"id": None, "name": "x"}, "burst": False, "type": 0,
            "member": {"user": {"id": "5"}},
        }

    def test_prefers_cached_full_member(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.partial_guilds | GatewayCacheFlags.members)
        guild = _cached_partial_guild(bot)
        member = Member.__new__(Member)
        member.id = 5
        guild._cache_members[5] = member
        reaction = Reaction(state=bot.state, data=self._data())
        self.assertIs(reaction.member, member)


class TestGuildCreateStageInstances(unittest.TestCase):
    def test_stage_instances_attached_to_cached_stage_channels(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.guilds | GatewayCacheFlags.channels)
        (guild,) = Parser(bot=bot).guild_create(_guild_data(
            channels=[{
                "id": "10", "type": 13, "name": "stage", "guild_id": "1",
                "bitrate": 64000, "user_limit": 0,
            }],
            stage_instances=[{
                "id": "20", "guild_id": "1", "channel_id": "10", "topic": "hi",
                "privacy_level": 2, "discoverable_disabled": False,
            }],
        ))
        channel = guild.get_channel(10)
        self.assertIsInstance(channel, StageChannel)
        self.assertEqual(channel.stage_instance.id, 20)


def _thread_data(thread_id=30, parent_id=10, archived=False):
    return {
        "id": str(thread_id), "type": 11, "guild_id": "1", "parent_id": str(parent_id),
        "name": "thread", "owner_id": "5",
        "thread_metadata": {"archived": archived, "auto_archive_duration": 60, "locked": False},
    }


class TestThreadCacheLifetime(unittest.TestCase):
    def _setup(self):
        bot = FakeBot(cache_flags=GatewayCacheFlags.guilds | GatewayCacheFlags.channels | GatewayCacheFlags.threads)
        parser = Parser(bot=bot)
        (guild,) = parser.guild_create(_guild_data(
            channels=[{"id": "10", "type": 0, "name": "general", "guild_id": "1"}],
        ))
        return parser, guild

    def test_archiving_removes_thread(self) -> None:
        parser, guild = self._setup()
        parser.thread_create(_thread_data())
        self.assertIsNotNone(guild.get_thread(30))

        parser.thread_update(_thread_data(archived=True))
        self.assertIsNone(guild.get_thread(30))

    def test_unarchiving_adds_thread_back(self) -> None:
        parser, guild = self._setup()
        parser.thread_update(_thread_data(archived=True))
        self.assertIsNone(guild.get_thread(30))

        parser.thread_update(_thread_data(archived=False))
        self.assertIsNotNone(guild.get_thread(30))

    def test_deleting_parent_channel_removes_its_threads(self) -> None:
        parser, guild = self._setup()
        parser.thread_create(_thread_data(thread_id=30, parent_id=10))
        parser.thread_create(_thread_data(thread_id=31, parent_id=99))

        parser.channel_delete({"id": "10", "type": 0, "name": "general", "guild_id": "1"})
        self.assertIsNone(guild.get_thread(30))
        self.assertIsNotNone(guild.get_thread(31))

    def test_partial_threads_keep_parent_id(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.guilds | GatewayCacheFlags.partial_channels | GatewayCacheFlags.partial_threads)
        parser = Parser(bot=bot)
        (guild,) = parser.guild_create(_guild_data(
            channels=[{"id": "10", "type": 0, "name": "general", "guild_id": "1", "parent_id": "5"}],
            threads=[_thread_data(thread_id=30, parent_id=10)],
        ))
        parser.thread_create(_thread_data(thread_id=31, parent_id=10))
        self.assertEqual(guild.get_channel(10).parent_id, 5)
        self.assertEqual(guild.get_thread(30).parent_id, 10)
        self.assertEqual(guild.get_thread(31).parent_id, 10)

        parser.channel_delete({"id": "10", "type": 0, "name": "general", "guild_id": "1"})
        self.assertIsNone(guild.get_thread(30))
        self.assertIsNone(guild.get_thread(31))

    def test_partial_channel_parent_id_is_optional(self) -> None:
        bot = FakeBot()
        self.assertIsNone(bot.get_partial_channel(10, guild_id=1).parent_id)
        self.assertEqual(bot.get_partial_channel(10, guild_id=1, parent_id="5").parent_id, 5)


class TestChannelInfo(unittest.TestCase):
    def test_parses_channels(self) -> None:
        bot = FakeBot(cache_flags=GatewayCacheFlags.partial_guilds)
        (guild, channels) = Parser(bot=bot).channel_info({
            "guild_id": "1",
            "channels": [
                {"id": "2", "status": "chilling", "voice_start_time": 1700000000},
                {"id": "3", "status": None},
            ],
        })
        self.assertEqual(guild.id, 1)
        self.assertIsInstance(channels[0], ChannelInfo)
        self.assertEqual(channels[0].channel.id, 2)
        self.assertEqual(channels[0].status, "chilling")
        self.assertEqual(int(channels[0].voice_start_time.timestamp()), 1700000000)
        self.assertIsNone(channels[1].status)
        self.assertIsNone(channels[1].voice_start_time)


if __name__ == "__main__":
    unittest.main()
