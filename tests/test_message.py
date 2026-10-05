import unittest

import orjson

from discord_http import (
    BaseThemeType, IntegrationType, InteractionType,
    Message, MessageFlags, PartialChannel, PartialRole, PartialUser
)

from _fake_client import FakeBot


class FakeState:
    cache = None

    def __init__(self):
        self.bot = FakeBot(self)


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


class TestMessageView(unittest.TestCase):
    def test_components_build_a_view_when_read(self) -> None:
        from discord_http import View

        message = Message(state=FakeState(), data=_message_data(components=[
            {"type": 1, "components": [{"type": 2, "style": 1, "label": "x", "custom_id": "btn"}]}
        ]))
        view = message.view
        self.assertIsInstance(view, View)
        self.assertEqual(view.to_dict()[0]["components"][0]["custom_id"], "btn")  # type: ignore[union-attr]

    def test_no_components_is_none(self) -> None:
        self.assertIsNone(Message(state=FakeState(), data=_message_data()).view)
        self.assertIsNone(Message(state=FakeState(), data=_message_data(components=[])).view)


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

    def test_to_dict_flags_is_json_serializable(self) -> None:
        message = Message(state=FakeState(), data=_message_data(attachments=[{
            "id": "1", "filename": "clip.mp4", "size": 100,
            "url": "https://x", "proxy_url": "https://x",
            "flags": 4,
        }]))
        attachment = message.attachments[0]
        data = attachment.to_dict()
        self.assertEqual(data["flags"], 4)
        self.assertIsInstance(data["flags"], int)
        orjson.dumps(data)  # raises TypeError if any value isn't JSON-serializable


class FakeCache:
    def get_guild(self, guild_id):
        return None

    def get_channel_thread(self, *, guild_id, channel_id):
        return None


class CachedFakeState(FakeState):
    cache = FakeCache()


class TestMessageMentions(unittest.TestCase):
    def test_role_mentions_use_mention_roles(self) -> None:
        # No message content intent, so content is empty
        message = Message(
            state=CachedFakeState(),
            data=_message_data(content="", mention_roles=["10", "11"]),
        )
        message.guild_id = 5
        roles = message.role_mentions
        self.assertTrue(all(isinstance(r, PartialRole) for r in roles))
        self.assertEqual([r.id for r in roles], [10, 11])

    def test_role_mentions_fall_back_to_content(self) -> None:
        message = Message(state=CachedFakeState(), data=_message_data(content="<@&123456789012345678>"))
        message.guild_id = 5
        self.assertEqual([r.id for r in message.role_mentions], [123456789012345678])

    def test_channel_mentions_prefer_mention_channels(self) -> None:
        message = Message(state=CachedFakeState(), data=_message_data(
            content="<#123456789012345678>",
            mention_channels=[{"id": "20", "guild_id": "30", "type": 0, "name": "general"}],
        ))
        channels = message.channel_mentions
        self.assertEqual(len(channels), 1)
        self.assertIsInstance(channels[0], PartialChannel)
        self.assertEqual((channels[0].id, channels[0].guild_id), (20, 30))

    def test_channel_mentions_from_content(self) -> None:
        message = Message(state=CachedFakeState(), data=_message_data(content="<#123456789012345678>"))
        self.assertEqual([c.id for c in message.channel_mentions], [123456789012345678])


class TestMessageContentVariants(unittest.TestCase):
    def test_pretty_content_resolves_known_mentions(self) -> None:
        message = Message(state=CachedFakeState(), data=_message_data(
            content="hi <@123456789012345678> and <@!123456789012345678> in <#223456789012345678>",
            mentions=[{
                "id": "123456789012345678", "username": "bob",
                "global_name": "Bobby", "discriminator": "0", "avatar": None,
            }],
            mention_channels=[{"id": "223456789012345678", "guild_id": "30", "type": 0, "name": "general"}],
        ))
        self.assertEqual(message.pretty_content, "hi @Bobby and @Bobby in #general")

    def test_pretty_content_without_cache(self) -> None:
        message = Message(state=FakeState(), data=_message_data(
            content="Hi there <@!86477779717066752> </test_ping:1542872400176226308> </role add:1542872400176226308>",
            mentions=[{
                "id": "86477779717066752", "username": "alexflipnote",
                "global_name": "AlexFlipnote", "discriminator": "0", "avatar": None,
            }],
            mention_roles=[],
        ))
        self.assertEqual(message.pretty_content, "Hi there @AlexFlipnote /test_ping /role add")

    def test_pretty_content_keeps_unresolved_mentions(self) -> None:
        content = "<@&323456789012345678> <#423456789012345678> <@523456789012345678>"
        message = Message(state=CachedFakeState(), data=_message_data(content=content))
        message.guild_id = 5
        self.assertEqual(message.pretty_content, content)

    def test_escaped_content(self) -> None:
        message = Message(state=FakeState(), data=_message_data(content="**bold** <@1> `code`"))
        self.assertEqual(message.escaped_content, r"\*\*bold\*\* \<@1\> \`code\`")


class TestMessageInteractionMetadata(unittest.TestCase):
    def test_parses_modal_submit_metadata(self) -> None:
        user = {"id": "3", "username": "bob", "discriminator": "0001", "avatar": None}
        message = Message(state=FakeState(), data=_message_data(interaction_metadata={
            "id": "50", "type": 5, "user": user,
            "authorizing_integration_owners": {"0": "100", "1": "3"},
            "original_response_message_id": "60",
            "triggering_interaction_metadata": {
                "id": "51", "type": 2, "user": user,
                "authorizing_integration_owners": {"1": "3"},
                "target_user": {"id": "4", "username": "al", "discriminator": "0001", "avatar": None},
                "target_message_id": "70",
            },
        }))
        interaction = message.interaction
        self.assertEqual(interaction.type, InteractionType.modal_submit)
        self.assertEqual(interaction.authorizing_integration_owners, {
            IntegrationType.guild: 100, IntegrationType.user: 3,
        })
        self.assertEqual(interaction.original_response_message_id, 60)
        self.assertIsNone(interaction.target_user)

        triggering = interaction.triggering_interaction_metadata
        self.assertEqual(triggering.id, 51)
        self.assertEqual(triggering.target_user.id, 4)
        self.assertEqual(triggering.target_message_id, 70)
        self.assertIsNone(triggering.triggering_interaction_metadata)

    def test_parses_component_metadata(self) -> None:
        message = Message(state=FakeState(), data=_message_data(interaction_metadata={
            "id": "50", "type": 3,
            "user": {"id": "3", "username": "bob", "discriminator": "0001", "avatar": None},
            "interacted_message_id": "80",
        }))
        self.assertEqual(message.interaction.interacted_message_id, 80)
        self.assertEqual(message.interaction.authorizing_integration_owners, {})


class TestMessageExtraFields(unittest.TestCase):
    def test_parses_top_level_fields(self) -> None:
        message = Message(state=FakeState(), data=_message_data(
            nonce="abc", webhook_id="7", application_id="8", position=4, flags=1 << 2,
            activity={"type": 1, "party_id": "p"},
            shared_client_theme={
                "colors": ["5865F2", "7258F2"], "gradient_angle": 0,
                "base_mix": 58, "base_theme": 1,
            },
        ))
        self.assertEqual(message.nonce, "abc")
        self.assertEqual(message.webhook_id, 7)
        self.assertEqual(message.application_id, 8)
        self.assertEqual(message.position, 4)
        self.assertIn(MessageFlags.suppress_embeds, message.flags)
        self.assertEqual(message.activity.party_id, "p")
        self.assertEqual(message.shared_client_theme.base_theme, BaseThemeType.dark)
        self.assertEqual(message.shared_client_theme.to_dict()["colors"], ["5865F2", "7258F2"])

    def test_defaults_when_absent(self) -> None:
        message = Message(state=FakeState(), data=_message_data())
        self.assertIsNone(message.nonce)
        self.assertIsNone(message.webhook_id)
        self.assertIsNone(message.thread)
        self.assertIsNone(message.activity)
        self.assertIsNone(message.shared_client_theme)
        self.assertEqual(int(message.flags), 0)

    def test_reaction_count_details(self) -> None:
        message = Message(state=FakeState(), data=_message_data(reactions=[{
            "count": 3, "me": False, "me_burst": False, "burst_colors": [],
            "emoji": {"id": None, "name": "x"},
            "count_details": {"burst": 1, "normal": 2},
        }]))
        reaction = message.reactions[0]
        self.assertEqual(reaction.normal_count, 2)
        self.assertEqual(reaction.burst_count, 1)


if __name__ == "__main__":
    unittest.main()
