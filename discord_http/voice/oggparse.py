import struct

from collections.abc import Iterator
from typing import IO

__all__ = (
    "OggPage",
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

    Reassembly of packets that may span pages is left to the caller; this
    class only exposes the raw segment table and body, plus a convenience
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
