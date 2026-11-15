import asyncio
import os
import struct
import unittest

from types import SimpleNamespace
from unittest import mock

from discord_http.errors import OpusError
from discord_http.voice import opus
from discord_http.voice.encryptor import _REPLAY_WINDOW, Encryptor
from discord_http.voice.gateway_udp import VoiceUDPProtocol


def _packet(sender: Encryptor, sequence: int = 1) -> bytes:
    return sender.encrypt(struct.pack(">BBHII", 0x80, 0x78, sequence, 960 * sequence, 3), b"opus-frame")


class TestReplayedPackets(unittest.TestCase):
    def test_same_packet_is_only_accepted_once(self) -> None:
        key = os.urandom(32)
        receiver = Encryptor(key)
        packet = _packet(Encryptor(key))

        self.assertEqual(receiver.decrypt(packet), b"opus-frame")
        with self.assertRaises(ValueError):
            receiver.decrypt(packet)

    def test_out_of_order_packets_are_accepted(self) -> None:
        key = os.urandom(32)
        sender, receiver = Encryptor(key), Encryptor(key)
        packets = [_packet(sender, i) for i in range(1, 6)]

        for packet in (packets[3], packets[0], packets[4], packets[1], packets[2]):
            self.assertEqual(receiver.decrypt(packet), b"opus-frame")

    def test_forged_packet_does_not_block_the_real_one(self) -> None:
        key = os.urandom(32)
        receiver = Encryptor(key)
        packet = _packet(Encryptor(key))
        forged = packet[:12] + bytes(len(packet) - 16) + packet[-4:]

        with self.assertRaises(Exception):
            receiver.decrypt(forged)
        self.assertEqual(receiver.decrypt(packet), b"opus-frame")

    def test_window_is_bounded(self) -> None:
        key = os.urandom(32)
        sender, receiver = Encryptor(key), Encryptor(key)
        for i in range(_REPLAY_WINDOW + 50):
            receiver.decrypt(_packet(sender, i & 0xFFFF))

        self.assertEqual(len(receiver._seen), _REPLAY_WINDOW)
        self.assertEqual(len(receiver._seen_order), _REPLAY_WINDOW)


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
