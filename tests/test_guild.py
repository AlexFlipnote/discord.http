import unittest

from datetime import UTC, datetime

from discord_http import (
    ScheduledEvent, ScheduledEventRecurrenceRule,
    ScheduledEventRecurrenceFrequency, ScheduledEventRecurrenceWeekday,
    GuildIncidentsData, WelcomeScreen, GuildWidgetSettings, GuildTemplate,
    GuildPreview, GuildOnboarding, OnboardingPromptOption,
    OnboardingPromptType, OnboardingMode, NSFWLevel, PremiumTier, MFALevel,
    Guild, PartialChannel,
)
from discord_http.guild import GuildWidget


class FakeCache:
    def get_guild(self, guild_id):
        return None


class FakeState:
    def __init__(self):
        self.cache = FakeCache()


def _scheduled_event_data(**overrides):
    data = {
        "id": "1", "guild_id": "2", "name": "evt",
        "privacy_level": 2, "status": 1, "entity_type": 2,
        "scheduled_start_time": "2024-01-01T00:00:00.000000+00:00",
    }
    data.update(overrides)
    return data


class TestScheduledEventChannel(unittest.TestCase):
    """ Regression tests: `.channel` used to compare `entity_id` (a snowflake
    string) against `ScheduledEventEntityType` members via `in (...)`, which
    raised ValueError for stage events and stayed None for voice events. """

    def test_voice_event_with_channel_id_resolves_channel(self) -> None:
        event = ScheduledEvent(state=FakeState(), data=_scheduled_event_data(
            entity_type=2, channel_id="888"
        ))
        self.assertIsNotNone(event.channel)
        self.assertEqual(event.channel.id, 888)

    def test_stage_event_with_entity_id_does_not_crash(self) -> None:
        event = ScheduledEvent(state=FakeState(), data=_scheduled_event_data(
            entity_type=1, entity_id="999", channel_id="888"
        ))
        self.assertEqual(event.channel.id, 888)

    def test_external_event_has_no_channel(self) -> None:
        event = ScheduledEvent(state=FakeState(), data=_scheduled_event_data(
            entity_type=3, channel_id=None
        ))
        self.assertIsNone(event.channel)


class TestScheduledEventImage(unittest.TestCase):
    def test_image_property_builds_asset(self) -> None:
        event = ScheduledEvent(state=FakeState(), data=_scheduled_event_data(image="abc123"))
        self.assertIsNotNone(event.image)
        self.assertIn("abc123", event.image.url)

    def test_image_property_none_when_absent(self) -> None:
        event = ScheduledEvent(state=FakeState(), data=_scheduled_event_data())
        self.assertIsNone(event.image)


class TestScheduledEventRecurrenceRule(unittest.TestCase):
    def test_to_dict_omits_discord_only_fields(self) -> None:
        rule = ScheduledEventRecurrenceRule(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            frequency=ScheduledEventRecurrenceFrequency.weekly,
            interval=1,
            end=datetime(2024, 6, 1, tzinfo=UTC),
            by_weekday=[ScheduledEventRecurrenceWeekday.friday],
            count=10,
        )
        payload = rule.to_dict()

        self.assertNotIn("end", payload)
        self.assertNotIn("count", payload)
        self.assertNotIn("by_year_day", payload)
        self.assertEqual(payload["frequency"], 2)
        self.assertEqual(payload["by_weekday"], [4])

    def test_from_data_parses_nested_n_weekday(self) -> None:
        rule = ScheduledEventRecurrenceRule._from_data({
            "start": "2024-01-01T00:00:00.000000+00:00",
            "frequency": 1,
            "interval": 2,
            "by_n_weekday": [{"n": 2, "day": 3}],
        })

        self.assertEqual(rule.frequency, ScheduledEventRecurrenceFrequency.monthly)
        self.assertEqual(len(rule.by_n_weekday), 1)
        self.assertEqual(rule.by_n_weekday[0].n, 2)
        self.assertEqual(rule.by_n_weekday[0].day, ScheduledEventRecurrenceWeekday.thursday)


class TestGuildIncidentsData(unittest.TestCase):
    def test_from_data_parses_timestamps(self) -> None:
        data = GuildIncidentsData._from_data({
            "invites_disabled_until": "2024-01-01T00:00:00.000000+00:00",
            "dms_disabled_until": None,
            "dm_spam_detected_at": None,
            "raid_detected_at": None,
        })
        self.assertIsNotNone(data.invites_disabled_until)
        self.assertIsNone(data.dms_disabled_until)


class TestWelcomeScreen(unittest.TestCase):
    def test_from_data_and_channel_to_dict(self) -> None:
        screen = WelcomeScreen(state=FakeState(), guild_id=2, data={
            "description": "hi",
            "welcome_channels": [
                {"channel_id": "1", "description": "d", "emoji_id": None, "emoji_name": "wave"}
            ],
        })
        self.assertEqual(screen.description, "hi")
        self.assertEqual(len(screen.welcome_channels), 1)

        channel = screen.welcome_channels[0].channel
        self.assertEqual(channel.id, 1)
        self.assertEqual(channel.guild_id, 2)

        payload = screen.welcome_channels[0].to_dict()
        self.assertEqual(payload["channel_id"], "1")
        self.assertEqual(payload["emoji_name"], "wave")


class TestGuildWidgetSettings(unittest.TestCase):
    def test_from_data(self) -> None:
        settings = GuildWidgetSettings(
            state=FakeState(), guild_id=2, data={"enabled": True, "channel_id": "123"}
        )
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.channel.id, 123)
        self.assertEqual(settings.channel.guild_id, 2)

    def test_from_data_no_channel_is_none(self) -> None:
        settings = GuildWidgetSettings(
            state=FakeState(), guild_id=2, data={"enabled": False}
        )
        self.assertIsNone(settings.channel)


class TestGuildWidget(unittest.TestCase):
    def test_channels_resolve_to_partial_channel(self) -> None:
        widget = GuildWidget(state=FakeState(), data={
            "id": "1", "name": "g", "channels": [
                {"id": "5", "name": "general", "position": 0},
            ], "members": [],
        })
        channel = widget.channels[0].channel
        self.assertIsInstance(channel, PartialChannel)
        self.assertEqual(channel.id, 5)
        self.assertEqual(channel.guild_id, 1)

    def test_members_stay_raw_since_ids_are_anonymized(self) -> None:
        widget = GuildWidget(state=FakeState(), data={
            "id": "1", "name": "g", "channels": [], "members": [
                {"id": "999", "username": "anon", "status": "online", "avatar_url": "https://x"},
            ],
        })
        self.assertEqual(widget.members[0].id, 999)


class TestOnboardingPromptOptionEmojiClearing(unittest.TestCase):
    """ Regression test: to_dict() used to omit falsy emoji fields entirely,
    meaning a previously-set emoji could never actually be cleared via edit. """

    def test_to_dict_always_emits_emoji_fields(self) -> None:
        option = OnboardingPromptOption(state=FakeState(), data={
            "id": "1", "title": "opt", "channel_ids": [], "role_ids": [],
        })
        payload = option.to_dict()

        self.assertIn("emoji_id", payload)
        self.assertIn("emoji_name", payload)
        self.assertIn("emoji_animated", payload)
        self.assertIsNone(payload["emoji_id"])
        self.assertIsNone(payload["emoji_name"])
        self.assertFalse(payload["emoji_animated"])

    def test_from_data_reads_nested_emoji_object(self) -> None:
        option = OnboardingPromptOption(state=FakeState(), data={
            "id": "1", "title": "opt", "channel_ids": [], "role_ids": [],
            "emoji": {"id": None, "name": "wave", "animated": False},
        })
        self.assertEqual(option.emoji.name, "wave")


class TestGuildTemplate(unittest.TestCase):
    def test_parses_creator_and_dates(self) -> None:
        template = GuildTemplate(state=FakeState(), data={
            "code": "abc", "name": "tmpl", "description": None, "usage_count": 0,
            "creator_id": "2",
            "creator": {"id": "2", "username": "bob", "discriminator": "0001", "avatar": None},
            "created_at": "2020-04-02T21:10:38+00:00",
            "updated_at": "2020-05-01T17:57:38+00:00",
            "source_guild_id": "3", "serialized_source_guild": {}, "is_dirty": None,
        })
        self.assertEqual(template.creator.name, "bob")
        self.assertEqual(template.guild_id, 3)
        self.assertFalse(template.is_dirty)


class TestGuildOnboarding(unittest.TestCase):
    def test_parses_prompts_and_mode(self) -> None:
        onboarding = GuildOnboarding(state=FakeState(), data={
            "guild_id": "1", "enabled": True, "mode": 1,
            "default_channel_ids": ["1"],
            "prompts": [{
                "id": "10", "type": 1, "title": "p",
                "single_select": False, "required": True, "in_onboarding": True,
                "options": [],
            }],
        })
        self.assertEqual(onboarding.mode, OnboardingMode.onboarding_advanced)
        self.assertEqual(onboarding.prompts[0].type, OnboardingPromptType.dropdown)


class TestGuildPreview(unittest.TestCase):
    def test_parses_basic_fields(self) -> None:
        preview = GuildPreview(state=FakeState(), data={
            "id": "1", "name": "g", "icon": None, "splash": None, "discovery_splash": None,
            "emojis": [], "features": [], "approximate_member_count": 5,
            "approximate_presence_count": 2, "description": None, "stickers": [],
        })
        self.assertEqual(preview.name, "g")
        self.assertEqual(preview.approximate_member_count, 5)


class TestGuildPremiumTierEnumConversion(unittest.TestCase):
    """ premium_tier/nsfw_level/mfa_level moved from raw ints to enums this
    session; make sure the dict-keyed `_GUILD_LIMITS[int(self.premium_tier)]`
    lookups still work with the enum in place. """

    def test_enum_fields_and_limits(self) -> None:
        guild = Guild(state=FakeState(), data={
            "id": "1", "name": "g", "features": [],
            "premium_tier": 3, "nsfw_level": 1, "mfa_level": 1,
        })
        self.assertEqual(guild.premium_tier, PremiumTier.tier_3)
        self.assertEqual(guild.nsfw_level, NSFWLevel.explicit)
        self.assertEqual(guild.mfa_level, MFALevel.elevated)
        self.assertEqual(guild.emojis_limit, 250)
        self.assertEqual(guild.filesize_limit, 104_857_600)


class TestGuildWelcomeScreenField(unittest.TestCase):
    def test_parsed_from_guild_object(self) -> None:
        guild = Guild(state=FakeState(), data={
            "id": "1", "name": "g", "features": [],
            "welcome_screen": {"description": "hi", "welcome_channels": []},
        })
        self.assertIsNotNone(guild.welcome_screen)
        self.assertEqual(guild.welcome_screen.description, "hi")


if __name__ == "__main__":
    unittest.main()
