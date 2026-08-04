import unittest

from discord_http.voice.receiver import VoiceReceiver
from discord_http.voice.sinks import AudioSink, VoiceData

class _Sink(AudioSink):
    def __init__(self) -> None:
        self.cleaned = False

    def write(self, user: int | None, data: VoiceData) -> None:
        pass

    def cleanup(self) -> None:
        self.cleaned = True


class _Decoder:
    def __init__(self) -> None:
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


class TestVoiceReceiverState(unittest.TestCase):
    def _receiver(self) -> VoiceReceiver:
        return VoiceReceiver(None)  # type: ignore[arg-type]

    def test_stop_keeps_ssrc_map(self) -> None:
        """ Stop sink delivery without discarding eagerly collected SSRC mappings. """
        # SPEAKING is mapped before listen(), and start() calls stop() when a
        # sink is swapped, so stop() must not wipe the mappings.
        receiver = self._receiver()
        receiver.add_ssrc(1, 100)

        receiver.start(_Sink())
        receiver.start(_Sink())
        receiver.stop()

        self.assertEqual(receiver._ssrc_map, {1: 100})

    def test_reset_clears_ssrc_state_and_keeps_sink(self) -> None:
        """ Reset SSRC-keyed state without finalizing the active sink. """
        # READY allocates fresh SSRCs but a reconnect must keep the active sink.
        receiver = self._receiver()
        sink = _Sink()
        decoder = _Decoder()
        receiver.start(sink)
        receiver.add_ssrc(1, 100)
        receiver._last_seq[1] = 7
        receiver._decoders[1] = decoder  # type: ignore[assignment]
        receiver._dave_unmapped_drops = 7

        receiver.reset()

        self.assertEqual(receiver._ssrc_map, {})
        self.assertEqual(receiver._last_seq, {})
        self.assertEqual(receiver._decoders, {})
        self.assertEqual(receiver._dave_unmapped_drops, 0)
        self.assertTrue(decoder.cleaned)
        self.assertTrue(receiver.is_listening())
        self.assertIs(receiver.sink, sink)
        self.assertFalse(sink.cleaned)


if __name__ == "__main__":
    unittest.main()
