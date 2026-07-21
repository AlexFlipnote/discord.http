import tempfile
import unittest

from pathlib import Path

from discord_http.voice.sinks import VoiceData, WaveSink

class TestWaveSink(unittest.TestCase):
    def test_finalized_sink_cannot_truncate_existing_recording(self) -> None:
        """ Refuse WaveSink reuse instead of silently truncating its recording. """
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "recording.wav"
            sink = WaveSink(destination)
            data = VoiceData(user=1, pcm=b"\x00\x00\x00\x00", opus=None, timestamp=0, ssrc=1)

            sink.write(1, data)
            sink.cleanup()
            original = destination.read_bytes()

            with self.assertRaisesRegex(RuntimeError, "finalized"):
                sink.write(1, data)

            self.assertEqual(destination.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
