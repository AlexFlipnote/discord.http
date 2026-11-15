import asyncio
import contextlib
import logging
import unittest

from yarl import URL

from discord_http import Client
from discord_http.http import DiscordAPI, HTTPResponse
from discord_http.message import PartialMessage


class _Recorder:
    """ Stands in for the HTTP client, resolving the URL the way aiohttp would before sending it. """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict]] = []
        self.status = 204

    async def request(self, method, url, *, res_method="json", **kwargs) -> HTTPResponse:  # noqa: ANN001, ANN003
        resolved = URL(url)
        self.sent.append((method, resolved.raw_path_qs, kwargs.get("headers", {})))
        return HTTPResponse(
            status=self.status,
            response='{"retry_after": 0.001}' if self.status == 429 else ({} if res_method == "json" else ""),
            reason="", res_method=res_method, headers={},  # type: ignore[arg-type]
        )


class _PathTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.client = Client(token="a.b.c", logging_level=logging.CRITICAL, loop=asyncio.get_event_loop())
        for task in self.client._background_tasks:
            task.cancel()
        self.http = _Recorder()
        self.client.state.http = self.http  # type: ignore[assignment]

    def message(self) -> PartialMessage:
        return PartialMessage(state=self.client.state, id=222, channel_id=111)


class TestValidatePath(unittest.TestCase):
    def test_ordinary_routes_pass(self) -> None:
        for path in (
            "/channels/1/messages/2",
            "/guilds/1/members?limit=1000&after=0",
            "/channels/1/messages/2/reactions/%F0%9F%98%80/@me",
            "/webhooks/1/some.token-with_dots/messages/@original",
            "/invites/..%2Fusers",
        ):
            DiscordAPI._validate_path(path)

    def test_dot_segments_are_refused(self) -> None:
        for path in (
            "/invites/../users/@me",
            "/invites/..",
            "/channels/1/./messages",
            "/invites/%2e%2e/users/@me",
            "/invites/%2E%2e/users/@me",
        ):
            with self.assertRaises(ValueError, msg=path):
                DiscordAPI._validate_path(path)

    def test_fragment_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            DiscordAPI._validate_path("/channels/1/messages/2/reactions/x#/@me")


class TestReactionRoutes(_PathTest):
    async def test_emoji_cannot_leave_the_reaction_route(self) -> None:
        await self.message().add_reaction("../../../../../guilds/9/bans/5#")
        method, path, _ = self.http.sent[-1]
        self.assertEqual(method, "PUT")
        self.assertTrue(path.startswith("/api/v10/channels/111/messages/222/reactions/"), path)
        self.assertTrue(path.endswith("/@me"), path)

    async def test_emoji_cannot_add_query_parameters(self) -> None:
        await self.message().add_reaction("x?type=1&a=")
        self.assertNotIn("?", self.http.sent[-1][1])

    async def test_keycap_emoji_keeps_its_hash(self) -> None:
        await self.message().add_reaction("#️⃣")
        self.assertEqual(
            self.http.sent[-1][1],
            "/api/v10/channels/111/messages/222/reactions/%23%EF%B8%8F%E2%83%A3/@me"
        )

    async def test_custom_emoji_still_resolves(self) -> None:
        await self.message().add_reaction("<:blob:123456789012345678>")
        self.assertEqual(
            URL(self.http.sent[-1][1]).path,
            "/api/v10/channels/111/messages/222/reactions/blob:123456789012345678/@me"
        )

    async def test_remove_reaction_defaults_to_the_bot(self) -> None:
        await self.message().remove_reaction("ok")
        self.assertEqual(self.http.sent[-1][:2], ("DELETE", "/api/v10/channels/111/messages/222/reactions/ok/@me"))

    async def test_remove_reaction_for_a_user(self) -> None:
        await self.message().remove_reaction("ok", user_id=5)
        self.assertEqual(self.http.sent[-1][1], "/api/v10/channels/111/messages/222/reactions/ok/5")


class TestCodeAndTokenRoutes(_PathTest):
    async def test_invite_code_stays_one_segment(self) -> None:
        with self.assertRaises(ValueError):
            await self.client.get_partial_invite("..").delete()
        self.assertEqual(self.http.sent, [])

        # The fake response is not an invite, only the request matters here
        with contextlib.suppress(KeyError):
            await self.client.get_partial_invite("../users/@me?x=1").delete()
        path = self.http.sent[-1][1]
        self.assertTrue(path.startswith("/api/v10/invites/..%2Fusers%2F"), path)
        self.assertEqual(path.count("/"), 4, path)
        self.assertNotIn("?", path)

    async def test_webhook_token_stays_one_segment(self) -> None:
        webhook = self.client.get_partial_webhook(1, webhook_token="x/../../../v10/channels/7/messages#")
        await webhook.send("hi", wait=False)
        _, path, headers = self.http.sent[-1]
        self.assertTrue(path.startswith("/api/webhooks/1/x%2F"), path)
        self.assertEqual(path.partition("?")[0].count("/"), 4, path)
        self.assertNotIn("Authorization", headers)

    async def test_bot_routes_keep_the_bot_token(self) -> None:
        await self.client.state.query("GET", "/users/@me", res_method="text")
        self.assertEqual(self.http.sent[-1][2]["Authorization"], "Bot a.b.c")


class TestIdCoercion(_PathTest):
    async def test_non_numeric_ids_are_refused(self) -> None:
        channel = self.client.get_partial_channel(111)
        with self.assertRaises(ValueError):
            await channel.fetch_message("../../9/messages/8")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            await channel.remove_thread_member("../../../guilds/9/members/5")  # type: ignore[arg-type]
        self.assertEqual(self.http.sent, [])


class TestTokensStayOutOfLogs(_PathTest):
    async def test_ratelimit_warning_hides_the_webhook_token(self) -> None:
        self.http.status = 429
        webhook = self.client.get_partial_webhook(1, webhook_token="SECRET-TOKEN")

        logger = logging.getLogger("discord_http.http")
        with self.assertLogs(logger, level="DEBUG") as logs, self.assertRaises(Exception):
            await webhook.delete()

        output = "\n".join(logs.output)
        self.assertIn("/webhooks/1/:token", output)
        self.assertNotIn("SECRET-TOKEN", output)


if __name__ == "__main__":
    unittest.main()
