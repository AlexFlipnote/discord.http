import unittest

from discord_http import Colour


class TestColour(unittest.TestCase):
    def test_init_requires_integer(self) -> None:
        with self.assertRaises(TypeError):
            Colour("ff00ff")  # pyright: ignore[reportArgumentType]

    def test_init_rejects_out_of_range_value(self) -> None:
        with self.assertRaises(ValueError):
            Colour(-1)

        with self.assertRaises(ValueError):
            Colour(0x1000000)

    def test_rgb_roundtrip(self) -> None:
        colour = Colour.from_rgb(12, 34, 56)
        self.assertEqual(colour.to_rgb(), (12, 34, 56))
        self.assertEqual(colour.to_hex(), "#0c2238")

    def test_from_hex_supports_short_form(self) -> None:
        colour = Colour.from_hex("#abc")
        self.assertEqual(int(colour), 0xAABBCC)
        self.assertEqual(str(colour), "#aabbcc")

    def test_from_hex_rejects_invalid_input(self) -> None:
        with self.assertRaises(ValueError):
            Colour.from_hex("ab")

        with self.assertRaises(ValueError):
            Colour.from_hex("nothex")

    def test_random_seed_is_deterministic(self) -> None:
        first = Colour.random(seed="discord.http")
        second = Colour.random(seed="discord.http")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
