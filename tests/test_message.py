import unittest

from discord_http import Message, PartialUser


class FakeState:
    pass


def _message_data(**overrides):
    data = {
        "id": "1", "channel_id": "2", "type": 0, "content": "hi",
        "author": {"id": "3", "username": "bob", "discriminator": "0001", "avatar": None},
    }
    data.update(overrides)
    return data


class TestMessageCallParticipants(unittest.TestCase):
    """ Regression test: MessageCall.participants used to be raw ints, unlike
    every sibling ID-list field added in the same session
    (Attachment.clip_participants, Invite.fetch_target_users()). """

    def test_participants_are_partial_users(self) -> None:
        message = Message(state=FakeState(), data=_message_data(call={
            "participants": ["10", "11"], "ended_timestamp": None,
        }))
        self.assertIsNotNone(message.call)
        self.assertTrue(all(isinstance(p, PartialUser) for p in message.call.participants))
        self.assertEqual([p.id for p in message.call.participants], [10, 11])

    def test_no_call_when_absent(self) -> None:
        message = Message(state=FakeState(), data=_message_data())
        self.assertIsNone(message.call)


class TestMessageRoleSubscriptionData(unittest.TestCase):
    def test_parses_role_subscription_data(self) -> None:
        message = Message(state=FakeState(), data=_message_data(role_subscription_data={
            "role_subscription_listing_id": "5", "tier_name": "Gold",
            "total_months_subscribed": 3, "is_renewal": True,
        }))
        self.assertIsNotNone(message.role_subscription_data)
        self.assertEqual(message.role_subscription_data.tier_name, "Gold")
        self.assertTrue(message.role_subscription_data.is_renewal)


class TestAttachmentNewFields(unittest.TestCase):
    def test_placeholder_and_clip_fields(self) -> None:
        message = Message(state=FakeState(), data=_message_data(attachments=[{
            "id": "1", "filename": "clip.mp4", "size": 100,
            "url": "https://x", "proxy_url": "https://x",
            "placeholder": "abc", "placeholder_version": 1,
            "clip_created_at": "2024-01-01T00:00:00.000000+00:00",
            "clip_participants": [
                {"id": "10", "username": "a", "discriminator": "0001", "avatar": None}
            ],
        }]))
        attachment = message.attachments[0]
        self.assertEqual(attachment.placeholder, "abc")
        self.assertEqual(attachment.placeholder_version, 1)
        self.assertIsNotNone(attachment.clip_created_at)
        self.assertEqual(len(attachment.clip_participants), 1)
        self.assertEqual(attachment.clip_participants[0].name, "a")


if __name__ == "__main__":
    unittest.main()
