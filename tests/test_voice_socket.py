import unittest

from unittest.mock import AsyncMock

import orjson

from discord_http.voice.enums import VoiceOpType
from discord_http.voice.socket import VoiceSocket

class _Connection:
    guild_id = 1

    def __init__(self) -> None:
        self.closed: list[int | None] = []

    def _on_socket_closed(self, close_code: int | None) -> None:
        self.closed.append(close_code)


class TestVoiceHeartbeat(unittest.IsolatedAsyncioTestCase):
    async def test_missing_ack_triggers_reconnect(self) -> None:
        """ Trigger reconnect when a heartbeat remains unacknowledged for an interval. """
        connection = _Connection()
        socket = VoiceSocket(connection)  # type: ignore[arg-type]
        socket._heartbeat_interval = 0
        socket._send_json = AsyncMock()  # type: ignore[method-assign]

        await socket._heartbeat_loop()

        socket._send_json.assert_awaited_once()
        self.assertEqual(connection.closed, [None])

    async def test_ack_clears_pending_heartbeat(self) -> None:
        """ Clear pending heartbeat state when the gateway acknowledges it. """
        connection = _Connection()
        socket = VoiceSocket(connection)  # type: ignore[arg-type]
        socket._send_json = AsyncMock()  # type: ignore[method-assign]

        await socket._send_heartbeat()
        self.assertTrue(socket._heartbeat_ack_pending)

        socket._dispatch_text(orjson.dumps({"op": int(VoiceOpType.heartbeat_ack), "d": {}}))

        self.assertFalse(socket._heartbeat_ack_pending)
        self.assertNotEqual(socket.latency, float("inf"))


if __name__ == "__main__":
    unittest.main()
