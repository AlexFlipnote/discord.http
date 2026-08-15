import time
import unittest

from discord_http.gateway.client import GatewayClient
from discord_http.gateway.shard import GatewayRatelimiter, Status


class TestGatewayRatelimiter(unittest.TestCase):
    def test_defaults(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0)
        self.assertEqual(limiter.max, 110)
        self.assertEqual(limiter.remaining, 110)
        self.assertEqual(limiter.per, 60.0)

    def test_reset_restores_remaining_and_clears_window(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0, count=2)
        limiter.remaining = 0
        limiter.window = time.monotonic()
        limiter.reset()
        self.assertEqual(limiter.remaining, 2)
        self.assertEqual(limiter.window, 0.0)

    def test_is_ratelimited_true_within_window_when_exhausted(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0, count=2)
        limiter.window = time.monotonic()
        limiter.remaining = 0
        self.assertTrue(limiter.is_ratelimited())

    def test_is_ratelimited_false_within_window_when_remaining(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0, count=2)
        limiter.window = time.monotonic()
        limiter.remaining = 1
        self.assertFalse(limiter.is_ratelimited())

    def test_is_ratelimited_false_once_window_expires_even_if_exhausted(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0, count=2, per=60.0)
        limiter.window = time.monotonic() - 1000
        limiter.remaining = 0
        self.assertFalse(limiter.is_ratelimited())

    def test_get_delay_consumes_tokens_until_exhausted_then_returns_wait_time(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0, count=2, per=60.0)
        limiter.window = time.monotonic() - 1000  # force the initial window-reset branch

        self.assertEqual(limiter.get_delay(), 0.0)
        self.assertEqual(limiter.remaining, 1)

        self.assertEqual(limiter.get_delay(), 0.0)
        self.assertEqual(limiter.remaining, 0)

        delay = limiter.get_delay()
        self.assertGreater(delay, 0.0)
        self.assertLessEqual(delay, 60.0)

    def test_get_delay_resets_window_once_expired(self) -> None:
        limiter = GatewayRatelimiter(shard_id=0, count=1, per=60.0)
        limiter.window = time.monotonic() - 1000
        limiter.remaining = 0

        delay = limiter.get_delay()
        self.assertEqual(delay, 0.0)
        self.assertEqual(limiter.remaining, 0)  # consumed the single token from the fresh window


class TestStatus(unittest.TestCase):
    def test_can_resume_false_without_session_id(self) -> None:
        status = Status(shard_id=0)
        self.assertFalse(status.can_resume())

    def test_can_resume_true_with_session_id(self) -> None:
        status = Status(shard_id=0)
        status.session_id = "abc"
        self.assertTrue(status.can_resume())

    def test_ping_is_zero_without_a_resumable_session(self) -> None:
        status = Status(shard_id=0)
        status._last_recv = 100.0
        status._last_send = 1.0
        self.assertEqual(status.ping, 0.0)

    def test_ping_is_recv_minus_send_when_resumable(self) -> None:
        status = Status(shard_id=0)
        status.session_id = "abc"
        status._last_send = 1.0
        status._last_recv = 3.5
        self.assertEqual(status.ping, 2.5)

    def test_is_zombied_false_before_any_heartbeat_sent(self) -> None:
        status = Status(shard_id=0)
        self.assertFalse(status.is_zombied())

    def test_is_zombied_true_when_heartbeat_sent_after_last_ack(self) -> None:
        status = Status(shard_id=0)
        status._last_ack = 1.0
        status._last_heartbeat = 2.0
        self.assertTrue(status.is_zombied())

    def test_is_zombied_false_once_acked_after_heartbeat(self) -> None:
        status = Status(shard_id=0)
        status._last_heartbeat = 1.0
        status._last_ack = 2.0
        self.assertFalse(status.is_zombied())

    def test_reset_clears_session_sequence_and_latency(self) -> None:
        status = Status(shard_id=0)
        status.sequence = 5
        status.session_id = "abc"
        status.latency = 0.2
        status.reset()
        self.assertIsNone(status.sequence)
        self.assertIsNone(status.session_id)
        self.assertEqual(status.latency, float("inf"))

    def test_update_ready_data_none_is_a_noop(self) -> None:
        status = Status(shard_id=0)
        status.update_ready_data(None)  # should not raise
        self.assertIsNone(status.session_id)

    def test_update_ready_data_sets_session_and_gateway(self) -> None:
        status = Status(shard_id=0)
        status.update_ready_data({
            "session_id": "xyz", "resume_gateway_url": "wss://example.com/",
        })
        self.assertEqual(status.session_id, "xyz")
        self.assertEqual(str(status.gateway), "wss://example.com/")

    def test_get_payload_includes_sequence(self) -> None:
        status = Status(shard_id=0)
        status.sequence = 42
        payload = status.get_payload()
        self.assertEqual(payload["d"], 42)

    def test_ack_computes_latency_from_last_send(self) -> None:
        status = Status(shard_id=0)
        status._last_send = time.perf_counter() - 0.05
        status.ack(ignore_warning=True)
        self.assertGreater(status.latency, 0.0)
        self.assertLess(status.latency, 5.0)

    def test_ack_warns_on_high_latency_unless_ignored(self) -> None:
        status = Status(shard_id=0)
        status._last_send = time.perf_counter() - 15
        with self.assertLogs("discord_http", level="WARNING"):
            status.ack()


class FakeRouter:
    def add_get(self, *args, **kwargs) -> None:
        pass


class FakeBackend:
    def __init__(self):
        self.router = FakeRouter()


class FakeBot:
    def __init__(self):
        self.backend = FakeBackend()


class TestShardByGuildId(unittest.TestCase):
    """ shard_by_guild_id() extracts the timestamp bits of a snowflake via a
    22-bit right shift (the same shift used to reconstruct a snowflake's
    creation time) before taking it modulo the shard count. """

    def _client(self, shard_count: int) -> GatewayClient:
        return GatewayClient(bot=FakeBot(), shard_count=shard_count)

    def test_single_shard_always_returns_zero(self) -> None:
        client = self._client(1)
        self.assertEqual(client.shard_by_guild_id(175928847299117063), 0)
        self.assertEqual(client.shard_by_guild_id(500000000000000000), 0)

    def test_known_guild_ids_map_to_expected_shards(self) -> None:
        client = self._client(16)
        self.assertEqual(client.shard_by_guild_id(175928847299117063), 4)
        self.assertEqual(client.shard_by_guild_id(933704302252408853), 4)
        self.assertEqual(client.shard_by_guild_id(500000000000000000), 14)

    def test_accepts_plain_int_and_snowflake_like_objects(self) -> None:
        client = self._client(4)

        class FakeSnowflake:
            def __int__(self) -> int:
                return 500000000000000000

        self.assertEqual(
            client.shard_by_guild_id(500000000000000000),
            client.shard_by_guild_id(FakeSnowflake()),  # type: ignore[arg-type]
        )


if __name__ == "__main__":
    unittest.main()
