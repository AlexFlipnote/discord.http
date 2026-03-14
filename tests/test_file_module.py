import io
import tempfile
import unittest

from pathlib import Path

from discord_http import File


class TestFile(unittest.TestCase):
    def test_bytes_io_requires_filename(self) -> None:
        with self.assertRaises(ValueError):
            File(io.BytesIO(b"abc"))

    def test_bytes_io_roundtrip_and_reset(self) -> None:
        buffer = io.BytesIO(b"abcdef")
        file = File(buffer, filename="sample.bin")

        self.assertEqual(file.filename, "sample.bin")
        self.assertEqual(file.data.read(2), b"ab")
        file.reset()
        self.assertEqual(file.data.read(3), b"abc")

    def test_spoiler_prefix(self) -> None:
        file = File(io.BytesIO(b"abc"), filename="x.txt", spoiler=True)
        self.assertEqual(file.filename, "SPOILER_x.txt")

    def test_to_dict_includes_optional_metadata(self) -> None:
        file = File(
            io.BytesIO(b"abc"),
            filename="voice.ogg",
            title="Voice",
            description="Test",
            duration_secs=3,
            waveform="wave",
        )
        payload = file.to_dict(0)

        self.assertEqual(payload["id"], 0)
        self.assertEqual(payload["filename"], "voice.ogg")
        self.assertEqual(payload["title"], "Voice")
        self.assertEqual(payload["description"], "Test")
        self.assertEqual(payload["duration_secs"], 3)
        self.assertEqual(payload["waveform"], "wave")

    def test_path_input_opens_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"hello")
            temp_path = Path(tmp.name)

        try:
            file = File(str(temp_path))
            self.assertEqual(file.filename, temp_path.name)
            self.assertEqual(file.data.read(), b"hello")
            file.close()
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
