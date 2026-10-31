import types
import unittest

from unittest import mock

from discord_http.commands import Interaction
from tests.test_context import _make_client, _member, _message, _user, close_client


async def _noop(*_) -> None:
    pass


class _ClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()

    def tearDown(self) -> None:
        close_client(self.client)


class TestFindInteraction(_ClientTestCase):
    def _add(self, custom_id: str, *, regex: bool = True) -> Interaction:
        return self.client.add_interaction(Interaction(_noop, custom_id, regex=regex))

    def test_exact_lookup_wins(self) -> None:
        exact = self._add("ticket:1", regex=False)
        self._add(r"ticket:\d+")
        self.assertIs(self.client.find_interaction("ticket:1"), exact)

    def test_first_registered_regex_wins(self) -> None:
        broad = self._add(r"ticket:")
        narrow = self._add(r"ticket:\d+")
        other = self._add(r"poll:(yes|no)")
        self.assertIs(self.client.find_interaction("ticket:5"), broad)
        self.assertIs(self.client.find_interaction("poll:no"), other)
        self.assertIsNone(self.client.find_interaction("nope"))
        # Uses re.match semantics (anchored at the start only)
        self.assertIsNone(self.client.find_interaction("x-ticket:5"))

        self.client.remove_interaction(broad)
        self.assertIs(self.client.find_interaction("ticket:5"), narrow)


class TestMessagePrefersCachedMember(_ClientTestCase):
    def test_author_and_mentions_use_cached_member(self) -> None:
        guild = self.client.get_partial_guild(100)
        cached = self.client.create_member_from_data(_member("3"), guild=guild)
        fake_guild = types.SimpleNamespace(id=100, get_member=lambda uid: cached if uid == 3 else None)

        data = _message()
        data["member"] = {"roles": [], "joined_at": "2024-01-01T00:00:00+00:00", "flags": 0}
        data["mentions"] = [
            {**_user("3"), "member": {"roles": [], "joined_at": "2024-01-01T00:00:00+00:00", "flags": 0}},
            {**_user("4"), "member": {"roles": [], "joined_at": "2024-01-01T00:00:00+00:00", "flags": 0}},
        ]

        with mock.patch.object(type(self.client.cache), "get_guild", return_value=fake_guild):
            message = self.client.create_message_from_data(data, guild=guild)

        self.assertIs(message.author, cached)
        self.assertIs(message.mentions[0], cached)
        self.assertIsNot(message.mentions[1], cached)
        self.assertEqual(message.mentions[1].id, 4)

    def test_builds_member_without_cache(self) -> None:
        guild = self.client.get_partial_guild(100)
        data = _message()
        data["member"] = {"roles": [], "joined_at": "2024-01-01T00:00:00+00:00", "flags": 0}
        message = self.client.create_message_from_data(data, guild=guild)
        self.assertEqual(message.author.id, 3)
        self.assertEqual(message.author.guild.id, 100)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
