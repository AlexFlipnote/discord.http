import unittest

from datetime import UTC, datetime

from discord_http import PartialVoiceState

from _fake_client import FakeBot


class FakeResponse:
    def __init__(self, response):
        self.response = response


class _MeBot(FakeBot):
    class _User:
        id = 4242

    user = _User()


class FakeState:
    def __init__(self):
        self.bot = _MeBot(self)
        self.calls = []

    async def query(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return FakeResponse("")


class TestPartialVoiceStateEdit(unittest.IsolatedAsyncioTestCase):
    async def test_own_voice_state_uses_me_route(self) -> None:
        state = FakeState()
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        await PartialVoiceState(state=state, id=4242, guild_id=1).edit(
            channel_id=5, suppress=False, request_to_speak_timestamp=ts
        )

        method, path, kwargs = state.calls[0]
        self.assertEqual((method, path), ("PATCH", "/guilds/1/voice-states/@me"))
        self.assertEqual(kwargs["json"], {
            "channel_id": "5", "suppress": False,
            "request_to_speak_timestamp": ts.isoformat()
        })

    async def test_clear_request_to_speak(self) -> None:
        state = FakeState()
        await PartialVoiceState(state=state, id=4242, guild_id=1).edit(request_to_speak_timestamp=None)
        self.assertEqual(state.calls[0][2]["json"], {"request_to_speak_timestamp": None})

    async def test_other_user_uses_user_route(self) -> None:
        state = FakeState()
        await PartialVoiceState(state=state, id=7, guild_id=1).edit(suppress=True)
        self.assertEqual(state.calls[0][1], "/guilds/1/voice-states/7")

    async def test_request_to_speak_rejected_for_other_user(self) -> None:
        state = FakeState()
        with self.assertRaises(ValueError):
            await PartialVoiceState(state=state, id=7, guild_id=1).edit(
                request_to_speak_timestamp=None
            )
        self.assertEqual(state.calls, [])


if __name__ == "__main__":
    unittest.main()
