import os
import struct
import unittest

from discord_http.voice.encryptor import Encryptor


class TestVoiceEncryptor(unittest.TestCase):
    def test_mode(self) -> None:
        key = b"\x00" * 32
        enc = Encryptor(key)
        self.assertEqual(enc.mode, "aead_aes256_gcm_rtpsize")

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


if __name__ == "__main__":
    unittest.main()
