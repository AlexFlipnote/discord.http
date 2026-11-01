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
        connection._full_reconnect.assert_awaited_once_with(None)

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


class TestVoiceCloseHandling(unittest.IsolatedAsyncioTestCase):
    def _connection(self) -> VoiceConnection:
        connection = object.__new__(VoiceConnection)
        connection.guild_id = 1
        connection._closing = False
        connection._reconnect = True
        connection._reconnect_task = None
        connection._move_target_channel_id = None
        connection._move_server_update_received = False
        connection._soft_reconnect = AsyncMock(return_value=True)  # type: ignore[method-assign]
        connection._full_reconnect = AsyncMock()  # type: ignore[method-assign]
        connection._teardown_and_remove = AsyncMock()  # type: ignore[method-assign]
        return connection

    async def test_unexpected_close_tries_soft_reconnect_first(self) -> None:
        """ Reuse the current credentials before leaving and rejoining. """
        connection = self._connection()

        await connection._handle_close(1006)

        connection._soft_reconnect.assert_awaited_once()
        connection._full_reconnect.assert_not_awaited()

    async def test_failed_soft_reconnect_falls_back_to_rejoin(self) -> None:
        connection = self._connection()
        connection._soft_reconnect.return_value = False

        await connection._handle_close(1006)

        connection._full_reconnect.assert_awaited_once_with(1006)

    async def test_disconnected_during_move_is_ignored(self) -> None:
        """ A cross-server move closes the old socket with 4014 before the new server arrives. """
        connection = self._connection()
        connection._move_target_channel_id = 456

        await connection._handle_close(4014)

        connection._teardown_and_remove.assert_not_awaited()
        connection._full_reconnect.assert_not_awaited()

    async def test_disconnected_without_move_tears_down(self) -> None:
        connection = self._connection()

        await connection._handle_close(4014)

        connection._teardown_and_remove.assert_awaited_once()

    async def test_removed_from_voice_during_move_tears_down(self) -> None:
        """ A real kick while a move is pending still tears down, as its 4014 was ignored. """
        connection = self._connection()
        connection._move_target_channel_id = 456
        connection.session_id = "session"
        connection.channel_id = 123
        connection._left_event = asyncio.Event()
        connection._state_event = asyncio.Event()

        connection.on_voice_state_update({"session_id": "session", "channel_id": None})
        task = connection._reconnect_task
        self.assertIsNotNone(task)
        await task

        self.assertIsNone(connection._move_target_channel_id)
        connection._teardown_and_remove.assert_awaited_once()

    async def test_full_reconnect_always_refreshes_voice_state(self) -> None:
        """ Re-issuing op4 to the current channel yields no VOICE_SERVER_UPDATE, so always leave first. """
        connection = self._connection()
        del connection._full_reconnect
        connection.socket = None
        connection.transport = None
        connection.udp = None
        connection._reconnect_on_session_invalid = False
        connection._self_deaf = False
        connection._self_mute = False
        connection._backoff = Mock(delay=Mock(return_value=0))
        connection.voice_client = SimpleNamespace(bot=SimpleNamespace(voice_reconnect_attempts=1))
        connection._force_voice_refresh = AsyncMock()  # type: ignore[method-assign]
        connection._connect = AsyncMock()  # type: ignore[method-assign]

        await connection._full_reconnect(1006)

        connection._force_voice_refresh.assert_awaited_once()
        connection._connect.assert_awaited_once()


class TestCallTerminatedDuringMove(unittest.IsolatedAsyncioTestCase):
    def _connection(self) -> VoiceConnection:
        return TestVoiceCloseHandling._connection(self)  # type: ignore[arg-type]

    async def test_call_terminated_during_move_is_ignored(self) -> None:
        """ Discord also closes the old socket with 4022 when moving. """
        connection = self._connection()
        connection._move_target_channel_id = 456

        await connection._handle_close(4022)

        connection._teardown_and_remove.assert_not_awaited()

    async def test_call_terminated_without_move_tears_down(self) -> None:
        connection = self._connection()

        await connection._handle_close(4022)

        connection._teardown_and_remove.assert_awaited_once()


class TestSessionDescriptionDave(unittest.IsolatedAsyncioTestCase):
    async def test_new_voice_session_gets_fresh_dave_manager(self) -> None:
        """ The stored external sender belongs to the previous voice session. """
        connection = object.__new__(VoiceConnection)
        connection._connected_event = asyncio.Event()
        connection.mode = None
        connection.voice_client = Mock(is_playing=Mock(return_value=False), is_paused=Mock(return_value=False))
        stale = Mock()
        connection.dave_session = stale

        async def reinit() -> None:
            self.assertIsNone(connection.dave_session)
            connection.dave_session = Mock()

        connection.reinit_dave_session = reinit  # type: ignore[method-assign]

        await connection.on_session_description({
            "secret_key": [0] * 32,
            "mode": "aead_aes256_gcm_rtpsize",
            "dave_protocol_version": 1,
        })

        self.assertIsNot(connection.dave_session, stale)
        self.assertTrue(connection._connected_event.is_set())
