import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

__all__ = (
    "Encryptor",
)


class Encryptor:
    """
    Handles Discord voice transport encryption.

    Implements the ``aead_aes256_gcm_rtpsize`` mode, which encrypts the RTP
    payload with AES-256-GCM while authenticating the unencrypted RTP header
    as additional authenticated data (AAD).
    """

    __slots__ = (
        "_aead",
        "_nonce",
    )

    def __init__(self, secret_key: bytes):
        self._aead = AESGCM(bytes(secret_key))
        self._nonce = 0

    def encrypt(self, header: bytes, plaintext: bytes) -> bytes:
        """
        Encrypt an RTP payload.

        Parameters
        ----------
        header:
            The unencrypted RTP header, used as the additional authenticated data.
        plaintext:
            The payload to encrypt, usually an Opus frame.

        Returns
        -------
            The packet, consisting of the header, the ciphertext, and the 4-byte big-endian nonce counter.
        """
        # Reusing a (key, nonce) pair with AES-GCM breaks the encryption entirely,
        # so refuse to wrap the 4-byte counter back to 0. At ~50 packets/sec this
        # takes ~2.7 years of one connection staying open, so a loud failure that
        # forces a reconnect (which rotates the secret key) is sufficient.
        if self._nonce >= 2 ** 32:
            raise RuntimeError(
                "voice nonce counter exhausted; reconnect to rotate the secret key"
            )

        nonce = self._nonce
        nonce_bytes = struct.pack(">I", nonce) + b"\x00" * 8
        ciphertext = self._aead.encrypt(nonce_bytes, plaintext, header)

        self._nonce += 1

        return header + ciphertext + struct.pack(">I", nonce)

    def decrypt(self, packet: bytes) -> bytes:
        """
        Decrypt a received RTP packet.

        Parameters
        ----------
        packet:
            The full received packet, including the header, ciphertext, and trailing nonce counter.

        Returns
        -------
            The decrypted payload with any RTP header extension body stripped, usually an Opus frame.
        """
        nonce_bytes = packet[-4:] + b"\x00" * 8

        offset = 12
        csrc_count = packet[0] & 0x0F
        offset += csrc_count * 4

        # In rtpsize modes only the 4-byte extension preamble (profile + length)
        # is authenticated as AAD, the extension body is encrypted with the payload
        extension_length = 0
        if packet[0] & 0x10:
            extension_length = struct.unpack(">H", packet[offset + 2:offset + 4])[0] * 4
            offset += 4

        header = packet[:offset]
        ciphertext = packet[offset:-4]

        return self._aead.decrypt(nonce_bytes, ciphertext, header)[extension_length:]
