import unittest

from discord_http import enums, flags
from discord_http.audit import AuditChange, AuditLogEntry
from discord_http.colour import Colour
from discord_http.channel import PartialChannel
from discord_http.object import Snowflake
from discord_http.role import PartialRole
from discord_http.user import PartialUser


class FakeState:
    pass


def _make_entry(action_type: int, **overrides) -> AuditLogEntry:
    data = {
        "id": "1", "guild_id": "100", "action_type": action_type,
    }
    data.update(overrides)
    return AuditLogEntry(state=FakeState(), data=data)


class TestAuditChangeTranslatorDispatch(unittest.TestCase):
    def test_color_translates_to_colour(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.role_update))
        change = AuditChange(entry=entry, data={"key": "color", "new_value": 16711680})
        self.assertIsInstance(change.new_value, Colour)
        self.assertEqual(int(change.new_value), 16711680)

    def test_permissions_translates_to_permissions_flag(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.role_update))
        change = AuditChange(entry=entry, data={"key": "permissions", "new_value": "8"})
        self.assertIsInstance(change.new_value, flags.Permissions)

    def test_id_translates_to_snowflake(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.role_update))
        change = AuditChange(entry=entry, data={"key": "id", "new_value": "555"})
        self.assertIsInstance(change.new_value, Snowflake)
        self.assertEqual(int(change.new_value), 555)

    def test_channel_id_translates_to_partial_channel(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.member_update))
        change = AuditChange(entry=entry, data={"key": "channel_id", "new_value": "222"})
        self.assertIsInstance(change.new_value, PartialChannel)
        self.assertEqual(change.new_value.id, 222)

    def test_key_without_a_translator_is_passed_through_unchanged(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_update))
        change = AuditChange(entry=entry, data={"key": "rate_limit_per_user", "new_value": 30})
        self.assertEqual(change.new_value, 30)

    def test_none_values_are_left_untranslated(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.role_update))
        change = AuditChange(entry=entry, data={"key": "color", "new_value": None, "old_value": None})
        self.assertIsNone(change.new_value)
        self.assertIsNone(change.old_value)

    def test_both_old_and_new_value_are_translated(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.role_update))
        change = AuditChange(entry=entry, data={"key": "color", "old_value": 1, "new_value": 2})
        self.assertIsInstance(change.old_value, Colour)
        self.assertIsInstance(change.new_value, Colour)


class TestAuditChangeAddRemoveSpecialCase(unittest.TestCase):
    def test_add_key_builds_partial_role_list(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.member_role_update))
        change = AuditChange(entry=entry, data={
            "key": "$add", "new_value": [{"id": "111", "name": "Role"}],
        })
        self.assertEqual(len(change.new_value), 1)
        self.assertIsInstance(change.new_value[0], PartialRole)
        self.assertEqual(change.new_value[0].id, 111)
        self.assertEqual(change.new_value[0].guild_id, entry.guild.id)

    def test_remove_key_also_builds_partial_role_list(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.member_role_update))
        change = AuditChange(entry=entry, data={
            "key": "$remove", "new_value": [{"id": "222", "name": "Role"}],
        })
        self.assertEqual(change.new_value[0].id, 222)


class TestHandleTypeDispatch(unittest.TestCase):
    def test_sticker_action_returns_sticker_type(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.sticker_create))
        change = AuditChange(entry=entry, data={"key": "type", "new_value": 1})
        self.assertIsInstance(change.new_value, enums.StickerType)

    def test_webhook_action_returns_webhook_type(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.webhook_create))
        change = AuditChange(entry=entry, data={"key": "type", "new_value": 1})
        self.assertIsInstance(change.new_value, enums.WebhookType)

    def test_integration_action_returns_raw_value(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.integration_create))
        change = AuditChange(entry=entry, data={"key": "type", "new_value": "twitch"})
        self.assertEqual(change.new_value, "twitch")

    def test_channel_overwrite_action_returns_permission_type(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_overwrite_create))
        change = AuditChange(entry=entry, data={"key": "type", "new_value": 0})
        self.assertIsInstance(change.new_value, enums.PermissionType)

    def test_default_falls_back_to_channel_type(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create))
        change = AuditChange(entry=entry, data={"key": "type", "new_value": 0})
        self.assertIsInstance(change.new_value, enums.ChannelType)


class TestHandleOverwrites(unittest.TestCase):
    def test_role_type_resolves_to_partial_role(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_update))
        change = AuditChange(entry=entry, data={
            "key": "permission_overwrites",
            "new_value": [{"id": "5", "type": 0, "allow": "0", "deny": "0"}],
        })
        target, ow = change.new_value[0]
        self.assertIsInstance(target, PartialRole)
        self.assertEqual(target.id, 5)
        self.assertEqual(ow.target_type, enums.PermissionType.role)

    def test_member_type_resolves_to_partial_member(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_update))
        change = AuditChange(entry=entry, data={
            "key": "permission_overwrites",
            "new_value": [{"id": "6", "type": 1, "allow": "0", "deny": "0"}],
        })
        target, ow = change.new_value[0]
        self.assertEqual(target.id, 6)
        self.assertEqual(ow.target_type, enums.PermissionType.member)


class TestHandleOverloadedFlagsAllowlist(unittest.TestCase):
    def test_channel_create_returns_channel_flags(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create))
        change = AuditChange(entry=entry, data={"key": "flags", "new_value": 1})
        self.assertIsInstance(change.new_value, flags.ChannelFlags)

    def test_thread_update_returns_channel_flags(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.thread_update))
        change = AuditChange(entry=entry, data={"key": "flags", "new_value": 1})
        self.assertIsInstance(change.new_value, flags.ChannelFlags)

    def test_unrelated_action_type_returns_raw_int(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.member_update))
        change = AuditChange(entry=entry, data={"key": "flags", "new_value": 1})
        self.assertEqual(change.new_value, 1)
        self.assertNotIsInstance(change.new_value, flags.ChannelFlags)


class TestAuditLogEntryActionType(unittest.TestCase):
    def test_known_action_type_parses_to_enum(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create))
        self.assertEqual(entry.action_type, enums.AuditLogType.channel_create)

    def test_unknown_action_type_falls_back_to_unknown(self) -> None:
        entry = _make_entry(999999)
        self.assertEqual(entry.action_type, enums.AuditLogType.unknown)


class TestAuditLogEntryTargetDispatch(unittest.TestCase):
    def test_no_target_id_returns_none(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create))
        self.assertIsNone(entry.target)

    def test_channel_target_type_resolves_to_partial_channel(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create), target_id="10")
        self.assertIsInstance(entry.target, PartialChannel)
        self.assertEqual(entry.target.id, 10)

    def test_message_target_type_resolves_via_convert_target_message(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.message_delete), target_id="20")
        self.assertIsInstance(entry.target, (PartialUser,))

    def test_target_type_without_a_matching_converter_falls_back_to_snowflake(self) -> None:
        # "webhook" target_type has no _convert_target_webhook method defined.
        entry = _make_entry(int(enums.AuditLogType.webhook_create), target_id="30")
        target = entry.target
        self.assertIsInstance(target, Snowflake)
        self.assertNotIsInstance(target, PartialChannel)
        self.assertEqual(target.id, 30)


class TestAuditLogEntryUser(unittest.TestCase):
    def test_no_user_id_returns_none(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create))
        self.assertIsNone(entry.user)

    def test_user_id_resolves_via_cache_or_partial(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_create), user_id="40")
        self.assertIsInstance(entry.user, PartialUser)
        self.assertEqual(entry.user.id, 40)

    def test_cached_user_is_returned_when_available(self) -> None:
        from discord_http.user import User

        cached = User(state=FakeState(), data={
            "id": "40", "username": "u", "discriminator": "0001", "avatar": None,
        })
        entry = AuditLogEntry(
            state=FakeState(),
            data={"id": "1", "guild_id": "100", "action_type": int(enums.AuditLogType.channel_create), "user_id": "40"},
            users={40: cached},
        )
        self.assertIs(entry.user, cached)


class TestGetChange(unittest.TestCase):
    def test_returns_matching_change(self) -> None:
        entry = _make_entry(
            int(enums.AuditLogType.channel_update),
            changes=[{"key": "name", "new_value": "general"}],
        )
        change = entry.get_change("name")
        self.assertIsNotNone(change)
        self.assertEqual(change.new_value, "general")

    def test_returns_none_for_missing_key(self) -> None:
        entry = _make_entry(int(enums.AuditLogType.channel_update), changes=[])
        self.assertIsNone(entry.get_change("name"))


if __name__ == "__main__":
    unittest.main()
