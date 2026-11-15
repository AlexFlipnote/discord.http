import logging
import unittest

from types import SimpleNamespace

from aiohttp import web
from aiohttp.test_utils import TestServer

from discord_http import Client
from discord_http.http import HTTPClient
from discord_http.view import AttachmentComponent

BIG = b"x" * (256 * 1024)


class TestMaxSize(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        async def sized(_request: web.Request) -> web.Response:
            return web.Response(body=BIG)

        async def chunked(_request: web.Request) -> web.StreamResponse:
            # No Content-Length, the size only shows while reading
            response = web.StreamResponse()
            await response.prepare(_request)
            for _ in range(4):
                await response.write(BIG[:65536])
            return response

        async def small_json(_request: web.Request) -> web.Response:
            return web.json_response({"ok": True})

        app = web.Application()
        app.router.add_get("/sized", sized)
        app.router.add_get("/chunked", chunked)
        app.router.add_get("/json", small_json)

        self.server = TestServer(app)
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)

        self.http = HTTPClient()
        await self.http._create_session()
        self.addAsyncCleanup(self.http._close_session)

    def url(self, path: str) -> str:
        return str(self.server.make_url(path))

    async def test_unlimited_by_default(self) -> None:
        r = await self.http.request("GET", self.url("/sized"), res_method="read")
        self.assertEqual(len(r.response), len(BIG))

    async def test_body_within_the_limit_is_returned(self) -> None:
        r = await self.http.request("GET", self.url("/sized"), res_method="read", max_size=len(BIG))
        self.assertEqual(r.response, BIG)

        r = await self.http.request("GET", self.url("/json"), res_method="json", max_size=1024)
        self.assertEqual(r.response, {"ok": True})

    async def test_declared_size_over_the_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            await self.http.request("GET", self.url("/sized"), res_method="read", max_size=1024)

    async def test_undeclared_size_over_the_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            await self.http.request("GET", self.url("/chunked"), res_method="read", max_size=100_000)


class TestExternalMediaGoesThroughTheProxy(unittest.IsolatedAsyncioTestCase):
    async def _fetched(self, media: dict, **kwargs) -> str:
        urls: list[str] = []

        async def request(_method: str, url: str, **_kwargs: object) -> SimpleNamespace:
            urls.append(url)
            return SimpleNamespace(status=200, response=b"")

        state = SimpleNamespace(http=SimpleNamespace(request=request))
        await AttachmentComponent(state=state, data={"media": media}).fetch(**kwargs)  # type: ignore[arg-type]
        return urls[0]

    async def test_user_chosen_url_is_never_contacted(self) -> None:
        media = {"url": "http://internal.example/secret", "proxy_url": "https://media.discordapp.net/external/x"}
        self.assertEqual(await self._fetched(media), media["proxy_url"])

    async def test_uploaded_attachment_still_uses_its_own_url(self) -> None:
        media = {
            "url": "https://cdn.discordapp.com/attachments/1/2/a.png",
            "proxy_url": "https://media.discordapp.net/attachments/1/2/a.png",
            "attachment_id": "2",
        }
        self.assertEqual(await self._fetched(media), media["url"])
        self.assertEqual(await self._fetched(media, use_cached=True), media["proxy_url"])


class TestDefaultAllowedMentions(unittest.IsolatedAsyncioTestCase):
    def _client(self, **kwargs) -> Client:
        client = Client(token="a.b.c", logging_level=logging.CRITICAL, **kwargs)
        for task in client._background_tasks:
            task.cancel()
        return client

    async def test_mass_mentions_are_off_unless_asked_for(self) -> None:
        parse = self._client()._default_allowed_mentions.to_dict()["parse"]
        self.assertEqual(parse, ["users"])

    async def test_explicit_setting_is_kept(self) -> None:
        from discord_http import AllowedMentions

        client = self._client(allowed_mentions=AllowedMentions.all())
        self.assertEqual(sorted(client._default_allowed_mentions.to_dict()["parse"]), ["everyone", "roles", "users"])


if __name__ == "__main__":
    unittest.main()
