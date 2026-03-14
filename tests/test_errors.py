import unittest

from discord_http import (
    Cooldown, BotMissingPermissions, CommandOnCooldown,
    HTTPException, UserMissingPermissions, Permissions
)


class FakeResponse:
    def __init__(self, status: int, reason: str, response):
        self.status = status
        self.reason = reason
        self.response = response


class TestCommandErrors(unittest.TestCase):
    def test_command_on_cooldown_message_contains_relative_timestamp(self) -> None:
        err = CommandOnCooldown(Cooldown(rate=1, per=10), retry_after=2.5)
        self.assertIn("<t:", err.discord_format)
        self.assertIn(":R>", err.discord_format)
        self.assertIn("Command is on cooldown", str(err))

    def test_missing_permissions_messages(self) -> None:
        perms = Permissions.from_names("send_messages", "manage_messages")

        user_err = UserMissingPermissions(perms)
        bot_err = BotMissingPermissions(perms)

        self.assertIn("send_messages", str(user_err))
        self.assertIn("Bot is missing permissions", str(bot_err))


class TestHTTPException(unittest.TestCase):
    def test_http_exception_with_dict_response(self) -> None:
        response = FakeResponse(
            status=400,
            reason="Bad Request",
            response={"code": 50035, "message": "Invalid Form Body", "errors": {"name": "too short"}},
        )

        err = HTTPException(response)  # pyright: ignore[reportArgumentType]
        self.assertEqual(err.code, 50035)
        self.assertIn("Invalid Form Body", err.text)
        self.assertIn("HTTP 400 > Bad Request", str(err))

    def test_http_exception_with_non_dict_response(self) -> None:
        response = FakeResponse(status=500, reason="Server Error", response="oops")
        err = HTTPException(response)  # pyright: ignore[reportArgumentType]

        self.assertEqual(err.code, 0)
        self.assertEqual(err.text, "oops")
        self.assertIn("HTTP 500 > Server Error", str(err))


if __name__ == "__main__":
    unittest.main()
