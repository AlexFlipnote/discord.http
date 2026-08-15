import unittest

from discord_http import Webhook


class FakeState:
    pass


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


if __name__ == "__main__":
    unittest.main()
