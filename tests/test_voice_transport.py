import asyncio
import struct
import unittest

from types import SimpleNamespace
from unittest import mock

from discord_http.errors import OpusError
from discord_http.voice import opus
from discord_http.voice.gateway_udp import VoiceUDPProtocol


class TestIpDiscovery(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _response(ssrc: int, ip: bytes = b"198.51.100.7", port: int = 4444) -> bytes:
        return struct.pack(">HHI", 2, 70, ssrc) + ip.ljust(64, b"\x00") + struct.pack(">H", port)

    async def test_response_for_another_ssrc_is_ignored(self) -> None:
        unpack = mock.Mock()
        proto = VoiceUDPProtocol(SimpleNamespace(voice_client=SimpleNamespace(_receiver=SimpleNamespace(unpack=unpack))))  # type: ignore[arg-type]
        proto.transport = mock.Mock()

        discovery = asyncio.ensure_future(proto.discover_ip(1000))
        await asyncio.sleep(0)

        proto.datagram_received(self._response(0xDEADBEEF, b"203.0.113.66"), ("1.2.3.4", 5))
        await asyncio.sleep(0)
        self.assertFalse(discovery.done())

        proto.datagram_received(self._response(1000), ("1.2.3.4", 5))
        self.assertEqual(await discovery, ("198.51.100.7", 4444))


class TestEncoderFrameLength(unittest.TestCase):
    def _encoder(self) -> tuple[opus.Encoder, mock.Mock]:
        lib = mock.Mock()
        lib.opus_encode.return_value = 3
        encoder = opus.Encoder.__new__(opus.Encoder)
        encoder._state = 0
        encoder._lib = lib
        return encoder, lib

    def test_short_and_long_frames_never_reach_libopus(self) -> None:
        encoder, lib = self._encoder()
        for size in (0, 2, opus.FRAME_SIZE - 2, opus.FRAME_SIZE + 2):
            with self.subTest(size=size), self.assertRaises(OpusError):
                encoder.encode(b"\x00" * size)
        lib.opus_encode.assert_not_called()

    def test_full_frame_is_encoded(self) -> None:
        encoder, lib = self._encoder()
        self.assertEqual(len(encoder.encode(b"\x00" * opus.FRAME_SIZE)), 3)
        self.assertEqual(lib.opus_encode.call_args.args[4].value, opus.MAX_PACKET_SIZE)


if __name__ == "__main__":
    unittest.main()
