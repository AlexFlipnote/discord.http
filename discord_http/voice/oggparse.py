import struct

from collections.abc import Iterator
from typing import IO

__all__ = (
    "OggPage",
    "OggStream",
)

# 4-byte capture pattern that begins every Ogg page.
_OGG_MAGIC = b"OggS"

# Fixed header layout that follows the 4-byte capture pattern, little-endian:
#   x  - version (1 byte, ignored, must be 0)
#   B  - header_type (1 byte)
#   Q  - granule_position (8 bytes, signed treated as unsigned here)
#   I  - bitstream_serial_number (4 bytes)
#   I  - page_sequence_number (4 bytes)
#   I  - CRC checksum (4 bytes)
#   B  - page_segments (1 byte, number of segments N)
# This is exactly 23 bytes, mirroring discord.py's well-known approach.
_HEADER_STRUCT = struct.Struct("<xBQIIIB")


class OggPage:
    """
    A single parsed Ogg page.

    The page is read eagerly from ``stream``, which must be positioned right
    after a found ``b"OggS"`` capture pattern. The fixed 23-byte header is read
    via :class:`struct.Struct`, followed by the ``page_segments`` segment table
    and the page body.

    Reassembly of packets that may span pages is left to :class:`OggStream`;
    this class only exposes the raw segment table and body, plus a convenience
    :meth:`iter_packets` that walks the lacing values for a single page.

    Attributes
    ----------
    header_type:
        The page header type bitfield. Bit ``0x01`` means this page is a
        continuation of a packet from the previous page.
    granule_position:
        The granule position of the page (codec-defined sample counter).
    bitstream_serial_number:
        The serial number identifying the logical bitstream.
    page_sequence_number:
        The monotonically increasing page sequence number.
    crc_checksum:
        The CRC checksum stored in the page header (not verified).
    segtable:
        The raw segment table (lacing values) as ``bytes``.
    data:
        The raw page body, whose length equals the sum of the lacing values.
    """

    __slots__ = (
        "bitstream_serial_number",
        "crc_checksum",
        "data",
        "granule_position",
        "header_type",
        "page_sequence_number",
        "segtable",
    )

    def __init__(self, stream: IO[bytes]) -> None:
        header = stream.read(_HEADER_STRUCT.size)
        if len(header) < _HEADER_STRUCT.size:
            raise ValueError("Incomplete Ogg page header")

        (
            self.header_type,
            self.granule_position,
            self.bitstream_serial_number,
            self.page_sequence_number,
            self.crc_checksum,
            page_segments,
        ) = _HEADER_STRUCT.unpack(header)

        self.segtable = stream.read(page_segments)
        if len(self.segtable) < page_segments:
            raise ValueError("Incomplete Ogg page segment table")

        body_length = sum(self.segtable)
        self.data = stream.read(body_length)
        if len(self.data) < body_length:
            raise ValueError("Incomplete Ogg page body")

    def iter_packets(self) -> Iterator[tuple[bytes, bool]]:
        """
        Yield the packet chunks contained in this single page.

        Each yielded tuple is ``(packet_bytes, complete)`` where ``complete`` is
        ``True`` when the accumulated chunk terminates a packet within this page
        (the lacing value was ``0-254``) and ``False`` when the packet continues
        into the next page (the final lacing value was exactly ``255``).

        Yields
        ------
        tuple[bytes, bool]
            A chunk of packet data and whether it completes the packet.
        """
        offset = 0
        partial = bytearray()

        for lacing in self.segtable:
            chunk = self.data[offset:offset + lacing]
            offset += lacing
            partial += chunk

            if lacing < 255:
                yield bytes(partial), True
                partial = bytearray()

        # A trailing run of 255s means the packet spills into the next page.
        if partial:
            yield bytes(partial), False


class OggStream:
    """
    A reader that extracts raw Opus packets from an Ogg/Opus byte stream.

    The stream is scanned for ``b"OggS"`` capture patterns; each page is parsed
    into an :class:`OggPage` and packets are reassembled across page boundaries
    according to the Ogg lacing rules (a trailing lacing value of ``255``
    continues a packet into the following page).

    Notes
    -----
    The first two packets of a standard Ogg/Opus stream are the ``OpusHead`` and
    ``OpusTags`` metadata headers. They are yielded as-is; consumers that only
    want audio frames should skip any packet starting with ``b"OpusHead"`` or
    ``b"OpusTags"``. They are never silently dropped.
    """

    __slots__ = ("stream",)

    def __init__(self, stream: IO[bytes]) -> None:
        self.stream = stream

    def _find_next_page(self) -> bool:
        """
        Advance the stream to just after the next ``b"OggS"`` capture pattern.

        Returns
        -------
        bool
            ``True`` if a capture pattern was found, ``False`` at end of stream.
        """
        head = self.stream.read(4)
        if head == _OGG_MAGIC:
            return True

        # Slide a 4-byte window forward one byte at a time until the magic is
        # found or the stream is exhausted.
        while True:
            byte = self.stream.read(1)
            if not byte:
                return False

            head = head[1:] + byte
            if head == _OGG_MAGIC:
                return True

    def iter_pages(self) -> Iterator[OggPage]:
        """
        Yield each :class:`OggPage` found in the stream, in order.

        Yields
        ------
        OggPage
            The next parsed page.
        """
        while self._find_next_page():
            yield OggPage(self.stream)

    def iter_packets(self) -> Iterator[bytes]:
        """
        Yield fully reassembled Opus packets across page boundaries.

        Packets split by ``255`` lacing values, both within a page and across
        pages, are concatenated before being yielded.

        Yields
        ------
        bytes
            A complete Opus packet, including the ``OpusHead``/``OpusTags``
            header packets at the start of the stream.
        """
        partial = bytearray()

        for page in self.iter_pages():
            for chunk, complete in page.iter_packets():
                partial += chunk
                if complete:
                    yield bytes(partial)
                    partial = bytearray()

        # A stream that ends on a 255-run is malformed, but flush whatever we
        # accumulated rather than silently discarding trailing data.
        if partial:
            yield bytes(partial)
