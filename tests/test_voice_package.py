import asyncio
import unittest

from types import SimpleNamespace
from unittest import mock

from discord_http.channel import PartialChannel
from discord_http.enums import ChannelType
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


class TestRtcpFilter(unittest.TestCase):
    def _protocol(self):
        from discord_http.voice.gateway_udp import VoiceUDPProtocol

        unpack = mock.Mock()
        proto = VoiceUDPProtocol(SimpleNamespace(voice_client=SimpleNamespace(_receiver=SimpleNamespace(unpack=unpack))))
        return proto, unpack

    def test_rtcp_feedback_is_dropped(self) -> None:
        """ 205 (RTPFB/NACK) and 206 (PSFB/PLI) were reaching the RTP decrypt as InvalidTag. """
        proto, unpack = self._protocol()
        for packet_type in (192, 200, 204, 205, 206, 223):
            proto.datagram_received(bytes([0x81, packet_type]) + b"\x00" * 30, ("", 0))
        unpack.assert_not_called()

    def test_opus_rtp_is_passed_on(self) -> None:
        proto, unpack = self._protocol()
        # Payload type 120 (0x78), with and without the marker bit
        for second in (0x78, 0xF8):
            proto.datagram_received(bytes([0x80, second]) + b"\x00" * 30, ("", 0))
        self.assertEqual(unpack.call_count, 2)


class TestDaveTransitionDropLogging(unittest.TestCase):
    def _receiver(self, error: Exception) -> VoiceReceiver:
        connection = mock.Mock(
            encryptor=mock.Mock(decrypt=mock.Mock(return_value=b"opus")),
            can_encrypt=mock.Mock(return_value=True),
            dave_decrypt_opus=mock.Mock(side_effect=error),
        )
        rx = VoiceReceiver(SimpleNamespace(connection=connection))
        rx.start(mock.Mock(wants_opus=mock.Mock(return_value=True)))
        rx.add_ssrc(5, 100)
        return rx

    def _packet(self) -> bytes:
        return bytes([0x80, 0x78]) + b"\x00\x01" + b"\x00" * 4 + (5).to_bytes(4, "big") + b"payload"

    def test_unencrypted_transition_frame_is_debug(self) -> None:
        rx = self._receiver(ValueError("Failed to decrypt: DecryptionFailed(UnencryptedWhenPassthroughDisabled)"))
        with self.assertLogs("discord_http.voice.receiver", "DEBUG") as logs:
            rx.unpack(self._packet())
        self.assertTrue(all(r.levelname == "DEBUG" for r in logs.records))
        rx.sink.write.assert_not_called()

    def test_other_dave_failures_stay_errors(self) -> None:
        rx = self._receiver(ValueError("Failed to decrypt: DecryptionFailed(InvalidTag)"))
        with self.assertLogs("discord_http.voice.receiver", "ERROR"):
            rx.unpack(self._packet())


class TestRtpPadding(unittest.TestCase):
    def _receiver(self, decrypted: bytes) -> VoiceReceiver:
        connection = mock.Mock(
            encryptor=mock.Mock(decrypt=mock.Mock(return_value=decrypted)),
            can_encrypt=mock.Mock(return_value=True),
            dave_decrypt_opus=mock.Mock(side_effect=lambda user, opus: opus),
        )
        rx = VoiceReceiver(SimpleNamespace(connection=connection))
        rx.start(mock.Mock(wants_opus=mock.Mock(return_value=True)))
        rx.add_ssrc(5, 100)
        return rx

    def _packet(self, padding: bool) -> bytes:
        return bytes([0xA0 if padding else 0x80, 0x78]) + b"\x00\x01" + b"\x00" * 4 + (5).to_bytes(4, "big") + b"enc"

    def test_padding_only_probe_is_dropped_before_dave(self) -> None:
        """ Seen live: 255 bytes of 0xFF with the P bit set, sent when a client starts a new media session. """
        rx = self._receiver(b"\xff" * 255)
        rx.unpack(self._packet(padding=True))
        rx.voice_client.connection.dave_decrypt_opus.assert_not_called()
        rx.sink.write.assert_not_called()

    def test_padding_is_stripped_from_audio(self) -> None:
        rx = self._receiver(b"opus" + b"\x00\x00\x03")
        rx.unpack(self._packet(padding=True))
        rx.voice_client.connection.dave_decrypt_opus.assert_called_once_with(100, b"opus")

    def test_no_padding_bit_leaves_payload(self) -> None:
        rx = self._receiver(b"opus\x03")
        rx.unpack(self._packet(padding=False))
        rx.voice_client.connection.dave_decrypt_opus.assert_called_once_with(100, b"opus\x03")


class TestSpeakingAfterNewSession(unittest.IsolatedAsyncioTestCase):
    def _connection(self, playing: bool) -> VoiceConnection:
        conn = VoiceConnection.__new__(VoiceConnection)
        conn.mode = None
        conn.dave_session = None
        conn._connected_event = asyncio.Event()
        conn.voice_client = mock.Mock(
            is_playing=mock.Mock(return_value=playing),
            is_paused=mock.Mock(return_value=False),
            speak=mock.AsyncMock(),
        )
        return conn

    async def test_resends_speaking_while_playing(self) -> None:
        """ Seen live: after a reconnect the new SSRC was never announced and listeners dropped all audio. """
        conn = self._connection(playing=True)
        await conn.on_session_description({"secret_key": [0] * 32})
        conn.voice_client.speak.assert_awaited_once_with(True)

    async def test_no_speaking_without_player(self) -> None:
        conn = self._connection(playing=False)
        await conn.on_session_description({"secret_key": [0] * 32})
        conn.voice_client.speak.assert_not_awaited()


class TestDaveRequired(unittest.IsolatedAsyncioTestCase):
    def _connection(self, channel_type: ChannelType) -> VoiceConnection:
        conn = VoiceConnection.__new__(VoiceConnection)
        conn.voice_client = mock.Mock(channel=mock.Mock(type=channel_type))
        conn._connect = mock.AsyncMock()
        return conn

    async def test_connect_without_davey_fails_fast(self) -> None:
        """ Seen live: without davey Discord closes with 4017 and connect() only timed out after 30s. """
        conn = self._connection(ChannelType.guild_voice)
        with mock.patch.object(connection_mod, "has_dave", False), self.assertRaises(RuntimeError):
            await conn.connect()
        conn._connect.assert_not_awaited()

    async def test_stage_channel_does_not_need_davey(self) -> None:
        conn = self._connection(ChannelType.guild_stage_voice)
        with mock.patch.object(connection_mod, "has_dave", False):
            await conn.connect()
        conn._connect.assert_awaited_once()

    async def test_dave_required_close_tears_down_without_reconnect(self) -> None:
        conn = VoiceConnection.__new__(VoiceConnection)
        conn.guild_id = 1
        conn._move_target_channel_id = None
        conn._teardown_and_remove = mock.AsyncMock()
        conn._soft_reconnect = mock.AsyncMock()
        conn._full_reconnect = mock.AsyncMock()
        await conn._handle_close(4017)
        conn._teardown_and_remove.assert_awaited_once()
        conn._soft_reconnect.assert_not_awaited()
        conn._full_reconnect.assert_not_awaited()
