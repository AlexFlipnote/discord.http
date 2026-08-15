import unittest

from discord_http.automod import AutoModRule, AutoModRuleAction, AutoModRuleTriggers
from discord_http.enums import AutoModRuleActionType, AutoModRuleEventType, AutoModRuleTriggerType
from discord_http.role import PartialRole
from discord_http.channel import PartialChannel


class FakeState:
    pass


class TestAutoModRuleActionDurationCap(unittest.TestCase):
    def test_duration_under_cap_is_unchanged(self) -> None:
        action = AutoModRuleAction(type=AutoModRuleActionType.timeout, duration_seconds=60)
        self.assertEqual(action.duration_seconds, 60)

    def test_duration_over_4_weeks_is_capped(self) -> None:
        action = AutoModRuleAction(type=AutoModRuleActionType.timeout, duration_seconds=99999999)
        self.assertEqual(action.duration_seconds, 2419200)

    def test_duration_exactly_at_cap_is_unchanged(self) -> None:
        action = AutoModRuleAction(type=AutoModRuleActionType.timeout, duration_seconds=2419200)
        self.assertEqual(action.duration_seconds, 2419200)

    def test_none_duration_is_left_as_none(self) -> None:
        action = AutoModRuleAction(type=AutoModRuleActionType.block_message)
        self.assertIsNone(action.duration_seconds)


class TestAutoModRuleActionFactories(unittest.TestCase):
    def test_create_message(self) -> None:
        action = AutoModRuleAction.create_message("blocked!")
        self.assertEqual(action.type, AutoModRuleActionType.block_message)
        self.assertEqual(action.custom_message, "blocked!")

    def test_create_alert_location(self) -> None:
        action = AutoModRuleAction.create_alert_location(123)
        self.assertEqual(action.type, AutoModRuleActionType.send_alert_message)
        self.assertEqual(action.channel_id, 123)

    def test_create_timeout_caps_duration(self) -> None:
        action = AutoModRuleAction.create_timeout(99999999)
        self.assertEqual(action.type, AutoModRuleActionType.timeout)
        self.assertEqual(action.duration_seconds, 2419200)


class TestAutoModRuleActionRoundTrip(unittest.TestCase):
    def test_to_dict_nests_metadata(self) -> None:
        action = AutoModRuleAction(
            type=AutoModRuleActionType.timeout,
            channel_id=1, duration_seconds=60, custom_message="hi",
        )
        payload = action.to_dict()
        self.assertEqual(payload["type"], int(AutoModRuleActionType.timeout))
        self.assertEqual(payload["metadata"], {
            "channel_id": "1", "duration_seconds": 60, "custom_message": "hi",
        })

    def test_to_dict_omits_unset_metadata(self) -> None:
        action = AutoModRuleAction(type=AutoModRuleActionType.block_message)
        payload = action.to_dict()
        self.assertEqual(payload["metadata"], {})

    def test_from_dict_round_trip(self) -> None:
        original = AutoModRuleAction(
            type=AutoModRuleActionType.send_alert_message, channel_id=5,
        )
        rebuilt = AutoModRuleAction.from_dict(original.to_dict())
        self.assertEqual(rebuilt.type, original.type)
        self.assertEqual(rebuilt.channel_id, original.channel_id)

    def test_from_dict_defaults_missing_metadata_fields_to_none(self) -> None:
        action = AutoModRuleAction.from_dict({
            "type": int(AutoModRuleActionType.block_message),
        })
        self.assertIsNone(action.channel_id)
        self.assertIsNone(action.duration_seconds)
        self.assertIsNone(action.custom_message)


class TestAutoModRuleTriggersRoundTrip(unittest.TestCase):
    def test_to_dict_omits_none_fields(self) -> None:
        triggers = AutoModRuleTriggers()
        payload = triggers.to_dict()
        self.assertNotIn("keyword_filter", payload)
        self.assertNotIn("regex_patterns", payload)
        self.assertNotIn("presets", payload)
        self.assertNotIn("allow_list", payload)
        self.assertNotIn("mention_total_limit", payload)
        # mention_raid_protection_enabled defaults to False, not None, so it's
        # always included.
        self.assertIn("mention_raid_protection_enabled", payload)

    def test_to_dict_includes_zero_mention_limit(self) -> None:
        triggers = AutoModRuleTriggers(mention_total_limit=0)
        payload = triggers.to_dict()
        self.assertEqual(payload["mention_total_limit"], 0)

    def test_from_dict_to_dict_round_trip(self) -> None:
        data = {
            "keyword_filter": ["a"], "regex_patterns": ["b.*"],
            "presets": [1], "allow_list": ["c"],
            "mention_total_limit": 5, "mention_raid_protection_enabled": True,
        }
        triggers = AutoModRuleTriggers.from_dict(data)
        payload = triggers.to_dict()
        self.assertEqual(payload["keyword_filter"], ["a"])
        self.assertEqual(payload["regex_patterns"], ["b.*"])
        self.assertEqual(payload["presets"], [1])
        self.assertEqual(payload["allow_list"], ["c"])
        self.assertEqual(payload["mention_total_limit"], 5)
        self.assertTrue(payload["mention_raid_protection_enabled"])

    def test_from_dict_defaults_missing_fields(self) -> None:
        triggers = AutoModRuleTriggers.from_dict({})
        self.assertIsNone(triggers.keyword_filter)
        self.assertFalse(triggers.mention_raid_protection_enabled)


class TestAutoModRuleConstruction(unittest.TestCase):
    def _data(self, **overrides) -> dict:
        data = {
            "id": "1", "guild_id": "100", "name": "rule", "creator_id": "5",
            "event_type": int(AutoModRuleEventType.message_send),
            "trigger_type": int(AutoModRuleTriggerType.keyword),
            "actions": [{"type": int(AutoModRuleActionType.block_message), "metadata": {}}],
        }
        data.update(overrides)
        return data

    def test_actions_are_parsed(self) -> None:
        rule = AutoModRule(state=FakeState(), data=self._data())
        self.assertEqual(len(rule.actions), 1)
        self.assertIsInstance(rule.actions[0], AutoModRuleAction)

    def test_trigger_metadata_is_none_when_absent(self) -> None:
        rule = AutoModRule(state=FakeState(), data=self._data())
        self.assertIsNone(rule.trigger_metadata)

    def test_trigger_metadata_is_parsed_when_present(self) -> None:
        rule = AutoModRule(state=FakeState(), data=self._data(
            trigger_metadata={"keyword_filter": ["bad"]},
        ))
        self.assertIsInstance(rule.trigger_metadata, AutoModRuleTriggers)
        self.assertEqual(rule.trigger_metadata.keyword_filter, ["bad"])

    def test_exempt_roles_and_channels_are_partial_objects(self) -> None:
        rule = AutoModRule(state=FakeState(), data=self._data(
            exempt_roles=["10"], exempt_channels=["20"],
        ))
        self.assertIsInstance(rule.exempt_roles[0], PartialRole)
        self.assertEqual(rule.exempt_roles[0].id, 10)
        self.assertIsInstance(rule.exempt_channels[0], PartialChannel)
        self.assertEqual(rule.exempt_channels[0].id, 20)

    def test_creator_property_builds_partial_user(self) -> None:
        rule = AutoModRule(state=FakeState(), data=self._data())
        self.assertEqual(rule.creator.id, 5)


if __name__ == "__main__":
    unittest.main()
