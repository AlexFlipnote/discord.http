import asyncio
import logging
import struct

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import VoiceConnection

__all__ = ("VoiceUDPProtocol",)

_log = logging.getLogger(__name__)


class VoiceUDPProtocol(asyncio.DatagramProtocol):
    """
    The UDP transport protocol for Discord voice.

    Handles IP discovery, routes inbound RTP packets to the receiver, and
    drops RTCP control traffic.
    """

    def __init__(self, connection: "VoiceConnection"):
        self.connection: "VoiceConnection" = connection
        """ The voice connection that owns this protocol. """

        self.transport: asyncio.DatagramTransport | None = None
        """ The UDP datagram transport, if connected. """

        self._discovery_future: asyncio.Future[bytes] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """
        Store the transport once the endpoint is created.

        Parameters
        ----------
        transport:
            The datagram transport for this protocol.
        """
        self.transport = transport  # type: ignore[assignment]

    def error_received(self, exc: Exception) -> None:
        """
        Log a transport-level error.

        Parameters
        ----------
        exc:
            The exception reported by the transport.
        """
        _log.warning("Voice UDP error for guild %s: %s", self.connection.guild_id, exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """
        Handle the transport being closed.

        Parameters
        ----------
        exc:
            The exception that caused the loss, if any.
        """
        if exc is not None:
            _log.debug("Voice UDP connection lost for guild %s", self.connection.guild_id, exc_info=exc)
        self.transport = None

    def datagram_received(self, data: bytes, addr: tuple) -> None:  # noqa: ARG002
        """
        Route an inbound datagram to the right consumer.

        Parameters
        ----------
        data:
            The raw datagram payload.
        addr:
            The source address of the datagram.
        """
        if len(data) < 2:
            return

        # IP discovery response (type 0x0002 in the second byte).
        if data[1] == 0x02 and self._discovery_future is not None and not self._discovery_future.done():
            self._discovery_future.set_result(data)
            return

        # Drop RTCP control packets (payload types 200-204).
        payload_type = data[1] & 0x7F
        if 200 <= payload_type <= 204:
            return

        # Otherwise treat it as RTP and hand it to the receiver, if any.
        receiver = self.connection.voice_client._receiver
        if receiver is not None:
            receiver.unpack(data)

    async def discover_ip(self, ssrc: int) -> tuple[str, int]:
        """
        Perform IP discovery to learn this client's external address.

        Parameters
        ----------
        ssrc:
            The SSRC assigned by the voice gateway.

        Returns
        -------
            The externally visible IP address and UDP port.

        Raises
        ------
        RuntimeError
            If the transport is not available.
        """
        if self.transport is None:
            raise RuntimeError("UDP transport is not available for IP discovery")

        loop = asyncio.get_running_loop()
        self._discovery_future = loop.create_future()

        request = struct.pack(">HHI", 0x1, 70, ssrc) + b"\x00" * 66
        self.transport.sendto(request)

        try:
            data = await asyncio.wait_for(self._discovery_future, timeout=20.0)
        finally:
            self._discovery_future = None

        # External IP is a null-terminated string starting at offset 8.
        ip_end = data.index(0, 8)
        ip = data[8:ip_end].decode("ascii")
        port = struct.unpack_from(">H", data, len(data) - 2)[0]

        return ip, port


async def create_udp(
    connection: "VoiceConnection",
    ip: str,
    port: int
) -> tuple[asyncio.DatagramTransport, VoiceUDPProtocol]:
    """
    Create a connected UDP datagram endpoint for voice.

    Parameters
    ----------
    connection:
        The voice connection that owns the new protocol.
    ip:
        The voice server IP address to connect to.
    port:
        The voice server UDP port to connect to.

    Returns
    -------
        The datagram transport and its protocol.
    """
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: VoiceUDPProtocol(connection),
        remote_addr=(ip, port),
    )
    return transport, protocol
