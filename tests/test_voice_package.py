import asyncio
import unittest

from types import SimpleNamespace
from unittest import mock

from discord_http.channel import PartialChannel
from discord_http.voice import connection as connection_mod, dave as dave_mod, receiver as receiver_mod
from discord_http.voice.client import VoiceClient
from discord_http.voice.connection import VoiceConnection
from discord_http.voice.dave import DaveManager
from discord_http.voice.player import AudioPlayer
from discord_http.voice.receiver import VoiceReceiver


class FakeDecoder:
    def decode(self, data: bytes | None) -> bytes:
        return b"C" if data is None else data


class TestReceiverSequence(unittest.TestCase):
    def setUp(self) -> None:
        self.rx = VoiceReceiver(SimpleNamespace())
        self.rx._get_decoder = lambda ssrc: FakeDecoder()
        patcher = mock.patch.object(receiver_mod.opus, "is_loaded", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_in_order_has_no_concealment(self) -> None:
        self.assertEqual(self.rx._decode_pcm(1, 10, b"a"), b"a")
        self.assertEqual(self.rx._decode_pcm(1, 11, b"b"), b"b")

    def test_gap_keeps_concealment_frame(self) -> None:
        self.rx._decode_pcm(1, 10, b"a")
        self.assertEqual(self.rx._decode_pcm(1, 12, b"c"), b"Cc")

    def test_late_packet_is_dropped_without_rewinding(self) -> None:
        self.rx._decode_pcm(1, 10, b"a")
        self.rx._decode_pcm(1, 12, b"c")
        self.assertIsNone(self.rx._decode_pcm(1, 11, b"b"))
        self.assertIsNone(self.rx._decode_pcm(1, 12, b"c"))
        # Next in-order packet is not treated as a gap
        self.assertEqual(self.rx._decode_pcm(1, 13, b"d"), b"d")

    def test_sequence_wraparound(self) -> None:
        self.rx._decode_pcm(1, 0xFFFF, b"a")
        self.assertEqual(self.rx._decode_pcm(1, 0, b"b"), b"b")


class TestDaveMissingDavey(unittest.IsolatedAsyncioTestCase):
    async def test_reinit_resets_version_before_raising(self) -> None:
        manager = DaveManager(SimpleNamespace(channel_id=1, user_id=2))
        with mock.patch.object(dave_mod, "has_dave", False), self.assertRaises(RuntimeError):
            await manager.reinit(1)
        self.assertEqual(manager._version, 0)
        self.assertIsNone(manager._session)


class FakeSocket:
    instances: list["FakeSocket"] = []

    def __init__(self, connection: VoiceConnection) -> None:
        self.connection = connection
        self.closed = False
        FakeSocket.instances.append(self)

    async def connect(self) -> None:
        pass

    def _request_close(self) -> None:
        pass

    async def close(self) -> None:
        self.closed = True


class TestHandshakeSocketLeak(unittest.IsolatedAsyncioTestCase):
    async def test_retry_closes_previous_socket(self) -> None:
        conn = VoiceConnection.__new__(VoiceConnection)
        conn.socket = None
        conn._state_event = asyncio.Event()
        conn._server_event = asyncio.Event()
        conn._connected_event = asyncio.Event()
        conn._state_event.set()
        conn._server_event.set()
        FakeSocket.instances = []

        with mock.patch.object(connection_mod, "VoiceSocket", FakeSocket):
            # First attempt times out waiting for the connected event
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(conn._wait_for_handshake(), 0.01)

            conn._connected_event.set()
            await conn._wait_for_handshake()

        first, second = FakeSocket.instances
        self.assertTrue(first.closed)
        self.assertIs(conn.socket, second)


class TestPlayerCleanupOnCancel(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_during_speak_still_cleans_up(self) -> None:
        source = mock.Mock()
        after = mock.Mock()
        speaking = asyncio.Event()

        async def speak(_: bool) -> None:
            speaking.set()
            await asyncio.sleep(10)

        vc = SimpleNamespace(loop=asyncio.get_running_loop(), _player=None, speak=speak, send_audio_packet=mock.Mock())
        player = AudioPlayer(source, vc, after=after)

        task = asyncio.create_task(player._cleanup())
        await speaking.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        source.cleanup.assert_called_once()
        after.assert_called_once_with(None)


class TestFailedConnectLeavesChannel(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_disconnects_and_unregisters(self) -> None:
        vc = mock.Mock(connect=mock.AsyncMock(side_effect=TimeoutError), disconnect=mock.AsyncMock())
        bot = mock.Mock(gateway=object(), get_voice_client=mock.Mock(return_value=None))
        channel = PartialChannel(state=SimpleNamespace(bot=bot), id=2, guild_id=1)  # type: ignore[arg-type]

        with mock.patch("discord_http.voice.client.VoiceClient", return_value=vc), self.assertRaises(TimeoutError):
            await channel.connect(timeout=0.1)

        vc.disconnect.assert_awaited_once_with(force=True)
        bot._remove_voice_client.assert_called_once_with(1)


class TestPlayWhileDisconnected(unittest.TestCase):
    def test_play_raises(self) -> None:
        vc = VoiceClient.__new__(VoiceClient)
        vc.connection = mock.Mock(is_connected=mock.Mock(return_value=False))
        after = mock.Mock()

        with self.assertRaises(RuntimeError):
            vc.play(b"", after=after)

        after.assert_not_called()


class TestTopLevelExports(unittest.TestCase):
    def test_voice_helpers_stay_under_voice(self) -> None:
        import discord_http

        self.assertTrue(hasattr(discord_http, "VoiceClient"))
        for name in ("is_loaded", "load_opus", "has_dave", "SAMPLE_RATE", "opus"):
            self.assertFalse(hasattr(discord_http, name), name)


class TestMoveWhileDisconnected(unittest.IsolatedAsyncioTestCase):
    async def test_move_to_raises_without_sending_op4(self) -> None:
        vc = VoiceClient.__new__(VoiceClient)
        vc.connection = mock.Mock(is_connected=mock.Mock(return_value=False), move_to=mock.AsyncMock())

        with self.assertRaises(RuntimeError):
            await vc.move_to(123)

        vc.connection.move_to.assert_not_awaited()
