import asyncio
import unittest

from types import SimpleNamespace

from discord_http.http import DiscordAPI, GlobalRatelimit, HTTPResponse, Ratelimit
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

    async def test_update_stores_bucket_hash_from_header(self) -> None:
        rl = Ratelimit("GET /test")
        self.assertIsNone(rl.bucket_hash)

        response = SimpleNamespace(headers={
            "X-RateLimit-Bucket": "abcd1234",
            "X-RateLimit-Reset": "0",
            "X-RateLimit-Limit": "5",
            "X-RateLimit-Remaining": "4",
            "X-RateLimit-Reset-After": "1.0",
        })
        rl.update(response)

        self.assertEqual(rl.bucket_hash, "abcd1234")

    async def test_update_keeps_previous_bucket_hash_when_header_absent(self) -> None:
        rl = Ratelimit("GET /test")
        rl.bucket_hash = "abcd1234"

        rl.update(SimpleNamespace(headers={}))

        self.assertEqual(rl.bucket_hash, "abcd1234")

    async def test_update_logs_and_switches_when_bucket_hash_changes(self) -> None:
        # This is the actual "notice a divergence" signal bucket_hash exists for:
        # our local key stayed the same, but Discord's real bucket for it changed.
        rl = Ratelimit("GET /test")
        rl.bucket_hash = "old-hash"

        with self.assertLogs("discord_http", level="DEBUG") as logs:
            rl.update(SimpleNamespace(headers={"X-RateLimit-Bucket": "new-hash"}))

        self.assertEqual(rl.bucket_hash, "new-hash")
        self.assertTrue(any("old-hash" in m and "new-hash" in m for m in logs.output))


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

    def test_unlisted_subresource_route_still_collapses(self) -> None:
        # Regression test: the old implementation only collapsed IDs behind a
        # hardcoded keyword list, so any route outside it (scheduled events here)
        # kept a raw ID and fragmented into its own bucket forever.
        key = self.api._get_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.assertEqual(key, "GET /guilds/999/scheduled-events/:id")

    def test_global_route_with_no_major_param_collapses(self) -> None:
        key = self.api._get_bucket_key("GET", "/stickers/123")
        self.assertEqual(key, "GET /stickers/:id")

    def test_stage_instances_keeps_channel_id_as_major_param(self) -> None:
        key = self.api._get_bucket_key("GET", "/stage-instances/321")
        self.assertEqual(key, "GET /stage-instances/321")

    def test_webhook_route_keeps_webhook_id_and_collapses_message_id(self) -> None:
        key = self.api._get_bucket_key("PATCH", "/webhooks/123456/abcToken123/messages/789")
        self.assertEqual(key, "PATCH /webhooks/123456/abcToken123/messages/:id")

    def test_mixed_alphanumeric_segment_is_left_untouched(self) -> None:
        # A digit run *inside* a segment (a token, or the literal "@original"
        # placeholder) must not be partially replaced - only a whole segment
        # that is purely digits counts as an ID.
        key = self.api._get_bucket_key("PATCH", "/webhooks/123456/abcToken123/messages/@original")
        self.assertEqual(key, "PATCH /webhooks/123456/abcToken123/messages/@original")


class TestRouteTemplateAndMajorParam(unittest.TestCase):
    def setUp(self) -> None:
        self.api = object.__new__(DiscordAPI)

    def test_route_template_collapses_major_param_too(self) -> None:
        # Unlike _get_bucket_key, the template must ignore major param value,
        # since Discord's bucket hash is the same regardless of which guild.
        self.assertEqual(
            self.api._route_template("GET", "/guilds/999/scheduled-events/555"),
            "GET /guilds/:id/scheduled-events/:id",
        )

    def test_route_template_matches_across_different_major_param_values(self) -> None:
        template_a = self.api._route_template("GET", "/guilds/999/scheduled-events/555")
        template_b = self.api._route_template("GET", "/guilds/111/scheduled-events/222")
        self.assertEqual(template_a, template_b)

    def test_route_template_keeps_delete_messages_suffix(self) -> None:
        self.assertEqual(
            self.api._route_template("DELETE", "/channels/123/messages/456"),
            "DELETE /channels/:id/messages/:id-delete",
        )

    def test_major_param_value_extracts_the_raw_id(self) -> None:
        self.assertEqual(self.api._major_param_value("/channels/123/messages/456"), "123")

    def test_major_param_value_empty_when_no_major_param(self) -> None:
        self.assertEqual(self.api._major_param_value("/stickers/123"), "")


class TestResolveBucketKey(unittest.TestCase):
    def setUp(self) -> None:
        self.api = object.__new__(DiscordAPI)
        self.api._bucket_hashes = {}

    def test_falls_back_to_local_guess_when_hash_unknown(self) -> None:
        template, key = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.assertEqual(template, "GET /guilds/:id/scheduled-events/:id")
        self.assertEqual(key, "GET /guilds/999/scheduled-events/:id")

    def test_uses_learned_hash_once_known(self) -> None:
        template, _ = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.api._bucket_hashes[template] = "abcXYZ"

        _, key = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/777")
        self.assertEqual(key, "GET #abcXYZ:999")

    def test_hash_based_key_still_separates_different_major_params(self) -> None:
        # Regression test: switching to the hash must not accidentally merge
        # buckets across guilds/channels/webhooks - only the minor param collapses.
        template, _ = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.api._bucket_hashes[template] = "abcXYZ"

        _, key_guild_999 = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/1")
        _, key_guild_111 = self.api._resolve_bucket_key("GET", "/guilds/111/scheduled-events/2")

        self.assertNotEqual(key_guild_999, key_guild_111)

    def test_hash_based_key_has_no_major_suffix_for_global_routes(self) -> None:
        template, _ = self.api._resolve_bucket_key("GET", "/stickers/123")
        self.api._bucket_hashes[template] = "abcXYZ"

        _, key = self.api._resolve_bucket_key("GET", "/stickers/456")
        self.assertEqual(key, "GET #abcXYZ")


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

    def test_reset_rewinds_raw_stream_not_wrapped_in_file(self) -> None:
        import io

        buffer = io.BytesIO(b"abcdef")

        multidata = MultipartData()
        multidata.attach("files[0]", buffer, filename="raw.bin")

        buffer.read()  # simulate the first (failed) send consuming the stream
        self.assertEqual(buffer.read(), b"")

        multidata.reset()
        self.assertEqual(buffer.read(3), b"abc")


class _FakeHTTPClient:
    """ Stands in for HTTPClient in query() tests: replays canned responses in order. """
    def __init__(self, responses: list[HTTPResponse]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def request(self, method, url, *, res_method="json", **kwargs) -> HTTPResponse:
        self.calls.append((method, url))
        return self._responses.pop(0)


def _fake_response(
    *, bucket_hash: str | None = None, status: int = 200, response: dict | None = None,
) -> HTTPResponse:
    headers = {
        "X-RateLimit-Limit": "5",
        "X-RateLimit-Remaining": "4",
        "X-RateLimit-Reset": "0",
        "X-RateLimit-Reset-After": "1.0",
    }
    if bucket_hash:
        headers["X-RateLimit-Bucket"] = bucket_hash

    return HTTPResponse(
        status=status, response=response if response is not None else {},
        reason=None, res_method="json", headers=headers,
    )


class TestQuerySelfCorrectsBucketKey(unittest.IsolatedAsyncioTestCase):
    """ End-to-end test of query()'s retry loop wiring _resolve_bucket_key() and
    _bucket_hashes together - the actual behavior change, not just the pure helpers. """

    def _make_api(self, responses: list[HTTPResponse]) -> DiscordAPI:
        api = object.__new__(DiscordAPI)
        api._default_headers = {}
        api.api_url = "https://discord.test/api/v10"
        api.base_url = "https://discord.test/api"
        api._buckets = {}
        api._bucket_hashes = {}
        api._global_ratelimit = GlobalRatelimit()
        api.http = _FakeHTTPClient(responses)
        return api

    async def test_first_call_uses_local_guess_and_learns_the_hash(self) -> None:
        api = self._make_api([_fake_response(bucket_hash="hashABC")])

        await api.query("GET", "/guilds/999/scheduled-events/555")

        self.assertEqual(api._bucket_hashes["GET /guilds/:id/scheduled-events/:id"], "hashABC")
        self.assertIn("GET /guilds/999/scheduled-events/:id", api._buckets)

    async def test_second_call_to_same_route_shape_uses_learned_hash(self) -> None:
        api = self._make_api([
            _fake_response(bucket_hash="hashABC"),
            _fake_response(bucket_hash="hashABC"),
        ])

        await api.query("GET", "/guilds/999/scheduled-events/555")
        await api.query("GET", "/guilds/999/scheduled-events/777")

        # The second, different-event-id request reused the hash-based key
        # instead of creating yet another fragmented per-event bucket.
        self.assertIn("GET #hashABC:999", api._buckets)

    async def test_different_guild_still_gets_its_own_bucket_after_hash_learned(self) -> None:
        api = self._make_api([
            _fake_response(bucket_hash="hashABC"),  # teaches the hash (local-guess key)
            _fake_response(bucket_hash="hashABC"),  # already knows the hash by now
        ])

        await api.query("GET", "/guilds/999/scheduled-events/555")
        await api.query("GET", "/guilds/111/scheduled-events/1")

        # The first call (the one that taught us the hash) still used the local guess.
        self.assertIn("GET /guilds/999/scheduled-events/:id", api._buckets)
        # The second, different-guild call already knew the hash and got its own
        # hash-based bucket - not merged with guild 999's.
        self.assertIn("GET #hashABC:111", api._buckets)
        self.assertNotIn("GET #hashABC:999", api._buckets)

    async def test_hash_learned_mid_call_does_not_orphan_a_429_cooldown(self) -> None:
        # Regression test: the bucket key used to be re-resolved on every retry
        # iteration. A 429 (which also carries X-RateLimit-Bucket) would teach the
        # hash and set its cooldown on the pre-hash Ratelimit object in the same
        # breath - the next iteration then resolved to a *different*, freshly
        # created hash-based object with no cooldown on it, so the retry fired
        # immediately instead of respecting retry_after. The key must be resolved
        # once for the whole call so the cooldown set on attempt 1 is still the
        # object attempt 2 waits on.
        api = self._make_api([
            _fake_response(status=429, bucket_hash="hashABC", response={
                "retry_after": 0.05, "global": False,
            }),
            _fake_response(status=200, bucket_hash="hashABC"),
        ])

        start = asyncio.get_running_loop().time()
        await api.query("GET", "/guilds/999/scheduled-events/555")
        elapsed = asyncio.get_running_loop().time() - start

        # Ratelimit.__aenter__ floors any wait at ~0.2s, so a real wait proves the
        # cooldown carried over; an orphaned cooldown would retry near-instantly.
        self.assertGreaterEqual(elapsed, 0.15)

        # Only the local-guess key was ever used for this call - the hash it
        # learned along the way didn't cause a mid-call switch to a second,
        # unrelated Ratelimit object.
        self.assertEqual(list(api._buckets), ["GET /guilds/999/scheduled-events/:id"])


if __name__ == "__main__":
    unittest.main()
