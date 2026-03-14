import unittest

from discord_http import AllowedMentions


class TestAllowedMentions(unittest.TestCase):
    def test_all_preset(self) -> None:
        data = AllowedMentions.all().to_dict()
        self.assertEqual(sorted(data["parse"]), ["everyone", "roles", "users"])
        self.assertTrue(data["replied_user"])

    def test_none_preset(self) -> None:
        data = AllowedMentions.none().to_dict()
        self.assertEqual(data["parse"], [])
        self.assertNotIn("users", data)
        self.assertNotIn("roles", data)
        self.assertNotIn("replied_user", data)

    def test_explicit_user_and_role_lists(self) -> None:
        allowed = AllowedMentions(
            everyone=False,
            users=[123, 456],
            roles=[789],
            replied_user=False,
        )
        data = allowed.to_dict()

        self.assertEqual(data["parse"], [])
        self.assertEqual(data["users"], [123, 456])
        self.assertEqual(data["roles"], [789])
        self.assertNotIn("replied_user", data)


if __name__ == "__main__":
    unittest.main()
