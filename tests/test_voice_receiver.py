import unittest

from discord_http.voice.receiver import VoiceReceiver
from discord_http.voice.sinks import AudioSink


class _Sink(AudioSink):
    def write(self, data) -> None:  # noqa: ANN001
        pass


class TestVoiceReceiverState(unittest.TestCase):
    def _receiver(self) -> VoiceReceiver:
        return VoiceReceiver(None)  # type: ignore[arg-type]

    def test_stop_keeps_ssrc_map(self) -> None:
        # SPEAKING is mapped before listen(), and start() calls stop() when a
        # sink is swapped, so stop() must not wipe the mappings.
        receiver = self._receiver()
        receiver.add_ssrc(1, 100)

        receiver.start(_Sink())
        receiver.start(_Sink())
        receiver.stop()

        self.assertEqual(receiver._ssrc_map, {1: 100})

    def test_reset_clears_ssrc_map(self) -> None:
        # SSRCs are reassigned across sessions, so teardown must forget them.
        receiver = self._receiver()
        receiver.add_ssrc(1, 100)
        receiver._dave_unmapped_drops = 7

        receiver.reset()

        self.assertEqual(receiver._ssrc_map, {})
        self.assertEqual(receiver._dave_unmapped_drops, 0)
        self.assertFalse(receiver.is_listening())


if __name__ == "__main__":
    unittest.main()
