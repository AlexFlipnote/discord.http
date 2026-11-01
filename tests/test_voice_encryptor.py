import os
import struct
import unittest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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

    def test_decrypt_client_packet_with_extension(self) -> None:
        """ Only the extension preamble is AAD in rtpsize, its body is encrypted with the payload. """
        key = os.urandom(32)

        # base header with the extension bit (0x10) set on byte0
        base = struct.pack(">BBHII", 0x90, 0x78, 5, 6, 7)
        # one-byte RTP extension: 0xBE 0xDE profile, length = 1 word (4 bytes)
        preamble = b"\xbe\xde" + struct.pack(">H", 1)
        extension_body = b"\x01\x02\x03\x04"
        opus_frame = b"another-opus-frame"

        nonce = struct.pack(">I", 9)
        ciphertext = AESGCM(key).encrypt(nonce + b"\x00" * 8, extension_body + opus_frame, base + preamble)
        packet = base + preamble + ciphertext + nonce

        self.assertEqual(Encryptor(key).decrypt(packet), opus_frame)

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
