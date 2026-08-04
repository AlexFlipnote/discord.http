import asyncio
import unittest

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from discord_http.voice.connection import VoiceConnection

class TestVoiceServerMigration(unittest.IsolatedAsyncioTestCase):
    def _connection(self) -> VoiceConnection:
        connection = object.__new__(VoiceConnection)
        connection.guild_id = 1
        connection.token = "old-token"
        connection.endpoint = "old.discord.media:443"
        connection.server_id = 1
        connection._server_event = asyncio.Event()
        connection._connected_event = asyncio.Event()
        connection._connected_event.set()
        connection._closing = False
        connection._reconnect_task = None
        connection._move_target_channel_id = None
        connection._move_server_update_received = False
        return connection

    async def test_changed_server_credentials_schedule_migration(self) -> None:
        """ Schedule migration after connected credentials change. """
        connection = self._connection()
        connection._migrate_voice_server = AsyncMock()  # type: ignore[method-assign]

        connection.on_voice_server_update(
            {
                "token": "new-token",
                "endpoint": "new.discord.media:2053",
                "guild_id": "1",
            }
        )
        task = connection._reconnect_task
        self.assertIsNotNone(task)
        await task

        self.assertEqual(connection.token, "new-token")
        self.assertEqual(connection.endpoint, "new.discord.media:2053")
        connection._migrate_voice_server.assert_awaited_once()

    async def test_unchanged_server_credentials_do_not_migrate(self) -> None:
        """ Leave the active connection alone when credentials are unchanged. """
        connection = self._connection()
        connection._migrate_voice_server = AsyncMock()  # type: ignore[method-assign]

        connection.on_voice_server_update(
            {
                "token": "old-token",
                "endpoint": "old.discord.media:443",
                "guild_id": "1",
            }
        )

        self.assertIsNone(connection._reconnect_task)
        connection._migrate_voice_server.assert_not_awaited()

    async def test_move_waits_for_state_update_when_server_update_arrives_first(self) -> None:
        """ Pair move updates before identifying a replacement voice session. """
        connection = self._connection()
        shard = SimpleNamespace(change_voice_state=AsyncMock())
        receiver = SimpleNamespace(reset=Mock())
        connection.voice_client = SimpleNamespace(_receiver=receiver)
        connection._get_shard = Mock(return_value=shard)  # type: ignore[method-assign]
        connection._migrate_voice_server = AsyncMock()  # type: ignore[method-assign]
        connection.channel_id = 123
        connection.session_id = "old-session"
        connection._left_event = asyncio.Event()
        connection._state_event = asyncio.Event()

        await connection.move_to(SimpleNamespace(id=456))  # type: ignore[arg-type]
        connection.on_voice_server_update({
            "token": "new-token",
            "endpoint": "old.discord.media:443",
            "guild_id": "1",
        })

        self.assertIsNone(connection._reconnect_task)
        self.assertTrue(connection._move_server_update_received)

        connection.on_voice_state_update({"session_id": "new-session", "channel_id": "456"})
        task = connection._reconnect_task
        self.assertIsNotNone(task)
        await task

        connection._migrate_voice_server.assert_awaited_once()
        self.assertEqual(connection.session_id, "new-session")

    async def test_move_waits_for_server_update_when_state_update_arrives_first(self) -> None:
        """ Do not reuse old credentials after the gateway acknowledges a move first. """
        connection = self._connection()
        shard = SimpleNamespace(change_voice_state=AsyncMock())
        receiver = SimpleNamespace(reset=Mock())
        connection.voice_client = SimpleNamespace(_receiver=receiver)
        connection._get_shard = Mock(return_value=shard)  # type: ignore[method-assign]
        connection._migrate_voice_server = AsyncMock()  # type: ignore[method-assign]
        connection.channel_id = 123
        connection.session_id = "old-session"
        connection._left_event = asyncio.Event()
        connection._state_event = asyncio.Event()

        await connection.move_to(SimpleNamespace(id=456))  # type: ignore[arg-type]
        connection.on_voice_state_update({"session_id": "new-session", "channel_id": "456"})

        self.assertIsNone(connection._reconnect_task)

        connection.on_voice_server_update({
            "token": "new-token",
            "endpoint": "old.discord.media:443",
            "guild_id": "1",
        })
        task = connection._reconnect_task
        self.assertIsNotNone(task)
        await task

        connection._migrate_voice_server.assert_awaited_once()
        receiver.reset.assert_called_once_with()

    async def test_failed_soft_migration_forces_voice_refresh(self) -> None:
        """ Refresh gateway voice state when direct migration fails. """
        connection = self._connection()
        connection._soft_reconnect = AsyncMock(return_value=False)  # type: ignore[method-assign]
        connection._full_reconnect = AsyncMock()  # type: ignore[method-assign]

        await connection._migrate_voice_server()

        connection._soft_reconnect.assert_awaited_once()
        connection._full_reconnect.assert_awaited_once_with(None, force_refresh=True)

    async def test_move_clears_ssrc_state_after_gateway_update(self) -> None:
        """ Reset SSRC state only after the gateway acknowledges a move. """
        connection = self._connection()
        shard = SimpleNamespace(change_voice_state=AsyncMock())
        receiver = SimpleNamespace(reset=Mock())
        connection.voice_client = SimpleNamespace(_receiver=receiver)
        connection._get_shard = Mock(return_value=shard)  # type: ignore[method-assign]
        connection.channel_id = 123
        connection.session_id = "session"
        connection._left_event = asyncio.Event()
        connection._state_event = asyncio.Event()
        channel = SimpleNamespace(id=456)

        await connection.move_to(channel)  # type: ignore[arg-type]

        shard.change_voice_state.assert_awaited_once_with(guild_id=1, channel_id=456)
        self.assertEqual(connection.channel_id, 123)
        receiver.reset.assert_not_called()

        connection.on_voice_state_update({"session_id": "session", "channel_id": "456"})

        self.assertEqual(connection.channel_id, 456)
        receiver.reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
