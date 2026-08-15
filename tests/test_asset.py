import unittest

from discord_http.asset import Asset


class FakeState:
    pass


class TestFromAvatarAnimatedDetection(unittest.TestCase):
    def test_a__prefix_is_animated_and_uses_gif(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "a_abc123")
        self.assertTrue(asset.animated)
        self.assertTrue(asset.url.endswith(".gif?size=1024"))

    def test_no_prefix_is_static_and_uses_png(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc123")
        self.assertFalse(asset.animated)
        self.assertTrue(asset.url.endswith(".png?size=1024"))


class TestAnimatedDetectionConsistencyAcrossFromMethods(unittest.TestCase):
    """ Every `_from_*` classmethod that accepts a Discord image hash detects
    animation the same way: an `a_` prefix on the hash. This is a regression
    guard so a future refactor can't silently drop the check on one of them. """

    def test_from_guild_avatar(self) -> None:
        animated = Asset._from_guild_avatar(FakeState(), 1, 2, "a_hash")
        static = Asset._from_guild_avatar(FakeState(), 1, 2, "hash")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)

    def test_from_guild_clan_badge(self) -> None:
        animated = Asset._from_guild_clan_badge(FakeState(), 1, "a_hash")
        static = Asset._from_guild_clan_badge(FakeState(), 1, "hash")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)

    def test_from_guild_banner(self) -> None:
        animated = Asset._from_guild_banner(FakeState(), 1, 2, "a_hash")
        static = Asset._from_guild_banner(FakeState(), 1, 2, "hash")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)

    def test_from_guild_image(self) -> None:
        animated = Asset._from_guild_image(FakeState(), 1, "a_hash", "icons")
        static = Asset._from_guild_image(FakeState(), 1, "hash", "icons")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)

    def test_from_application_image(self) -> None:
        animated = Asset._from_application_image(FakeState(), 1, "a_hash")
        static = Asset._from_application_image(FakeState(), 1, "hash")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)

    def test_from_application_asset(self) -> None:
        animated = Asset._from_application_asset(FakeState(), 1, "a_hash")
        static = Asset._from_application_asset(FakeState(), 1, "hash")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)

    def test_from_banner(self) -> None:
        animated = Asset._from_banner(FakeState(), 1, "a_hash")
        static = Asset._from_banner(FakeState(), 1, "hash")
        self.assertTrue(animated.animated)
        self.assertFalse(static.animated)


class TestAlwaysStaticFromMethods(unittest.TestCase):
    def test_from_default_avatar_is_never_animated(self) -> None:
        asset = Asset._from_default_avatar(FakeState(), 3)
        self.assertFalse(asset.animated)

    def test_from_collectibles_is_never_animated(self) -> None:
        asset = Asset._from_collectibles(FakeState(), "img")
        self.assertFalse(asset.animated)

    def test_from_scheduled_event_cover_image_is_never_animated(self) -> None:
        asset = Asset._from_scheduled_event_cover_image(FakeState(), 1, "cover")
        self.assertFalse(asset.animated)

    def test_from_icon_is_never_animated(self) -> None:
        asset = Asset._from_icon(FakeState(), 1, "hash", "team")
        self.assertFalse(asset.animated)


class TestFromAvatarDecorationTwoPrefixCase(unittest.TestCase):
    """ Avatar decorations use TWO distinct animated prefixes, unlike every
    other asset type which only checks `a_`. """

    def test_legacy_a__prefix_is_animated(self) -> None:
        asset = Asset._from_avatar_decoration(FakeState(), "a_deco")
        self.assertTrue(asset.animated)

    def test_v2_a__prefix_is_animated(self) -> None:
        asset = Asset._from_avatar_decoration(FakeState(), "v2_a_deco")
        self.assertTrue(asset.animated)

    def test_plain_hash_is_not_animated(self) -> None:
        asset = Asset._from_avatar_decoration(FakeState(), "deco")
        self.assertFalse(asset.animated)

    def test_v2_without_a_prefix_is_not_animated(self) -> None:
        asset = Asset._from_avatar_decoration(FakeState(), "v2_deco")
        self.assertFalse(asset.animated)


class TestFromActivityAssetMpRouting(unittest.TestCase):
    def test_mp_prefixed_image_routes_through_media_proxy(self) -> None:
        asset = Asset._from_activity_asset(FakeState(), 1, "mp:external/foo.png")
        self.assertTrue(asset.url.startswith(Asset.PROXY))
        self.assertEqual(asset.url, f"{Asset.PROXY}/mp:external/foo.png")

    def test_non_mp_image_routes_through_cdn_app_assets(self) -> None:
        asset = Asset._from_activity_asset(FakeState(), 1, "abc123")
        self.assertTrue(asset.url.startswith(Asset.BASE))
        self.assertIn("/app-assets/1/abc123.png", asset.url)


class TestReplace(unittest.TestCase):
    def test_format_change_updates_extension(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc")
        replaced = asset.replace(format="webp")
        self.assertTrue(replaced.url.split("?")[0].endswith(".webp"))

    def test_format_change_to_gif_marks_animated(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc")  # static source
        replaced = asset.replace(format="gif")
        self.assertTrue(replaced.animated)

    def test_format_change_to_png_marks_not_animated(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "a_abc")  # animated source
        replaced = asset.replace(format="png")
        self.assertFalse(replaced.animated)

    def test_format_change_preserves_existing_size_query(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc")  # has ?size=1024
        replaced = asset.replace(format="webp")
        self.assertEqual(replaced.url.split("size=")[1].split("&")[0], "1024")

    def test_size_change_updates_query_only(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc")
        replaced = asset.replace(size=256)
        self.assertIn("size=256", replaced.url)
        self.assertTrue(replaced.url.split("?")[0].endswith(".png"))

    def test_replace_preserves_key(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc")
        replaced = asset.replace(size=256)
        self.assertEqual(replaced.key, asset.key)

    def test_replace_returns_new_instance_original_untouched(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "abc")
        original_url = asset.url
        asset.replace(size=256)
        self.assertEqual(asset.url, original_url)


class TestWithStaticFormat(unittest.TestCase):
    def test_delegates_to_replace_with_format(self) -> None:
        asset = Asset._from_avatar(FakeState(), 1, "a_abc")
        result = asset.with_static_format("png")
        self.assertFalse(result.animated)
        self.assertTrue(result.url.split("?")[0].endswith(".png"))


if __name__ == "__main__":
    unittest.main()
