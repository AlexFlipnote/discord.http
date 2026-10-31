import unittest

from discord_http import StickerPack

from _fake_client import FakeBot


class FakeState:
    def __init__(self):
        self.bot = FakeBot(self)


def _sticker_data(sticker_id: str) -> dict:
    return {
        "id": sticker_id, "pack_id": "100", "name": "wave", "description": "hi",
        "tags": "wave", "type": 1, "format_type": 1, "sort_value": 1,
    }


class TestStickerPack(unittest.TestCase):
    def test_parses_pack(self) -> None:
        pack = StickerPack(state=FakeState(), data={
            "id": "100", "name": "Wumpus Beyond", "sku_id": "101",
            "cover_sticker_id": "2", "description": "Say hello to Wumpus",
            "banner_asset_id": "761773777976819732",
            "stickers": [_sticker_data("1"), _sticker_data("2")],
        })

        self.assertEqual(pack.id, 100)
        self.assertEqual(pack.sku_id, 101)
        self.assertEqual([s.id for s in pack.stickers], [1, 2])
        self.assertEqual(pack.cover_sticker.id, 2)
        self.assertIsNone(pack.stickers[0].guild_id)
        self.assertEqual(
            pack.banner.url,
            "https://cdn.discordapp.com/app-assets/710982414301790216/store/761773777976819732.png?size=1024"
        )

    def test_optional_fields_absent(self) -> None:
        pack = StickerPack(state=FakeState(), data={
            "id": "100", "name": "p", "sku_id": "101", "description": "d", "stickers": [],
        })

        self.assertIsNone(pack.cover_sticker)
        self.assertIsNone(pack.banner)


if __name__ == "__main__":
    unittest.main()
