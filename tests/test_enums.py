import unittest

from discord_http import DefaultAvatarType


class TestBaseEnumBehavior(unittest.TestCase):
    def test_string_and_int_conversion(self) -> None:
        self.assertEqual(str(DefaultAvatarType.blurple), "blurple")
        self.assertEqual(int(DefaultAvatarType.blurple), 0)

    def test_comparison_with_numeric_values(self) -> None:
        self.assertTrue(DefaultAvatarType.blurple == 0)
        self.assertTrue(DefaultAvatarType.grey > 0)
        self.assertTrue(DefaultAvatarType.blurple < 1)
        self.assertTrue(DefaultAvatarType.orange >= 3)
        self.assertTrue(DefaultAvatarType.red <= 4)

    def test_comparison_with_names(self) -> None:
        self.assertTrue(DefaultAvatarType.blurple == "blurple")
        self.assertTrue(DefaultAvatarType.grey > "blurple")
        self.assertTrue(DefaultAvatarType.green < "orange")
        self.assertTrue(DefaultAvatarType.blurple >= "blurple")
        self.assertTrue(DefaultAvatarType.grey <= "grey")


if __name__ == "__main__":
    unittest.main()
