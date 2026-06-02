import io
import shutil
import struct
import subprocess
import unittest

from discord_http.voice.oggparse import OggPage, OggStream


def _build_page(
    body: bytes,
    segtable: bytes,
    *,
    header_type: int = 0,
    granule_position: int = 0,
    serial: int = 1,
    sequence: int = 0,
    crc: int = 0,
) -> bytes:
    """Build a single valid Ogg page from a body and a hand-crafted segment table."""
    if sum(segtable) != len(body):
        raise ValueError("segment table must sum to body length")
    header = struct.pack(
        "<4sBBQIIIB",
        b"OggS",
        0,  # version
        header_type,
        granule_position,
        serial,
        sequence,
        crc,
        len(segtable),
    )
    return header + segtable + body


class TestOggParse(unittest.TestCase):
    def test_single_page_single_packet(self) -> None:
        body = b"hello opus"
        page_bytes = _build_page(body, bytes([len(body)]))

        stream = OggStream(io.BytesIO(page_bytes))
        packets = list(stream.iter_packets())

        self.assertEqual(packets, [body])

    def test_page_header_fields_parsed(self) -> None:
        body = b"\x00\x01\x02\x03"
        page_bytes = _build_page(
            body,
            bytes([len(body)]),
            header_type=0x02,
            granule_position=12345,
            sequence=7,
        )

        # Skip the 4-byte magic, then parse the page directly.
        buffer = io.BytesIO(page_bytes)
        self.assertEqual(buffer.read(4), b"OggS")
        page = OggPage(buffer)

        self.assertEqual(page.header_type, 0x02)
        self.assertEqual(page.granule_position, 12345)
        self.assertEqual(page.page_sequence_number, 7)
        self.assertEqual(page.segtable, bytes([len(body)]))
        self.assertEqual(page.data, body)

    def test_multiple_packets_in_one_page(self) -> None:
        packet_a = b"first"
        packet_b = b"second-packet"
        body = packet_a + packet_b
        segtable = bytes([len(packet_a), len(packet_b)])

        stream = OggStream(io.BytesIO(_build_page(body, segtable)))
        self.assertEqual(list(stream.iter_packets()), [packet_a, packet_b])

    def test_packet_spanning_segments_via_255_lacing(self) -> None:
        # A packet exactly 255 bytes long needs a 255 lacing + a 0 lacing terminator.
        body = b"x" * 255
        segtable = bytes([255, 0])

        stream = OggStream(io.BytesIO(_build_page(body, segtable)))
        self.assertEqual(list(stream.iter_packets()), [body])

    def test_packet_spanning_pages(self) -> None:
        # First page ends mid-packet (trailing 255 lacing), second page continues it.
        head = b"a" * 255
        tail = b"bcd"
        page_one = _build_page(head, bytes([255]), sequence=0)
        page_two = _build_page(tail, bytes([len(tail)]), header_type=0x01, sequence=1)

        stream = OggStream(io.BytesIO(page_one + page_two))
        self.assertEqual(list(stream.iter_packets()), [head + tail])

    def test_scans_past_leading_garbage(self) -> None:
        body = b"payload"
        page_bytes = _build_page(body, bytes([len(body)]))

        stream = OggStream(io.BytesIO(b"garbage-before-magic" + page_bytes))
        self.assertEqual(list(stream.iter_packets()), [body])

    def test_ffmpeg_generated_opus_stream(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self.skipTest("ffmpeg not available on PATH")

        result = subprocess.run(  # noqa: S603
            [
                ffmpeg,
                "-f", "lavfi",
                "-i", "sine=frequency=440:duration=1",
                "-c:a", "libopus",
                "-f", "ogg",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        data = result.stdout
        self.assertTrue(data, "ffmpeg produced no output")

        packets = list(OggStream(io.BytesIO(data)).iter_packets())

        self.assertGreater(len(packets), 2)
        self.assertTrue(packets[0].startswith(b"OpusHead"))
        self.assertTrue(packets[1].startswith(b"OpusTags"))


if __name__ == "__main__":
    unittest.main()
