import asyncio
import io
import shutil
import struct
import unittest

from discord_http.voice.oggparse import OggPage


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


def _parse_page(page_bytes: bytes) -> OggPage:
    """Parse a single page built by ``_build_page``, skipping the 4-byte magic."""
    buffer = io.BytesIO(page_bytes)
    assert buffer.read(4) == b"OggS"
    return OggPage(buffer)


class TestOggParse(unittest.TestCase):
    def test_page_header_fields_parsed(self) -> None:
        body = b"\x00\x01\x02\x03"
        page = _parse_page(_build_page(
            body,
            bytes([len(body)]),
            header_type=0x02,
            granule_position=12345,
            sequence=7,
        ))

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

        page = _parse_page(_build_page(body, segtable))
        self.assertEqual(
            list(page.iter_packets()),
            [(packet_a, True), (packet_b, True)],
        )

    def test_packet_spanning_segments_via_255_lacing(self) -> None:
        # A packet exactly 255 bytes long needs a 255 lacing + a 0 lacing terminator.
        body = b"x" * 255
        segtable = bytes([255, 0])

        page = _parse_page(_build_page(body, segtable))
        self.assertEqual(list(page.iter_packets()), [(body, True)])

    def test_packet_spanning_pages(self) -> None:
        # First page ends mid-packet (trailing 255 lacing), second page continues it.
        head = b"a" * 255
        tail = b"bcd"
        page_one = _parse_page(_build_page(head, bytes([255]), sequence=0))
        page_two = _parse_page(_build_page(tail, bytes([len(tail)]), header_type=0x01, sequence=1))

        self.assertEqual(list(page_one.iter_packets()), [(head, False)])
        self.assertEqual(list(page_two.iter_packets()), [(tail, True)])

    def test_truncated_page_raises(self) -> None:
        body = b"payload"
        page_bytes = _build_page(body, bytes([len(body)]))

        # Chop off the last body byte; parsing must fail rather than mis-parse.
        with self.assertRaises(ValueError):
            _parse_page(page_bytes[:-1])

    def test_ffmpeg_generated_opus_stream(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg not available on PATH")

        from discord_http.voice.player import FFmpegOpusAudio

        async def read_all() -> list[bytes]:
            source = FFmpegOpusAudio(
                "sine=frequency=440:duration=1",
                before_options="-f lavfi",
            )
            packets = []
            try:
                while packet := await source.read():
                    packets.append(packet)
            finally:
                source.cleanup()
            return packets

        packets = asyncio.run(read_all())

        # The OpusHead/OpusTags header packets are filtered out by the source,
        # so everything left must be audio packets.
        self.assertGreater(len(packets), 0)
        for packet in packets:
            self.assertFalse(packet.startswith((b"OpusHead", b"OpusTags")))


if __name__ == "__main__":
    unittest.main()
