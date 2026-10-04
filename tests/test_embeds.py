import unittest

from datetime import UTC, datetime

from discord_http import Embed, EmbedFlags


class TestEmbedFooterValidation(unittest.TestCase):
    def test_icon_url_without_text_raises(self) -> None:
        embed = Embed()
        with self.assertRaises(ValueError):
            embed.set_footer(icon_url="https://example.com/x.png")

    def test_clearing_both_removes_footer(self) -> None:
        embed = Embed().set_footer(text="hi")
        embed.set_footer()
        self.assertIsNone(embed.footer)


class TestEmbedFieldCap(unittest.TestCase):
    def test_raises_past_25_fields(self) -> None:
        embed = Embed()
        for i in range(25):
            embed.add_field(name=str(i), value=str(i))

        with self.assertRaises(ValueError):
            embed.add_field(name="26", value="26")

    def test_remove_field_out_of_range_does_not_raise(self) -> None:
        embed = Embed()
        embed.remove_field(0)  # no fields at all


class TestEmbedLen(unittest.TestCase):
    def test_sums_all_text_fields(self) -> None:
        embed = (
            Embed(title="abc", description="de")
            .set_footer(text="fg")
            .set_author(name="hij")
            .add_field(name="k", value="lm")
        )
        # title(3) + description(2) + footer(2) + author(3) + field name(1) + field value(2)
        self.assertEqual(len(embed), 13)

    def test_documents_that_to_dict_never_enforces_the_6000_char_limit(self) -> None:
        # Discord itself enforces a combined 6000-character limit across
        # title/description/fields/footer/author and will 400 past it, but
        # to_dict() does not check `len(self)` against that limit anywhere -
        # unlike add_field()'s 25-field cap, which IS enforced locally.
        embed = Embed(description="x" * 7000)
        self.assertGreater(len(embed), 6000)
        self.assertEqual(embed.to_dict()["description"], "x" * 7000)


class TestEmbedCopyAndTimestampRoundTrip(unittest.TestCase):
    """ Regression test: Embed.from_dict() used to store the raw ISO8601
    timestamp *string* instead of parsing it back into a datetime, so
    to_dict()'s `isinstance(self.timestamp, datetime)` guard silently dropped
    the timestamp entirely on any *second* serialization - i.e. embed.copy()
    always lost its timestamp the moment the copy was serialized. """

    def test_copy_preserves_timestamp_across_two_serializations(self) -> None:
        original = Embed(title="t", timestamp=datetime(2024, 1, 1, tzinfo=UTC))
        copy = original.copy()

        self.assertIsInstance(copy.timestamp, datetime)
        self.assertIn("timestamp", copy.to_dict())

    def test_copy_is_not_field_list_aliased(self) -> None:
        original = Embed().add_field(name="a", value="b")
        copy = original.copy()
        copy.add_field(name="c", value="d")

        self.assertEqual(len(original.fields), 1)
        self.assertEqual(len(copy.fields), 2)


class TestEmbedToDictTimestampMutation(unittest.TestCase):
    def test_naive_datetime_is_localized_in_place(self) -> None:
        embed = Embed(title="t", timestamp=datetime(2024, 1, 1))  # naive
        self.assertIsNone(embed.timestamp.tzinfo)

        embed.to_dict()
        self.assertIsNotNone(embed.timestamp.tzinfo)


class TestEmbedSubObjectRoundTrips(unittest.TestCase):
    def test_optional_fields_omitted_when_falsy(self) -> None:
        embed = Embed(title="t").set_author(name="a")
        payload = embed.to_dict()["author"]
        self.assertNotIn("url", payload)
        self.assertNotIn("icon_url", payload)

    def test_from_dict_to_dict_round_trip(self) -> None:
        data = {
            "title": "t", "description": "d", "color": 255,
            "footer": {"text": "f"},
            "author": {"name": "a"},
            "fields": [{"name": "n", "value": "v", "inline": False}],
        }
        embed = Embed.from_dict(data)
        rebuilt = embed.to_dict()

        self.assertEqual(rebuilt["title"], "t")
        self.assertEqual(rebuilt["color"], 255)
        self.assertEqual(rebuilt["fields"][0]["inline"], False)


class TestEmbedReadOnlyFields(unittest.TestCase):
    def test_parses_provider_video_proxy_urls_and_flags(self) -> None:
        embed = Embed.from_dict({
            "type": "video", "flags": 1 << 5,
            "provider": {"name": "YouTube", "url": "https://youtube.com"},
            "video": {"url": "https://youtube.com/embed/x", "width": 1280},
            "author": {"name": "a", "icon_url": "https://a", "proxy_icon_url": "https://p/a"},
            "footer": {"text": "f", "icon_url": "https://f", "proxy_icon_url": "https://p/f"},
        })
        self.assertEqual(embed.provider.name, "YouTube")
        self.assertEqual(embed.video.url, "https://youtube.com/embed/x")
        self.assertEqual(embed.author.proxy_icon_url, "https://p/a")
        self.assertEqual(embed.footer.proxy_icon_url, "https://p/f")
        self.assertIn(EmbedFlags.is_content_inventory_entry, embed.flags)

    def test_read_only_fields_are_not_sent_back(self) -> None:
        payload = Embed.from_dict({
            "title": "t", "flags": 32,
            "provider": {"name": "p"}, "video": {"url": "https://v"},
            "author": {"name": "a", "proxy_icon_url": "https://p/a"},
            "footer": {"text": "f", "proxy_icon_url": "https://p/f"},
        }).to_dict()
        for key in ("provider", "video", "flags"):
            self.assertNotIn(key, payload)
        self.assertNotIn("proxy_icon_url", payload["author"])
        self.assertNotIn("proxy_icon_url", payload["footer"])

    def test_defaults_on_new_embed(self) -> None:
        embed = Embed()
        self.assertIsNone(embed.provider)
        self.assertIsNone(embed.video)
        self.assertEqual(int(embed.flags), 0)


class TestEmbedSetters(unittest.TestCase):
    def test_set_and_remove_chain(self) -> None:
        now = datetime.now(UTC)
        embed = (
            Embed()
            .set_title("title")
            .set_description(123)
            .set_url("https://example.com")
            .set_timestamp(now)
        )
        self.assertEqual(
            (embed.title, embed.description, embed.url, embed.timestamp),
            ("title", "123", "https://example.com", now)
        )

        embed.remove_title().remove_description().remove_url().remove_timestamp()
        self.assertEqual(embed.to_dict(), {})

    def test_set_none_removes(self) -> None:
        embed = Embed(title="a", description="b", url="https://example.com")
        embed.set_title(None).set_description(None).set_url(None).set_timestamp(None)
        self.assertEqual(embed.to_dict(), {})


if __name__ == "__main__":
    unittest.main()
