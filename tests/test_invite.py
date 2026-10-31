import unittest

from discord_http import PartialInvite

from _fake_client import FakeBot


class FakeResponse:
    def __init__(self, response):
        self.response = response


class FakeState:
    def __init__(self, csv_text: str):
        self._csv_text = csv_text
        self.bot = FakeBot(self)

    async def query(self, method, path, **kwargs):
        return FakeResponse(self._csv_text)


class TestFetchTargetUsersCSVParsing(unittest.IsolatedAsyncioTestCase):
    async def test_skips_header_row(self) -> None:
        invite = PartialInvite(state=FakeState("user_id\n123\n456\n"), code="abc")
        users = await invite.fetch_target_users()
        self.assertEqual([u.id for u in users], [123, 456])

    async def test_handles_no_header(self) -> None:
        invite = PartialInvite(state=FakeState("123\n456\n"), code="abc")
        users = await invite.fetch_target_users()
        self.assertEqual([u.id for u in users], [123, 456])

    async def test_handles_empty_response(self) -> None:
        invite = PartialInvite(state=FakeState(""), code="abc")
        users = await invite.fetch_target_users()
        self.assertEqual(users, [])


class RecordingState:
    def __init__(self):
        self.calls = []
        self.bot = FakeBot(self)

    async def query(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return FakeResponse("")


class TestTargetUserEndpoints(unittest.IsolatedAsyncioTestCase):
    async def test_add_and_remove_target_user(self) -> None:
        state = RecordingState()
        invite = PartialInvite(state=state, code="abc")
        await invite.add_target_user(123)
        await invite.remove_target_user(state.bot.get_partial_user(456))
        self.assertEqual(state.calls[0][:2], ("PUT", "/invites/abc/target-users/123"))
        self.assertEqual(state.calls[1][:2], ("DELETE", "/invites/abc/target-users/456"))

    async def test_bulk_add_and_remove(self) -> None:
        state = RecordingState()
        invite = PartialInvite(state=state, code="abc")
        await invite.bulk_add_target_users([1, 2])
        await invite.bulk_remove_target_users([3])
        self.assertEqual(state.calls[0][1], "/invites/abc/target-users/bulk-add")
        self.assertEqual(state.calls[0][2]["json"], {"user_ids": ["1", "2"]})
        self.assertEqual(state.calls[1][1], "/invites/abc/target-users/bulk-delete")
        self.assertEqual(state.calls[1][2]["json"], {"user_ids": ["3"]})

    async def test_bulk_limit(self) -> None:
        invite = PartialInvite(state=RecordingState(), code="abc")
        with self.assertRaises(ValueError):
            await invite.bulk_add_target_users(list(range(1001)))


if __name__ == "__main__":
    unittest.main()
