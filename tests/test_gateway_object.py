import unittest

from types import SimpleNamespace

from discord_http.gateway.enums import ActivityType, StatusType
from discord_http.gateway.object import PlayingStatus, ThreadListSyncPayload


class TestPlayingStatusStyleCoercion(unittest.TestCase):
    def test_string_status_and_type_are_converted_to_enums(self) -> None:
        status = PlayingStatus(name="hi", status="idle", type="watching")
        self.assertEqual(status.status, StatusType.idle)
        self.assertEqual(status.type, ActivityType.watching)

    def test_int_status_and_type_are_converted_to_enums(self) -> None:
        status = PlayingStatus(status=int(StatusType.dnd), type=int(ActivityType.listening))
        self.assertEqual(status.status, StatusType.dnd)
        self.assertEqual(status.type, ActivityType.listening)

    def test_idle_status_sets_since_timestamp(self) -> None:
        status = PlayingStatus(status="idle")
        self.assertIsNotNone(status.since)

    def test_non_idle_status_leaves_since_none(self) -> None:
        status = PlayingStatus(status="online")
        self.assertIsNone(status.since)

    def test_streaming_type_requires_a_url(self) -> None:
        status = PlayingStatus(type="streaming", url="https://twitch.tv/x")
        self.assertEqual(status.url, "https://twitch.tv/x")

    def test_non_streaming_type_has_no_url_even_if_given(self) -> None:
        status = PlayingStatus(type="playing", url="https://twitch.tv/x")
        self.assertIsNone(status.url)


class TestPlayingStatusToDict(unittest.TestCase):
    def test_custom_type_mirrors_name_into_state(self) -> None:
        status = PlayingStatus(name="Feeling great", type="custom")
        payload = status.to_dict()
        self.assertEqual(payload["activities"][0]["name"], "Feeling great")
        self.assertEqual(payload["activities"][0]["state"], "Feeling great")

    def test_missing_type_with_name_falls_back_to_playing(self) -> None:
        status = PlayingStatus(name="Some Game")
        payload = status.to_dict()
        self.assertEqual(payload["activities"][0]["type"], int(ActivityType.playing))

    def test_no_name_produces_an_empty_activity(self) -> None:
        status = PlayingStatus()
        payload = status.to_dict()
        self.assertEqual(payload["activities"], [{}])

    def test_url_only_included_for_streaming(self) -> None:
        status = PlayingStatus(type="streaming", url="https://twitch.tv/x", name="Game")
        payload = status.to_dict()
        self.assertEqual(payload["activities"][0]["url"], "https://twitch.tv/x")


class FakeGuild:
    id = 10

    def __init__(self):
        self._channels = {}

    def get_channel(self, cid):
        return self._channels.get(cid)

    def get_partial_channel(self, cid):
        return SimpleNamespace(id=cid)


class FakeCache:
    def __init__(self, guild):
        self._guild = guild

    def get_guild(self, gid):
        return self._guild


class FakeBot:
    def __init__(self, guild):
        self.cache = FakeCache(guild)
        self._guild = guild

    def get_partial_guild(self, gid):
        return self._guild


class FakeState:
    def __init__(self, guild):
        self.bot = FakeBot(guild)


def _thread_data(thread_id: int, parent_id: int) -> dict:
    return {
        "id": str(thread_id), "guild_id": "10", "parent_id": str(parent_id),
        "type": 11, "name": "thread",
    }


def _member_data(thread_id: int, user_id: int) -> dict:
    return {
        "id": str(thread_id), "user_id": str(user_id),
        "join_timestamp": "2024-01-01T00:00:00.000000+00:00", "flags": 0,
    }


class TestThreadListSyncPayloadCombined(unittest.TestCase):
    """ Regression coverage for combined() incorrectly matching members to
    threads via `member.id` (the member's USER id) instead of
    `member.thread_id` - the two are unrelated snowflakes, so the old
    comparison silently produced an empty member list for every thread. """

    def _payload(self, threads, members, channel_ids=("20",)) -> ThreadListSyncPayload:
        guild = FakeGuild()
        return ThreadListSyncPayload(state=FakeState(guild), data={
            "guild_id": "10",
            "channel_ids": list(channel_ids),
            "threads": threads,
            "members": members,
        })

    def test_member_is_matched_to_its_thread_by_thread_id(self) -> None:
        payload = self._payload(
            threads=[_thread_data(1, 20)],
            members=[_member_data(1, 999)],
        )
        (channel, (thread, members)), = payload.combined()
        self.assertEqual(channel.id, 20)
        self.assertEqual(thread.id, 1)
        self.assertEqual([m.id for m in members], [999])

    def test_member_belonging_to_a_different_thread_is_excluded(self) -> None:
        payload = self._payload(
            threads=[_thread_data(1, 20)],
            members=[_member_data(2, 999)],  # belongs to thread 2, not 1
        )
        (_, (_, members)), = payload.combined()
        self.assertEqual(members, [])

    def test_thread_without_a_matching_channel_is_skipped(self) -> None:
        payload = self._payload(
            threads=[_thread_data(1, 999)],  # parent_id not in channel_ids
            members=[],
            channel_ids=("20",),
        )
        self.assertEqual(list(payload.combined()), [])

    def test_multiple_members_can_belong_to_the_same_thread(self) -> None:
        payload = self._payload(
            threads=[_thread_data(1, 20)],
            members=[_member_data(1, 100), _member_data(1, 200)],
        )
        (_, (_, members)), = payload.combined()
        self.assertCountEqual([m.id for m in members], [100, 200])


class TestThreadListSyncPayloadProperties(unittest.TestCase):
    def test_channel_ids_are_converted_to_ints(self) -> None:
        guild = FakeGuild()
        payload = ThreadListSyncPayload(state=FakeState(guild), data={
            "guild_id": "10", "channel_ids": ["20", "30"], "threads": [], "members": [],
        })
        self.assertEqual(payload.channel_ids, [20, 30])

    def test_empty_threads_and_members_return_empty_lists(self) -> None:
        guild = FakeGuild()
        payload = ThreadListSyncPayload(state=FakeState(guild), data={
            "guild_id": "10", "channel_ids": [], "threads": [], "members": [],
        })
        self.assertEqual(payload.threads, [])
        self.assertEqual(payload.members, [])
        self.assertEqual(payload.channels, [])


if __name__ == "__main__":
    unittest.main()
