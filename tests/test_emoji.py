import unittest

from discord_http.emoji import EmojiParser


class TestEmojiParserConstructor(unittest.TestCase):
    def test_unicode_emoji_is_not_a_discord_emoji(self) -> None:
        parser = EmojiParser("\U0001F600")
        self.assertFalse(parser.discord_emoji)
        self.assertIsNone(parser.id)
        self.assertEqual(parser.name, "\U0001F600")
        self.assertFalse(parser.animated)

    def test_custom_emoji_string_is_parsed(self) -> None:
        parser = EmojiParser("<:wave:123456789012345678>")
        self.assertTrue(parser.discord_emoji)
        self.assertFalse(parser.animated)
        self.assertEqual(parser.name, "wave")
        self.assertEqual(parser.id, 123456789012345678)

    def test_animated_custom_emoji_string_is_parsed(self) -> None:
        parser = EmojiParser("<a:wave:123456789012345678>")
        self.assertTrue(parser.discord_emoji)
        self.assertTrue(parser.animated)
        self.assertEqual(parser.name, "wave")
        self.assertEqual(parser.id, 123456789012345678)

    def test_bare_digit_string_is_treated_as_an_id(self) -> None:
        parser = EmojiParser("123456789012345678")
        self.assertTrue(parser.discord_emoji)
        self.assertFalse(parser.animated)
        self.assertEqual(parser.id, 123456789012345678)
        # No name info is available for a bare ID - it's stored as the digit string itself.
        self.assertEqual(parser.name, "123456789012345678")


class TestEmojiParserDunder(unittest.TestCase):
    def test_str_returns_raw_input(self) -> None:
        parser = EmojiParser("<:wave:123456789012345678>")
        self.assertEqual(str(parser), "<:wave:123456789012345678>")

    def test_int_returns_id_for_discord_emoji(self) -> None:
        parser = EmojiParser("<:wave:123456789012345678>")
        self.assertEqual(int(parser), 123456789012345678)

    def test_int_returns_none_for_unicode_emoji(self) -> None:
        # Python's int() builtin enforces an int return from __int__, so we
        # must call the dunder directly to observe the documented None case.
        parser = EmojiParser("\U0001F600")
        self.assertIsNone(parser.__int__())

    def test_repr_includes_id_only_for_discord_emoji(self) -> None:
        discord_parser = EmojiParser("<:wave:123456789012345678>")
        unicode_parser = EmojiParser("\U0001F600")
        self.assertIn("id=", repr(discord_parser))
        self.assertNotIn("id=", repr(unicode_parser))


class TestEmojiParserUrl(unittest.TestCase):
    def test_url_is_none_for_unicode_emoji(self) -> None:
        parser = EmojiParser("\U0001F600")
        self.assertIsNone(parser.url)

    def test_url_uses_png_for_static_custom_emoji(self) -> None:
        parser = EmojiParser("<:wave:123456789012345678>")
        self.assertTrue(parser.url.endswith(".png"))

    def test_url_uses_gif_for_animated_custom_emoji(self) -> None:
        parser = EmojiParser("<a:wave:123456789012345678>")
        self.assertTrue(parser.url.endswith(".gif"))


class TestEmojiParserToDict(unittest.TestCase):
    def test_unicode_emoji_to_dict(self) -> None:
        parser = EmojiParser("\U0001F600")
        self.assertEqual(parser.to_dict(), {"name": "\U0001F600", "id": None})

    def test_custom_emoji_to_dict_includes_animated(self) -> None:
        parser = EmojiParser("<a:wave:123456789012345678>")
        self.assertEqual(parser.to_dict(), {
            "id": 123456789012345678, "name": "wave", "animated": True,
        })


class TestEmojiParserToForumDict(unittest.TestCase):
    def test_unicode_emoji_uses_emoji_name(self) -> None:
        parser = EmojiParser("\U0001F600")
        self.assertEqual(parser.to_forum_dict(), {
            "emoji_name": "\U0001F600", "emoji_id": None,
        })

    def test_custom_emoji_uses_emoji_id_as_string(self) -> None:
        parser = EmojiParser("<:wave:123456789012345678>")
        self.assertEqual(parser.to_forum_dict(), {
            "emoji_name": None, "emoji_id": "123456789012345678",
        })


class TestEmojiParserToReaction(unittest.TestCase):
    def test_unicode_emoji_returns_the_emoji_itself(self) -> None:
        parser = EmojiParser("\U0001F600")
        self.assertEqual(parser.to_reaction(), "\U0001F600")

    def test_custom_emoji_returns_name_colon_id(self) -> None:
        parser = EmojiParser("<:wave:123456789012345678>")
        self.assertEqual(parser.to_reaction(), "wave:123456789012345678")


class TestEmojiParserFromDict(unittest.TestCase):
    def test_from_dict_without_id_builds_unicode_emoji(self) -> None:
        parser = EmojiParser.from_dict({"name": "\U0001F600", "id": None})
        self.assertFalse(parser.discord_emoji)
        self.assertEqual(parser.name, "\U0001F600")

    def test_from_dict_with_id_builds_custom_emoji(self) -> None:
        parser = EmojiParser.from_dict({
            "name": "wave", "id": "123456789012345678", "animated": False,
        })
        self.assertTrue(parser.discord_emoji)
        self.assertEqual(parser.name, "wave")
        self.assertEqual(parser.id, 123456789012345678)
        self.assertFalse(parser.animated)

    def test_from_dict_with_animated_true(self) -> None:
        parser = EmojiParser.from_dict({
            "name": "wave", "id": "123456789012345678", "animated": True,
        })
        self.assertTrue(parser.animated)

    def test_round_trip_through_to_dict(self) -> None:
        original = EmojiParser("<a:wave:123456789012345678>")
        rebuilt = EmojiParser.from_dict(original.to_dict())

        self.assertEqual(rebuilt.name, original.name)
        self.assertEqual(rebuilt.id, original.id)
        self.assertEqual(rebuilt.animated, original.animated)


if __name__ == "__main__":
    unittest.main()
