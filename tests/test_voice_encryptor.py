import os
import struct
import unittest

from discord_http.voice.encryptor import Encryptor


class TestVoiceEncryptor(unittest.TestCase):
    def test_roundtrip_basic_header(self) -> None:
        key = os.urandom(32)
        header = struct.pack(">BBHII", 0x80, 0x78, 1, 2, 3)
        plaintext = b"opus-frame-data"

        sender = Encryptor(key)
        packet = sender.encrypt(header, plaintext)

        self.assertEqual(packet[:12], header)
        self.assertEqual(packet[-4:], struct.pack(">I", 0))

        receiver = Encryptor(key)
        self.assertEqual(receiver.decrypt(packet), plaintext)

    def test_roundtrip_with_extension(self) -> None:
        key = os.urandom(32)

        # base header with the extension bit (0x10) set on byte0
        base = struct.pack(">BBHII", 0x90, 0x78, 5, 6, 7)
        # one-byte RTP extension: 0xBE 0xDE profile, length = 1 word (4 bytes)
        extension = b"\xbe\xde" + struct.pack(">H", 1) + b"\x01\x02\x03\x04"
        header = base + extension
        plaintext = b"another-opus-frame"

        sender = Encryptor(key)
        packet = sender.encrypt(header, plaintext)

        self.assertEqual(packet[:len(header)], header)

        receiver = Encryptor(key)
        self.assertEqual(receiver.decrypt(packet), plaintext)

    def test_nonce_increments(self) -> None:
        key = os.urandom(32)
        header = struct.pack(">BBHII", 0x80, 0x78, 1, 2, 3)

        sender = Encryptor(key)
        first = sender.encrypt(header, b"a")
        second = sender.encrypt(header, b"a")

        self.assertEqual(first[-4:], struct.pack(">I", 0))
        self.assertEqual(second[-4:], struct.pack(">I", 1))

    def test_nonce_exhaustion_raises(self) -> None:
        # Reusing a (key, nonce) pair with AES-GCM is catastrophic, so the
        # counter must refuse to wrap back to 0 instead of silently reusing.
        key = os.urandom(32)
        header = struct.pack(">BBHII", 0x80, 0x78, 1, 2, 3)

        sender = Encryptor(key)
        sender._nonce = 2 ** 32 - 1
        packet = sender.encrypt(header, b"a")
        self.assertEqual(packet[-4:], struct.pack(">I", 2 ** 32 - 1))

        with self.assertRaises(RuntimeError):
            sender.encrypt(header, b"a")


if __name__ == "__main__":
    unittest.main()
