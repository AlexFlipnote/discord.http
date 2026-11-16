import asyncio
import unittest

from types import SimpleNamespace
from unittest import mock

from aiohttp import WSMsgType

from discord_http.gateway.enums import PayloadType, ShardCloseType
from discord_http.gateway.shard import Shard

TOKEN = "a.b.c"


class _WS:
    close_code = None

    def __init__(self, events: list | None = None) -> None:
        self.sent: list[dict] = []
        self.events = events or []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def receive(self, timeout: float | None = None):  # noqa: ANN201, ARG002
        if self.events:
            return self.events.pop(0)
        # Not asyncio.sleep, the reconnect tests replace that with a no-op
        await asyncio.Event().wait()

    async def ping(self) -> None:
        pass


class _Connect:
    def __init__(self, ws: _WS | None = None, exc: Exception | None = None) -> None:
        self.ws, self.exc = ws, exc

    async def __aenter__(self) -> _WS | None:
        if self.exc is not None:
            raise self.exc
        return self.ws

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Session:
    def __init__(self, plan: list[_Connect]) -> None:
        self.plan = plan
        self.calls = 0

    def ws_connect(self, _url: str, **_kwargs: object) -> _Connect:
        self.calls += 1
        return self.plan.pop(0)


def _shard(session: object = None, *, debug_events: bool = False) -> tuple[Shard, list]:
    dispatched: list[tuple[str, tuple]] = []
    bot = SimpleNamespace(
        state=SimpleNamespace(
            http=SimpleNamespace(session=session),
            _default_headers={"User-Agent": "test"},
            create_jitter=lambda: 0.0,
        ),
        token=TOKEN,
        gateway_capabilities=None,
        playing_status=None,
        guild_ready_timeout=5,
        chunk_guilds_on_startup=False,
        cache=SimpleNamespace(cache_flags=None),
        has_any_dispatch=lambda name: name == "shard_closed",
        dispatch=lambda name, *args: dispatched.append((name, args)),
    )
    shard = Shard(
        bot=bot, intents=None, cache_flags=None, shard_id=0, shard_count=1,  # type: ignore[arg-type]
        api_version=10, debug_events=debug_events,
    )
    return shard, dispatched


class TestTokenStaysOutOfDebugEvents(unittest.IsolatedAsyncioTestCase):
    async def test_identify_and_resume_are_redacted_for_listeners(self) -> None:
        shard, dispatched = _shard(debug_events=True)
        shard.ws = _WS()  # type: ignore[assignment]

        for op in (PayloadType.identify, PayloadType.resume):
            await shard.send_message({"op": int(op), "d": {"token": TOKEN, "seq": 1}})

        seen = [args[0] for name, args in dispatched if name == "raw_socket_sent"]
        self.assertEqual(len(seen), 2)
        for message in seen:
            self.assertEqual(message["d"]["token"], "[redacted]")
            self.assertEqual(message["d"]["seq"], 1)

        # What goes over the wire is untouched
        self.assertEqual([m["d"]["token"] for m in shard.ws.sent], [TOKEN, TOKEN])  # type: ignore[union-attr]


class TestOutboundCommandsAreRatelimited(unittest.IsolatedAsyncioTestCase):
    async def test_voice_state_and_presence_count_against_the_limit(self) -> None:
        shard, _ = _shard()
        shard.ws = _WS()  # type: ignore[assignment]
        before = shard._ratelimiter.max

        await shard.change_voice_state(guild_id=1, channel_id=2)
        await shard.change_presence(SimpleNamespace(to_dict=dict))  # type: ignore[arg-type]

        self.assertEqual(shard._ratelimiter.remaining, before - 2)


class TestReconnectSurvivesAFailedConnect(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = mock.patch("discord_http.gateway.shard.asyncio.sleep", new=mock.AsyncMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    async def _settle(self, shard: Shard) -> None:
        for _ in range(20):
            await asyncio.get_running_loop().run_in_executor(None, lambda: None)
            if shard._connection is None or shard._connection.done():
                break

    async def test_keeps_trying_after_the_websocket_fails_to_open(self) -> None:
        dropped = _WS([SimpleNamespace(type=WSMsgType.ERROR, data="boom")])
        back = _WS()
        session = _Session([
            _Connect(dropped),
            _Connect(exc=OSError("network is down")),
            _Connect(exc=TimeoutError()),
            _Connect(back),
        ])
        shard, dispatched = _shard(session)
        shard._was_ready = True
        shard.status.session_id = "session"
        shard.status.sequence = 5

        shard.connect()
        for _ in range(50):
            await asyncio.get_running_loop().run_in_executor(None, lambda: None)
            if session.calls >= 4:
                break

        self.assertEqual(session.calls, 4)
        self.assertIs(shard.ws, back)
        # The session survived, so the next thing sent can be a RESUME
        self.assertEqual(shard.status.session_id, "session")

        kinds = [args[0].close_type for name, args in dispatched if name == "shard_closed"]
        self.assertNotIn(ShardCloseType.hard_crash, kinds)
        self.assertEqual(kinds.count(ShardCloseType.reconnect), 2)

        shard._should_kill = True
        if shard._connection is not None:
            shard._connection.cancel()

    async def test_startup_failure_is_left_to_the_launcher(self) -> None:
        session = _Session([_Connect(exc=OSError("network is down"))])
        shard, dispatched = _shard(session)

        shard.connect()
        await self._settle(shard)

        self.assertEqual(session.calls, 1)
        kinds = [args[0].close_type for name, args in dispatched if name == "shard_closed"]
        self.assertEqual(kinds, [ShardCloseType.hard_crash])

    async def test_unexpected_errors_still_stop_the_shard(self) -> None:
        session = _Session([_Connect(exc=RuntimeError("bug"))])
        shard, dispatched = _shard(session)
        shard._was_ready = True

        shard.connect()
        await self._settle(shard)

        self.assertEqual(session.calls, 1)
        kinds = [args[0].close_type for name, args in dispatched if name == "shard_closed"]
        self.assertEqual(kinds, [ShardCloseType.hard_crash])


if __name__ == "__main__":
    unittest.main()
