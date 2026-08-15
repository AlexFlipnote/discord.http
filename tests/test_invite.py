import unittest

from discord_http import PartialInvite


class FakeResponse:
    def __init__(self, response):
        self.response = response


class FakeState:
    def __init__(self, csv_text: str):
        self._csv_text = csv_text

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


if __name__ == "__main__":
    unittest.main()
