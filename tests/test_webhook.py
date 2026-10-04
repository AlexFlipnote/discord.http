import unittest

import orjson

from discord_http import AllowedMentions, PartialWebhook, Webhook


class FakeState:
    pass


class FakeResponse:
    def __init__(self, response):
        self.response = response


class RecordingState:
    def __init__(self):
        self.calls = []

    async def query(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return FakeResponse(None)


class FakeBot:
    _default_allowed_mentions = AllowedMentions()


def _payload_json(writer) -> dict:
    for part, *_ in writer._parts:
        if part.headers.get("Content-Type") == "application/json":
            return orjson.loads(part._value)
    raise AssertionError("payload_json not found")


class TestWebhookIdResolution(unittest.TestCase):
    """ Regression test (found via live testing, not review): Webhook.id used
    to prefer `application_id` over the webhook's own `id`. Discord always
    sets `application_id` to the creating bot's application ID on bot-created
    webhooks, so this silently pointed every send() call at the wrong URL
    (401 Invalid Webhook Token) for essentially every webhook a bot creates
    for itself. """

    def test_id_prefers_the_webhooks_own_id(self) -> None:
        webhook = Webhook(state=FakeState(), data={
            "id": "111", "application_id": "222",
            "channel_id": "1", "guild_id": "2", "name": "hook", "token": "tok",
        })
        self.assertEqual(webhook.id, 111)
        self.assertEqual(webhook.application_id, 222)

    def test_falls_back_to_application_id_when_id_missing(self) -> None:
        webhook = Webhook(state=FakeState(), data={
            "application_id": "222",
            "channel_id": "1", "guild_id": "2", "name": "hook", "token": "tok",
        })
        self.assertEqual(webhook.id, 222)


class TestWebhookSendForumThread(unittest.IsolatedAsyncioTestCase):
    async def test_thread_name_and_applied_tags(self) -> None:
        state = RecordingState()
        state.bot = FakeBot()
        webhook = PartialWebhook(state=state, id=1, token="tok")
        await webhook.send("hi", thread_name="post", applied_tags=[10, 11], wait=False)

        method, path, kwargs = state.calls[0]
        self.assertEqual(path, "/webhooks/1/tok")
        self.assertEqual(kwargs["params"], {})

        payload = _payload_json(kwargs["data"])
        self.assertEqual(payload["thread_name"], "post")
        self.assertEqual(payload["applied_tags"], ["10", "11"])

    async def test_query_params(self) -> None:
        state = RecordingState()
        state.bot = FakeBot()
        webhook = PartialWebhook(state=state, id=1, token="tok")
        await webhook.send("hi", thread_id=5, view=None, wait=False)

        kwargs = state.calls[0][2]
        self.assertEqual(kwargs["params"], {"thread_id": "5", "with_components": "true"})
        self.assertNotIn("thread_name", _payload_json(kwargs["data"]))


if __name__ == "__main__":
    unittest.main()
