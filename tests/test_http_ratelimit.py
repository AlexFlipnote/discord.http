import asyncio
import unittest

from types import SimpleNamespace

from discord_http.http import DiscordAPI, GlobalRatelimit, HTTPResponse, Ratelimit
from discord_http.utils import MultipartData


class TestGlobalRatelimitConstruction(unittest.TestCase):
    def test_construction_outside_a_running_loop_does_not_raise(self) -> None:
        # Must not eagerly call get_running_loop() - this can run before any loop exists
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
        # Must not evict mid-429-cooldown, or the next request starts falsely-fresh
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
        # The actual "notice a divergence" signal bucket_hash exists for
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
        # A real global 429 must pause ALL requests, not just the one that triggered it
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
        # The old keyword-list version never collapsed this, fragmenting per event
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
        # Only a whole segment that is purely digits counts as an id
        key = self.api._get_bucket_key("PATCH", "/webhooks/123456/abcToken123/messages/@original")
        self.assertEqual(key, "PATCH /webhooks/123456/abcToken123/messages/@original")


class TestRouteTemplateAndMajorParam(unittest.TestCase):
    def setUp(self) -> None:
        self.api = object.__new__(DiscordAPI)

    def test_route_template_collapses_major_param_too(self) -> None:
        # Unlike _get_bucket_key, the hash is the same regardless of which guild
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
        template, key, fallback = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.assertEqual(template, "GET /guilds/:id/scheduled-events/:id")
        self.assertEqual(key, "GET /guilds/999/scheduled-events/:id")
        self.assertEqual(fallback, key)

    def test_uses_learned_hash_once_known(self) -> None:
        template, _, _ = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.api._bucket_hashes[template] = "abcXYZ"

        _, key, fallback = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/777")
        self.assertEqual(key, "GET #abcXYZ:999")
        self.assertEqual(fallback, "GET /guilds/999/scheduled-events/:id")

    def test_hash_based_key_still_separates_different_major_params(self) -> None:
        # The hash must not merge buckets across guilds/channels/webhooks
        template, _, _ = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/555")
        self.api._bucket_hashes[template] = "abcXYZ"

        _, key_guild_999, _ = self.api._resolve_bucket_key("GET", "/guilds/999/scheduled-events/1")
        _, key_guild_111, _ = self.api._resolve_bucket_key("GET", "/guilds/111/scheduled-events/2")

        self.assertNotEqual(key_guild_999, key_guild_111)

    def test_hash_based_key_has_no_major_suffix_for_global_routes(self) -> None:
        template, _, _ = self.api._resolve_bucket_key("GET", "/stickers/123")
        self.api._bucket_hashes[template] = "abcXYZ"

        _, key, _ = self.api._resolve_bucket_key("GET", "/stickers/456")
        self.assertEqual(key, "GET #abcXYZ")


class TestGetRatelimitMigration(unittest.IsolatedAsyncioTestCase):
    async def test_migrates_existing_bucket_state_to_the_new_key(self) -> None:
        # Used to reset to limit=1 defaults instead of keeping the real known state
        api = object.__new__(DiscordAPI)
        api._buckets = {}

        old = api.get_ratelimit("GET /guilds/999/scheduled-events/:id")
        old.limit = 5
        old.remaining = 3

        migrated = api.get_ratelimit("GET #abcXYZ:999", migrate_from="GET /guilds/999/scheduled-events/:id")

        self.assertIs(migrated, old)
        self.assertEqual(migrated.limit, 5)
        self.assertEqual(migrated.remaining, 3)
        self.assertEqual(migrated.key, "GET #abcXYZ:999")
        self.assertNotIn("GET /guilds/999/scheduled-events/:id", api._buckets)

    async def test_no_migration_source_creates_a_fresh_bucket(self) -> None:
        api = object.__new__(DiscordAPI)
        api._buckets = {}

        rl = api.get_ratelimit("GET #abcXYZ:999", migrate_from="GET /guilds/999/scheduled-events/:id")

        self.assertEqual(rl.limit, 1)
        self.assertEqual(rl.remaining, 1)


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
    *,
    bucket_hash: str | None = None,
    status: int = 200,
    response: dict | None = None,
    limit: str = "5",
    remaining: str = "4",
    reset: str = "0",
) -> HTTPResponse:
    headers = {
        "X-RateLimit-Limit": limit,
        "X-RateLimit-Remaining": remaining,
        "X-RateLimit-Reset": reset,
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

        # Reused the hash-based key instead of fragmenting per event id
        self.assertIn("GET #hashABC:999", api._buckets)

    async def test_different_guild_still_gets_its_own_bucket_after_hash_learned(self) -> None:
        api = self._make_api([
            _fake_response(bucket_hash="hashABC"),  # teaches the hash (local-guess key)
            _fake_response(bucket_hash="hashABC"),  # already knows the hash by now
        ])

        await api.query("GET", "/guilds/999/scheduled-events/555")
        await api.query("GET", "/guilds/111/scheduled-events/1")

        # First call (taught the hash) kept the local guess; second already knew it
        self.assertIn("GET /guilds/999/scheduled-events/:id", api._buckets)
        self.assertIn("GET #hashABC:111", api._buckets)
        self.assertNotIn("GET #hashABC:999", api._buckets)

    async def test_hash_learned_mid_call_does_not_orphan_a_429_cooldown(self) -> None:
        # Re-resolving the key per retry used to drop the 429 cooldown mid-loop
        api = self._make_api([
            _fake_response(status=429, bucket_hash="hashABC", response={
                "retry_after": 0.05, "global": False,
            }),
            _fake_response(status=200, bucket_hash="hashABC"),
        ])

        start = asyncio.get_running_loop().time()
        with self.assertLogs("discord_http", level="WARNING"):
            await api.query("GET", "/guilds/999/scheduled-events/555")
        elapsed = asyncio.get_running_loop().time() - start

        # __aenter__ floors any wait at ~0.2s; an orphaned cooldown retries near-instantly
        self.assertGreaterEqual(elapsed, 0.15)

        # Only the local-guess key was ever used - no mid-call switch to a second object
        self.assertEqual(list(api._buckets), ["GET /guilds/999/scheduled-events/:id"])

    async def test_switching_to_hash_key_preserves_the_bucket_state(self) -> None:
        # Used to reset to limit=1 instead of carrying over the real known state
        api = self._make_api([
            _fake_response(bucket_hash="hashABC", limit="5", remaining="4", reset="100"),
            _fake_response(bucket_hash="hashABC", limit="5", remaining="3", reset="100"),
        ])

        await api.query("PATCH", "/channels/570916125672603659/messages/111")
        await api.query("PATCH", "/channels/570916125672603659/messages/222")

        self.assertEqual(list(api._buckets), ["PATCH #hashABC:570916125672603659"])
        rl = api._buckets["PATCH #hashABC:570916125672603659"]
        self.assertEqual(rl.limit, 5)
        self.assertEqual(rl.remaining, 3)

    async def test_ratelimit_warning_shows_the_normalized_path_not_the_raw_id(self) -> None:
        # Should read as "this counts as one bucket", not the one id that triggered it
        api = self._make_api([
            _fake_response(status=429, response={"retry_after": 0.01, "global": False}),
            _fake_response(status=200),
        ])

        with self.assertLogs("discord_http", level="WARNING") as logs:
            await api.query("GET", "/guilds/999/scheduled-events/555")

        message = "\n".join(logs.output)
        self.assertIn("GET /guilds/999/scheduled-events/:id", message)
        self.assertNotIn("555", message)

    async def test_ratelimit_warning_stays_readable_even_once_hash_is_known(self) -> None:
        # Once the key has switched to the opaque hash internally, must still print the path
        api = self._make_api([
            _fake_response(bucket_hash="abcXYZ"),  # teaches the hash
            _fake_response(
                status=429, bucket_hash="abcXYZ",
                response={"retry_after": 0.01, "global": False},
            ),
            _fake_response(status=200, bucket_hash="abcXYZ"),
        ])

        await api.query("GET", "/guilds/999/scheduled-events/555")

        with self.assertLogs("discord_http", level="WARNING") as logs:
            await api.query("GET", "/guilds/999/scheduled-events/777")

        message = "\n".join(logs.output)
        self.assertIn("GET /guilds/999/scheduled-events/:id", message)
        self.assertNotIn("#", message)
        self.assertNotIn("abcXYZ", message)


if __name__ == "__main__":
    unittest.main()
