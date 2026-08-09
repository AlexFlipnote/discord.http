import asyncio
import unittest

from discord_http.http import DiscordAPI, GlobalRatelimit, Ratelimit
from discord_http.utils import MultipartData


class TestGlobalRatelimitConstruction(unittest.TestCase):
    def test_construction_outside_a_running_loop_does_not_raise(self) -> None:
        # Regression test: DiscordAPI.__init__ (and thus GlobalRatelimit())
        # can run before any event loop exists, e.g. a plain `Client(...)`
        # in a synchronous script. Must not eagerly call get_running_loop().
        grl = GlobalRatelimit()
        self.assertIsNone(grl._loop)


class TestRatelimit(unittest.IsolatedAsyncioTestCase):
    async def test_is_inactive_false_when_fresh(self) -> None:
        rl = Ratelimit("GET /test")
        self.assertFalse(rl.is_inactive())

    async def test_is_inactive_true_after_idle_window(self) -> None:
        rl = Ratelimit("GET /test")
        rl._last_request -= 61
        self.assertTrue(rl.is_inactive())

    async def test_is_inactive_false_while_in_flight(self) -> None:
        rl = Ratelimit("GET /test")
        rl._last_request -= 61
        rl.in_flight = 1
        self.assertFalse(rl.is_inactive())

    async def test_is_inactive_false_during_cooldown_window(self) -> None:
        # Regression test: a bucket must not be evicted while it's mid-429
        # cooldown, or the next request starts from a falsely-optimistic
        # fresh bucket and immediately re-triggers the same rate limit.
        rl = Ratelimit("GET /test")
        rl._last_request -= 61
        rl.expires = rl._loop.time() + 30
        self.assertFalse(rl.is_inactive())

    async def test_is_inactive_true_once_cooldown_expires(self) -> None:
        rl = Ratelimit("GET /test")
        rl._last_request -= 61
        rl.expires = rl._loop.time() - 1
        self.assertTrue(rl.is_inactive())

    async def test_aenter_aexit_tracks_in_flight(self) -> None:
        rl = Ratelimit("GET /test")
        async with rl:
            self.assertEqual(rl.in_flight, 1)
            self.assertEqual(rl.remaining, 0)
        self.assertEqual(rl.in_flight, 0)

    async def test_aenter_waits_until_bucket_resets(self) -> None:
        rl = Ratelimit("GET /test")
        rl.remaining = 0
        rl.expires = rl._loop.time() + 0.2

        start = rl._loop.time()
        async with rl:
            pass
        elapsed = rl._loop.time() - start

        self.assertGreaterEqual(elapsed, 0.15)


class TestGlobalRatelimit(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_consumes_tokens_up_to_max(self) -> None:
        grl = GlobalRatelimit(max_requests=3, per=10.0)
        for _ in range(3):
            await grl.acquire()
        self.assertEqual(grl.remaining, 0)

    async def test_acquire_blocks_once_exhausted_and_resumes_after_window(self) -> None:
        grl = GlobalRatelimit(max_requests=1, per=0.2)
        await grl.acquire()

        start = grl._loop.time()
        await grl.acquire()  # must wait for the window to roll over
        elapsed = grl._loop.time() - start

        self.assertGreaterEqual(elapsed, 0.1)

    async def test_lock_for_blocks_every_request_until_it_clears(self) -> None:
        # Regression test: a real global 429 must pause ALL requests, not
        # just the one route that happened to trigger it.
        grl = GlobalRatelimit(max_requests=5, per=10.0)
        grl.lock_for(0.2)

        start = grl._loop.time()
        await grl.acquire()
        elapsed = grl._loop.time() - start

        self.assertGreaterEqual(elapsed, 0.15)

    async def test_lock_clears_itself_once_expired(self) -> None:
        grl = GlobalRatelimit(max_requests=5, per=10.0)
        grl.lock_for(0.05)
        await asyncio.sleep(0.1)

        await grl.acquire()
        self.assertIsNone(grl.locked_until)


class TestGetBucketKey(unittest.TestCase):
    def setUp(self) -> None:
        # _get_bucket_key touches only its arguments, not any instance state,
        # so a bare instance (skipping __init__) is enough to exercise it.
        self.api = object.__new__(DiscordAPI)

    def test_normalizes_sub_resource_id(self) -> None:
        key = self.api._get_bucket_key("GET", "/channels/123/messages/456")
        self.assertEqual(key, "GET /channels/123/messages/:id")

    def test_leaves_top_level_resource_id_untouched(self) -> None:
        key = self.api._get_bucket_key("GET", "/guilds/999/channels")
        self.assertEqual(key, "GET /guilds/999/channels")

    def test_delete_messages_gets_special_suffix(self) -> None:
        key = self.api._get_bucket_key("DELETE", "/channels/123/messages/456")
        self.assertEqual(key, "DELETE /channels/123/messages/:id-delete")

    def test_strips_query_parameters(self) -> None:
        key = self.api._get_bucket_key("GET", "/channels/123/messages?limit=50")
        self.assertEqual(key, "GET /channels/123/messages")


class TestMultipartDataReset(unittest.TestCase):
    def test_reset_rewinds_attached_file_streams(self) -> None:
        import io

        from discord_http import File

        buffer = io.BytesIO(b"abcdef")
        file = File(buffer, filename="sample.bin")

        multidata = MultipartData()
        multidata.attach("files[0]", file, filename=file.filename)

        file.data.read()  # simulate the first (failed) send consuming the stream
        self.assertEqual(file.data.read(), b"")

        multidata.reset()
        self.assertEqual(file.data.read(3), b"abc")


if __name__ == "__main__":
    unittest.main()
