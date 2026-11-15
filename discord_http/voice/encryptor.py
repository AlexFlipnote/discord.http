import struct

from collections import deque

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

__all__ = (
    "Encryptor",
)

# How many received nonces are remembered to recognise a packet sent twice.
# At 50 packets a second per speaker this covers well over a minute
_REPLAY_WINDOW = 4096


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
        "_seen",
        "_seen_order",
    )

    def __init__(self, secret_key: bytes):
        self._aead = AESGCM(bytes(secret_key))
        self._nonce = 0
        self._seen: set[bytes] = set()
        self._seen_order: deque[bytes] = deque()

    def encrypt(self, header: bytes, plaintext: bytes) -> bytes:
        """
        Encrypt an RTP payload.

        Parameters
        ----------
        header
            The unencrypted RTP header, used as the additional authenticated data.
        plaintext
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
        packet
            The full received packet, including the header, ciphertext, and trailing nonce counter.

        Returns
        -------
            The decrypted payload with any RTP header extension body stripped, usually an Opus frame.

        Raises
        ------
        ValueError
            If a packet with the same nonce was already received.
        """
        nonce = packet[-4:]
        # A nonce is never used twice under one key, so seeing one again means
        # the packet was captured and sent a second time
        if nonce in self._seen:
            raise ValueError("Voice packet was already received (replayed nonce)")

        nonce_bytes = nonce + b"\x00" * 8

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

        plaintext = self._aead.decrypt(nonce_bytes, ciphertext, header)

        # Remembered only once the packet proved authentic, garbage can't fill the window
        self._seen.add(nonce)
        self._seen_order.append(nonce)
        if len(self._seen_order) > _REPLAY_WINDOW:
            self._seen.discard(self._seen_order.popleft())

        return plaintext[extension_length:]
