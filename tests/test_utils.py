import base64
import unittest

from datetime import datetime, timedelta, UTC
from typing import Optional

from discord_http import utils, Snowflake, MISSING

class TestURL(unittest.TestCase):
    def setUp(self):
        self.base_url_str = "https://example.com/foo/bar.png?v=1#section"
        self.url = utils.URL(self.base_url_str)

    def test_basic_properties(self):
        self.assertEqual(self.url.scheme, "https")
        self.assertEqual(self.url.host, "example.com")
        self.assertEqual(self.url.path, "/foo/bar.png")
        self.assertEqual(self.url.fragment, "section")
        self.assertEqual(self.url.origin, "https://example.com")

    def test_pathlib_style_properties(self):
        self.assertEqual(self.url.name, "bar.png")
        self.assertEqual(self.url.stem, "bar")
        self.assertEqual(self.url.suffix, ".png")

        # Test directory-style path
        dir_url = utils.URL("https://example.com/assets/images/")
        self.assertEqual(dir_url.name, "images")
        self.assertEqual(dir_url.suffix, "")

    def test_query_manipulation(self):
        # Test reading query
        self.assertEqual(self.url["v"], "1")

        # Test updating (merging) query
        updated = self.url.update_query(v=2, theme="dark")
        self.assertEqual(updated["v"], "2")
        self.assertEqual(updated["theme"], "dark")

        # Test removing query parameter
        removed = updated.update_query(v=None)
        self.assertNotIn("v", removed.query)

        # Test clear_query
        cleared = self.url.clear_query()
        self.assertEqual(cleared.query, {})
        self.assertFalse("?" in str(cleared))

    def test_path_manipulation(self):
        # Test truediv (/) operator
        joined = self.url.parent / "logo.jpg"
        self.assertEqual(joined.path, "/foo/logo.jpg")

        # Test update_path with append and lstrip fix
        base = utils.URL("https://example.com/api")
        appended = base.update_path("/v1", append=True)
        self.assertEqual(appended.path, "/api/v1")

    def test_request_uri(self):
        self.assertEqual(self.url.request_uri, "/foo/bar.png?v=1#section")

        # Test without query/fragment
        simple = utils.URL("https://example.com/test")
        self.assertEqual(simple.request_uri, "/test")

    def test_credentials(self):
        auth_url = utils.URL("https://example.com").update_user("admin", "password123")
        self.assertEqual(auth_url.user, "admin")
        self.assertEqual(auth_url.password, "password123")
        self.assertIn("admin:password123@", str(auth_url))

        # Test removing user
        no_auth = auth_url.update_user(None)
        self.assertIsNone(no_auth.user)
        self.assertNotIn("@", str(no_auth))

    def test_immutability(self):
        old_url = self.url.url
        self.url.update_query(test="data")
        self.assertEqual(self.url.url, old_url)

    def test_human_repr(self):
        encoded_url = utils.URL("https://example.com/hello%20world")
        self.assertEqual(encoded_url.human_repr(), "https://example.com/hello world")

    def test_join(self):
        base = utils.URL("https://example.com/blog/posts/")
        relative = base.join("../assets/img.png")
        self.assertEqual(relative.url, "https://example.com/blog/assets/img.png")


class TestUtilsTextAndTyping(unittest.TestCase):
    def test_escape_markdown(self) -> None:
        text = "Hello *world*_test_"
        self.assertEqual(utils.escape_markdown(text), "Hello \\*world\\*\\_test\\_")
        self.assertEqual(utils.escape_markdown(text, remove=True), "Hello worldtest")

    def test_plural(self) -> None:
        self.assertEqual(utils.plural("cat", 1), "cat")
        self.assertEqual(utils.plural("cat", 2), "cats")

    def test_ordinal(self) -> None:
        self.assertEqual(utils.ordinal(1), "1st")
        self.assertEqual(utils.ordinal(2), "2nd")
        self.assertEqual(utils.ordinal(3), "3rd")
        self.assertEqual(utils.ordinal(4), "4th")
        self.assertEqual(utils.ordinal(11), "11th")
        self.assertEqual(utils.ordinal(22), "22nd")

    def test_unwrap_optional(self) -> None:
        self.assertIs(utils.unwrap_optional(Optional[int]), int)  # pyright: ignore[reportArgumentType]
        self.assertIs(utils.unwrap_optional(int), int)


class TestSmallTimeFormat(unittest.TestCase):
    def test_format_time_boundaries(self) -> None:
        self.assertEqual(utils.format_small_unit(0), "0ns")
        self.assertEqual(utils.format_small_unit(0.0000005), "500ns")
        self.assertEqual(utils.format_small_unit(0.0005), "500µs")
        self.assertEqual(utils.format_small_unit(0.5), "500ms")
        self.assertEqual(utils.format_small_unit(2), "2.00s")


class TestUtilsGeneral(unittest.TestCase):
    def test_parse_time_accepts_seconds_milliseconds_and_microseconds(self) -> None:
        self.assertEqual(utils.parse_time(1_700_000_000), datetime.fromtimestamp(1_700_000_000, tz=UTC))
        self.assertEqual(utils.parse_time(1_700_000_000_000), datetime.fromtimestamp(1_700_000_000, tz=UTC))
        self.assertEqual(utils.parse_time(1_700_000_000_000_000), datetime.fromtimestamp(1_700_000_000, tz=UTC))

    def test_parse_time_string_and_invalid_type(self) -> None:
        self.assertEqual(utils.parse_time("2024-01-01T00:00:00+00:00"), datetime(2024, 1, 1, tzinfo=UTC))
        with self.assertRaises(TypeError):
            utils.parse_time(3.14)  # type: ignore[arg-type]

    def test_normalize_entity_id(self) -> None:
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        sf = Snowflake(123456789012345678)

        self.assertEqual(utils.normalize_entity_id(55), 55)
        self.assertEqual(utils.normalize_entity_id("66"), 66)
        self.assertEqual(utils.normalize_entity_id(sf), int(sf))
        self.assertIsInstance(utils.normalize_entity_id(dt), int)

        with self.assertRaises(TypeError):
            utils.normalize_entity_id("abc")

    def test_unicode_name(self) -> None:
        self.assertEqual(utils.unicode_name("A"), "LATIN_CAPITAL_LETTER_A")
        self.assertEqual(utils.unicode_name(""), "")

    def test_oauth_url(self) -> None:
        url = utils.oauth_url(123, user_install=True, permissions="8")
        self.assertIn("client_id=123", url)
        self.assertIn("interaction_type=1", url)
        self.assertIn("permissions=8", url)

    def test_divide_chunks(self) -> None:
        self.assertEqual(utils.divide_chunks([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_add_to_datetime(self) -> None:
        aware = datetime(2024, 1, 1, tzinfo=UTC)
        self.assertEqual(utils.add_to_datetime(aware), aware)

        delta_result = utils.add_to_datetime(timedelta(seconds=5))
        int_result = utils.add_to_datetime(5)
        now = datetime.now(UTC)

        self.assertTrue(abs((delta_result - now).total_seconds()) < 10)
        self.assertTrue(abs((int_result - now).total_seconds()) < 10)

        with self.assertRaises(ValueError):
            utils.add_to_datetime(datetime(2024, 1, 1))

        with self.assertRaises(TypeError):
            utils.add_to_datetime("invalid")  # type: ignore[arg-type]

    def test_mime_type_image(self) -> None:
        self.assertEqual(utils.mime_type_image(b"\x89PNG\r\n\x1a\nrest"), "image/png")
        self.assertEqual(utils.mime_type_image(b"\xff\xd8\xffrest"), "image/jpeg")
        self.assertEqual(utils.mime_type_image(b"GIF89arest"), "image/gif")
        self.assertEqual(utils.mime_type_image(b"RIFFxxxxWEBPrest"), "image/webp")

        with self.assertRaises(ValueError):
            utils.mime_type_image(b"nope")

    def test_mime_type_audio(self) -> None:
        self.assertEqual(utils.mime_type_audio(b"OggSrest"), "audio/ogg")
        self.assertEqual(utils.mime_type_audio(b"ID3rest"), "audio/mpeg")
        self.assertEqual(utils.mime_type_audio(bytes([255, 224, 0, 0])), "audio/mpeg")

        with self.assertRaises(ValueError):
            utils.mime_type_audio(b"bad")

    def test_bytes_to_base64(self) -> None:
        png = b"\x89PNG\r\n\x1a\nrest"
        encoded = utils.bytes_to_base64(png)
        self.assertTrue(encoded.startswith("data:image/png;base64,"))

        raw = encoded.split(",", 1)[1]
        self.assertEqual(base64.b64decode(raw), png)

        with self.assertRaises(ValueError):
            utils.bytes_to_base64(123)  # type: ignore[arg-type]

    def test_get_int(self) -> None:
        data = {"a": "10", "b": 20}
        self.assertEqual(utils.get_int(data, "a"), 10)
        self.assertEqual(utils.get_int(data, "b"), 20)
        self.assertEqual(utils.get_int(data, "missing", default=7), 7)

        with self.assertRaises(ValueError):
            utils.get_int({"x": "abc"}, "x")


class TestDiscordTimestampAndMissing(unittest.TestCase):
    def test_discord_timestamp_formats(self) -> None:
        ts = utils.DiscordTimestamp(1_700_000_000)
        self.assertEqual(str(ts), "<t:1700000000>")
        self.assertEqual(ts.short_time, "<t:1700000000:t>")
        self.assertEqual(ts.long_time, "<t:1700000000:T>")
        self.assertEqual(ts.short_date, "<t:1700000000:d>")
        self.assertEqual(ts.long_date, "<t:1700000000:D>")
        self.assertEqual(ts.short_date_time, "<t:1700000000:f>")
        self.assertEqual(ts.long_date_time, "<t:1700000000:F>")
        self.assertEqual(ts.relative_time, "<t:1700000000:R>")
        self.assertEqual(int(ts), 1_700_000_000)

    def test_discord_timestamp_accepts_datetime_and_timedelta(self) -> None:
        from_dt = utils.DiscordTimestamp(datetime(2024, 1, 1, tzinfo=UTC))
        self.assertIsInstance(int(from_dt), int)

        from_td = utils.DiscordTimestamp(timedelta(seconds=1))
        self.assertIsInstance(int(from_td), int)

        with self.assertRaises(TypeError):
            utils.DiscordTimestamp("bad")  # type: ignore[arg-type]

    def test_missing_behaves_like_sentinel(self) -> None:
        self.assertFalse(bool(MISSING))
        self.assertEqual(str(MISSING), "")
        self.assertEqual(int(MISSING), -1)
        self.assertEqual(bytes(MISSING), b"")
        self.assertEqual(repr(MISSING), "<MISSING>")
        self.assertIsNone(next(iter(MISSING)))


if __name__ == "__main__":
    unittest.main()
