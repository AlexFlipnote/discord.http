import unittest

from types import SimpleNamespace

from discord_http.view import AttachmentComponent


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


if __name__ == "__main__":
    unittest.main()
