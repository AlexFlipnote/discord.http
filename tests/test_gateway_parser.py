import asyncio
import unittest

from discord_http.entitlements import Entitlements, Subscription
from discord_http.gateway.enums import PayloadType
from discord_http.gateway.object import GuildApplicationCommandPermissions
from discord_http.gateway.parser import Parser, GuildMembersChunk
from discord_http.user import User


class FakeState:
    pass


class FakeBot:
    def __init__(self):
        self.state = FakeState()
        self.application = None
        self.cache = None


class TestEntitlementHandlers(unittest.TestCase):
    def test_create_update_delete_share_helper(self) -> None:
        parser = Parser(bot=FakeBot())
        data = {
            "id": "1", "sku_id": "2", "application_id": "3",
            "type": 1, "deleted": False,
        }
        for method_name in ("entitlement_create", "entitlement_update", "entitlement_delete"):
            (result,) = getattr(parser, method_name)(data)
            self.assertIsInstance(result, Entitlements)
            self.assertEqual(result.id, 1)


class TestSubscriptionHandlers(unittest.TestCase):
    def test_create_update_delete_build_subscription_without_route_context(self) -> None:
        parser = Parser(bot=FakeBot())
        data = {
            "id": "1", "user_id": "2", "sku_ids": ["10"], "entitlement_ids": [],
            "current_period_start": "2024-01-01T00:00:00.000000+00:00",
            "current_period_end": "2024-02-01T00:00:00.000000+00:00",
            "status": 0,
        }
        for method_name in ("subscription_create", "subscription_update", "subscription_delete"):
            (result,) = getattr(parser, method_name)(data)
            self.assertIsInstance(result, Subscription)
            # No sku_id kwarg is passed on the gateway path, since there's no
            # "SKU used to fetch this" context here - only the real sku_ids apply.
            self.assertIsNone(result._route_sku_id)


class TestApplicationCommandPermissionsUpdate(unittest.TestCase):
    def test_parses_permissions(self) -> None:
        parser = Parser(bot=FakeBot())
        (result,) = parser.application_command_permissions_update({
            "id": "1", "application_id": "2", "guild_id": "3",
            "permissions": [{"id": "4", "type": 1, "permission": True}],
        })
        self.assertIsInstance(result, GuildApplicationCommandPermissions)
        self.assertFalse(result.is_default())
        self.assertEqual(result.permissions[0].id, 4)

    def test_is_default_when_id_matches_application_id(self) -> None:
        parser = Parser(bot=FakeBot())
        (result,) = parser.application_command_permissions_update({
            "id": "2", "application_id": "2", "guild_id": "3", "permissions": [],
        })
        self.assertTrue(result.is_default())

    def test_role_and_user_and_channel_targets_are_resolved(self) -> None:
        from discord_http.role import PartialRole
        from discord_http.user import PartialUser
        from discord_http.channel import PartialChannel

        parser = Parser(bot=FakeBot())
        (result,) = parser.application_command_permissions_update({
            "id": "1", "application_id": "2", "guild_id": "3",
            "permissions": [
                {"id": "10", "type": 1, "permission": True},
                {"id": "20", "type": 2, "permission": True},
                {"id": "30", "type": 3, "permission": False},
            ],
        })
        role_perm, user_perm, channel_perm = result.permissions
        self.assertIsInstance(role_perm.target, PartialRole)
        self.assertIsInstance(user_perm.target, PartialUser)
        self.assertIsInstance(channel_perm.target, PartialChannel)
        self.assertEqual(role_perm.target.id, 10)
        self.assertEqual(user_perm.target.id, 20)
        self.assertEqual(channel_perm.target.id, 30)

    def test_everyone_role_target_still_resolves_since_its_id_is_real(self) -> None:
        # The @everyone role's ID always equals guild_id - it's a real role,
        # not a special sentinel, unlike the user/channel "all X" constants.
        from discord_http.role import PartialRole

        parser = Parser(bot=FakeBot())
        (result,) = parser.application_command_permissions_update({
            "id": "1", "application_id": "2", "guild_id": "3",
            "permissions": [{"id": "3", "type": 1, "permission": True}],
        })
        self.assertIsInstance(result.permissions[0].target, PartialRole)
        self.assertEqual(result.permissions[0].target.id, 3)

    def test_all_members_sentinel_resolves_to_no_target(self) -> None:
        # type=user with id == guild_id is Discord's "@everyone" / all-members
        # constant, not a real user.
        parser = Parser(bot=FakeBot())
        (result,) = parser.application_command_permissions_update({
            "id": "1", "application_id": "2", "guild_id": "3",
            "permissions": [{"id": "3", "type": 2, "permission": True}],
        })
        self.assertIsNone(result.permissions[0].target)

    def test_all_channels_sentinel_resolves_to_no_target(self) -> None:
        # type=channel with id == guild_id - 1 is Discord's all-channels
        # constant, not a real channel.
        parser = Parser(bot=FakeBot())
        (result,) = parser.application_command_permissions_update({
            "id": "1", "application_id": "2", "guild_id": "3",
            "permissions": [{"id": "2", "type": 3, "permission": True}],
        })
        self.assertIsNone(result.permissions[0].target)


class TestUserUpdate(unittest.TestCase):
    """ Regression coverage for the USER_UPDATE dispatch, which mutates the
    cached Application.bot in place so Client.user reflects the change
    immediately, without needing to re-fetch the application. """

    def test_updates_bots_own_application_user(self) -> None:
        bot = FakeBot()

        class FakeApplication:
            bot = None

        bot.application = FakeApplication()
        parser = Parser(bot=bot)

        (user,) = parser.user_update({
            "id": "1", "username": "new_name", "discriminator": "0001", "avatar": None,
        })
        self.assertIsInstance(user, User)
        self.assertEqual(bot.application.bot.name, "new_name")

    def test_does_not_crash_without_a_cached_application(self) -> None:
        parser = Parser(bot=FakeBot())
        (user,) = parser.user_update({
            "id": "1", "username": "new_name", "discriminator": "0001", "avatar": None,
        })
        self.assertEqual(user.name, "new_name")


class TestRateLimited(unittest.IsolatedAsyncioTestCase):
    """ Regression test: RATE_LIMITED (currently only opcode 8, Request Guild
    Members) was entirely unhandled, meaning a rate-limited chunk_guild()/
    fetch_members() call would silently hang for the full 30s timeout instead
    of failing fast with a clear error. """

    async def test_fails_matching_pending_chunk_request(self) -> None:
        bot = FakeBot()
        parser = Parser(bot=bot)

        chunk_state = type("ChunkState", (), {"bot": type("B", (), {"loop": asyncio.get_running_loop()})()})()
        chunk = GuildMembersChunk(state=chunk_state, guild_id=1)
        parser._chunk_requests[chunk.nonce] = chunk

        wait_task = asyncio.ensure_future(chunk.wait())
        await asyncio.sleep(0)

        (payload,) = parser.rate_limited({
            "opcode": int(PayloadType.request_guild_members),
            "retry_after": 5.0,
            "meta": {"guild_id": "1", "nonce": chunk.nonce},
        })
        self.assertEqual(payload.retry_after, 5.0)
        self.assertNotIn(chunk.nonce, parser._chunk_requests)

        with self.assertRaises(RuntimeError):
            await wait_task

    async def test_ignores_unrelated_rate_limits(self) -> None:
        parser = Parser(bot=FakeBot())
        (payload,) = parser.rate_limited({
            "opcode": 99, "retry_after": 1.0, "meta": {},
        })
        self.assertEqual(payload.opcode, 99)


if __name__ == "__main__":
    unittest.main()
