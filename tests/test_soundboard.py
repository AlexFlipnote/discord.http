import unittest

from discord_http import SoundboardSound

from _fake_client import FakeBot


class FakeCache:
    def get_guild(self, guild_id):
        return None


class FakeState:
    def __init__(self):
        self.cache = FakeCache()
        self.bot = FakeBot(self)


class TestSoundboardSound(unittest.TestCase):
    def test_default_sound_has_no_guild(self) -> None:
        sound = SoundboardSound(state=FakeState(), guild=None, data={
            "name": "quack", "sound_id": "1", "volume": 1.0,
            "emoji_id": None, "emoji_name": "\U0001F986", "available": True,
        })

        self.assertEqual(sound.id, 1)
        self.assertIsNone(sound.guild_id)
        self.assertIsNone(sound.guild)
        self.assertIsNone(sound.emoji)
        self.assertEqual(sound.emoji_name, "\U0001F986")

    def test_guild_id_falls_back_to_payload(self) -> None:
        sound = SoundboardSound(state=FakeState(), guild=None, data={
            "name": "Yay", "sound_id": "2", "volume": 0.5,
            "emoji_id": "3", "emoji_name": None, "guild_id": "4", "available": True,
        })

        self.assertEqual(sound.guild_id, 4)
        self.assertEqual(sound.emoji.id, 3)


if __name__ == "__main__":
    unittest.main()
