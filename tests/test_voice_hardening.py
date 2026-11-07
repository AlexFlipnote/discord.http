import asyncio
import shutil
import unittest

from types import SimpleNamespace
from unittest import mock

from discord_http.errors import FFmpegError, VoiceConnectionClosed
from discord_http.utils import ExponentialBackoff
from discord_http.voice import connection as connection_mod
from discord_http.voice.connection import VoiceConnection
from discord_http.voice.dave import DaveManager
from discord_http.voice.player import AudioPlayer, AudioSource, FFmpegOpusAudio
from discord_http.voice.receiver import VoiceReceiver
from discord_http.voice.sinks import CallbackSink, VoiceData


class _Source(AudioSource):
    """ An endless Opus source that records whether it was cleaned up. """

    def __init__(self) -> None:
        self.cleaned = False

    async def read(self) -> bytes:
        return b"\xf8\xff\xfe"

    def is_opus(self) -> bool:
        return True

    def cleanup(self) -> None:
        self.cleaned = True


def _player_client() -> SimpleNamespace:
    vc = SimpleNamespace(
        loop=asyncio.get_running_loop(),
        guild_id=1,
        _player=None,
        speak=mock.AsyncMock(),
        send_audio_packet=mock.Mock(),
    )
    return vc


class TestPlayerStopBeforeStart(unittest.IsolatedAsyncioTestCase):
    async def test_after_runs_when_stopped_in_the_same_tick(self) -> None:
        """ Seen live: play() then stop() never called after, stalling queue bots. """
        source = _Source()
        calls: list[Exception | None] = []
        player = AudioPlayer(source, _player_client(), after=calls.append)  # type: ignore[arg-type]

        player.start()
        player.stop()
        await asyncio.sleep(0.05)

        self.assertEqual(calls, [None])
        self.assertTrue(source.cleaned)

    async def test_async_after_is_awaited(self) -> None:
        done = asyncio.Event()

        async def after(_error: Exception | None) -> None:
            done.set()

        player = AudioPlayer(_Source(), _player_client(), after=after)  # type: ignore[arg-type]
        player.start()
        await asyncio.sleep(0.05)
        player.stop()

        await asyncio.wait_for(done.wait(), 1)


class TestPlayerSetSource(unittest.IsolatedAsyncioTestCase):
    async def test_paused_player_stays_paused(self) -> None:
        old = _Source()
        player = AudioPlayer(old, _player_client())  # type: ignore[arg-type]
        player.start()
        await asyncio.sleep(0.05)
        player.pause()

        player.set_source(_Source())

        self.assertTrue(player.is_paused())
        self.assertTrue(old.cleaned)
        player.stop()
        await asyncio.sleep(0.01)


@unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg is not installed")
class TestFFmpegErrors(unittest.IsolatedAsyncioTestCase):
    async def test_missing_file_raises_instead_of_finishing_silently(self) -> None:
        source = FFmpegOpusAudio("this-file-does-not-exist.mp3")
        try:
            with self.assertRaises(FFmpegError):
                await source.read()
        finally:
            source.cleanup()
            await asyncio.sleep(0.1)


class _Socket:
    """ A voice socket stand-in, ``on_connect`` decides how the handshake goes. """

    instances: list["_Socket"] = []
    on_connect = None

    def __init__(self, connection: VoiceConnection) -> None:
        self.connection = connection
        self.closed = asyncio.Event()
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.seq_ack = -1
        self.resume: bool | None = None
        _Socket.instances.append(self)

    async def connect(self, *, resume: bool = False) -> None:
        self.resume = resume
        if _Socket.on_connect is not None:
            _Socket.on_connect(self)

    def _request_close(self) -> None:
        pass

    async def close(self) -> None:
        self.closed.set()

    def fail(self, code: int, reason: str = "") -> None:
        self.close_code = code
        self.close_reason = reason
        self.closed.set()


def _connection() -> VoiceConnection:
    conn = VoiceConnection.__new__(VoiceConnection)
    conn.guild_id = 1
    conn.socket = None
    conn.transport = None
    conn.udp = None
    conn.token = "token"
    conn.endpoint = "endpoint"
    conn.session_id = "session"
    conn.channel_id = 123
    conn._closing = False
    conn._reconnect = True
    conn._handshaking = False
    conn._reconnect_task = None
    conn._move_target_channel_id = None
    conn._move_server_update_received = False
    conn._socket_credentials = ("token", "endpoint")
    conn._self_mute = False
    conn._self_deaf = False
    conn._state_event = asyncio.Event()
    conn._server_event = asyncio.Event()
    conn._ready_event = asyncio.Event()
    conn._connected_event = asyncio.Event()
    conn._update_event = asyncio.Event()
    conn._state_event.set()
    conn._server_event.set()
    return conn


class _SocketTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _Socket.instances = []
        _Socket.on_connect = None
        patcher = mock.patch.object(connection_mod, "VoiceSocket", _Socket)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestHandshakeFailsFast(_SocketTest):
    async def test_close_during_connect_raises_its_code(self) -> None:
        """ Seen live: a 4006 during connect() waited the full 30s and raised a bare TimeoutError. """
        _Socket.on_connect = lambda s: s.fail(4017, "E2EE/DAVE protocol required")
        conn = _connection()

        with self.assertRaises(VoiceConnectionClosed) as ctx:
            await asyncio.wait_for(conn._wait_for_handshake(), 1)

        self.assertEqual(ctx.exception.code, 4017)
        self.assertIn("DAVE", str(ctx.exception))

    async def test_moved_while_connecting_retries_with_new_credentials(self) -> None:
        """ Join-to-create bots move the bot within a second of joining. """
        conn = _connection()

        def on_connect(socket: _Socket) -> None:
            if len(_Socket.instances) == 1:
                socket.fail(4022)
                conn.channel_id = 456
                conn.token = "new-token"
            else:
                conn._connected_event.set()

        _Socket.on_connect = on_connect

        await asyncio.wait_for(conn._wait_for_handshake(), 1)

        self.assertEqual(len(_Socket.instances), 2)
        self.assertIs(conn.socket, _Socket.instances[1])

    async def test_disconnect_while_opening_stops_the_connect(self) -> None:
        conn = _connection()

        def on_connect(_socket: _Socket) -> None:
            conn._closing = True

        _Socket.on_connect = on_connect

        with self.assertRaises(VoiceConnectionClosed):
            await asyncio.wait_for(conn._wait_for_handshake(), 1)

        self.assertTrue(_Socket.instances[0].closed.is_set())


class TestResume(_SocketTest):
    async def test_resume_acknowledges_the_old_sequence(self) -> None:
        conn = _connection()
        conn.socket = _Socket(conn)  # type: ignore[assignment]
        conn.socket.seq_ack = 41
        _Socket.on_connect = lambda _s: conn._connected_event.set()

        await conn._resume()

        new = _Socket.instances[-1]
        self.assertTrue(new.resume)
        self.assertEqual(new.seq_ack, 41)

    async def test_refused_resume_reconnects_instead_of_leaving(self) -> None:
        """ Seen live: a 4015 resume refused with 4006 made the bot leave voice. """
        conn = _connection()
        conn._soft_reconnect = mock.AsyncMock(return_value=True)  # type: ignore[method-assign]
        conn._teardown_and_remove = mock.AsyncMock()  # type: ignore[method-assign]
        _Socket.on_connect = lambda s: s.fail(4006)

        await asyncio.wait_for(conn._handle_close(4015), 1)

        conn._soft_reconnect.assert_awaited_once()
        conn._teardown_and_remove.assert_not_awaited()


class TestServerUpdates(unittest.IsolatedAsyncioTestCase):
    async def test_null_endpoint_waits_for_the_next_server(self) -> None:
        conn = _connection()
        conn._connected_event.set()
        conn._schedule_server_migration = mock.Mock()  # type: ignore[method-assign]

        conn.on_voice_server_update({"token": "new-token", "endpoint": None, "guild_id": "1"})

        self.assertIsNone(conn.endpoint)
        self.assertFalse(conn._server_event.is_set())
        conn._schedule_server_migration.assert_not_called()


class TestMoveTo(unittest.IsolatedAsyncioTestCase):
    async def test_same_channel_does_nothing(self) -> None:
        conn = _connection()
        shard = SimpleNamespace(change_voice_state=mock.AsyncMock())
        conn._get_shard = mock.Mock(return_value=shard)  # type: ignore[method-assign]

        await conn.move_to(SimpleNamespace(id=123))  # type: ignore[arg-type]

        shard.change_voice_state.assert_not_awaited()
        self.assertIsNone(conn._move_target_channel_id)

    async def test_refused_move_times_out_and_forgets_the_target(self) -> None:
        """ A leftover target would make a later 4022 look like part of a move. """
        conn = _connection()
        shard = SimpleNamespace(change_voice_state=mock.AsyncMock())
        conn._get_shard = mock.Mock(return_value=shard)  # type: ignore[method-assign]

        with self.assertRaises(TimeoutError):
            await conn.move_to(SimpleNamespace(id=456), timeout=0.05)  # type: ignore[arg-type]

        self.assertIsNone(conn._move_target_channel_id)


class TestReadyTransport(unittest.IsolatedAsyncioTestCase):
    async def test_second_ready_closes_the_first_udp_socket(self) -> None:
        conn = _connection()
        conn.voice_client = SimpleNamespace(_receiver=SimpleNamespace(reset=mock.Mock()))  # type: ignore[assignment]
        conn.connected_user_ids = set()
        old = mock.Mock()
        conn.transport = old
        udp = SimpleNamespace(discover_ip=mock.AsyncMock(return_value=("1.2.3.4", 5)))

        with mock.patch.object(connection_mod, "create_udp", mock.AsyncMock(return_value=(mock.Mock(), udp))):
            await conn.on_ready({"ssrc": 1, "ip": "1.1.1.1", "port": 1, "modes": ["aead_aes256_gcm_rtpsize"]})

        old.close.assert_called_once_with()
        self.assertIsNot(conn.transport, old)


class _DaveSocket:
    def __init__(self) -> None:
        self.invalid_ids: list[int] = []
        self.ready_ids: list[int] = []
        self.binary: list[int] = []

    async def send_invalid_commit_welcome(self, transition_id: int) -> None:
        self.invalid_ids.append(transition_id)

    async def send_transition_ready(self, transition_id: int) -> None:
        self.ready_ids.append(transition_id)

    async def send_binary(self, opcode: int, _payload: bytes) -> None:
        self.binary.append(opcode)


class _BrokenSession:
    ready = True
    can_encrypt = True
    protocol_version = 1

    def __init__(self) -> None:
        self.expected: list[int] | None = None
        self.recognized: list[int] | None = None
        self.prepared: list[tuple[int, int]] = []
        self.commit_result: bool | None = None

    def process_commit(self, _commit: bytes) -> bool:
        if self.commit_result is None:
            raise ValueError("bad commit")
        return self.commit_result

    def process_welcome(self, _welcome: bytes, recognized_user_ids: list[int] | None = None) -> None:
        self.recognized = recognized_user_ids

    def prepare_transition(self, transition_id: int, protocol_version: int) -> None:
        self.prepared.append((transition_id, protocol_version))

    def execute_transition(self, _transition_id: int) -> bool:
        return True

    def process_proposals(self, _optype, _proposals, expected_user_ids=None) -> None:
        self.expected = expected_user_ids

    def decrypt(self, _user_id, _media_type, _packet) -> bytes:
        raise ValueError("Failed to decrypt: DecryptionFailed(InvalidTag)")


def _dave() -> tuple[DaveManager, _DaveSocket, _BrokenSession]:
    socket = _DaveSocket()
    connection = SimpleNamespace(
        socket=socket,
        channel_id=1234,
        guild_id=1,
        user_id=5678,
        dave_protocol_version=1,
        connected_user_ids={42},
        _dave_lock=asyncio.Lock(),
    )
    manager = DaveManager(connection)  # type: ignore[arg-type]
    session = _BrokenSession()
    manager._session = session  # type: ignore[assignment]
    manager._version = 1
    return manager, socket, session


class TestDaveRecovery(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(DaveManager, "reinit", new_callable=mock.AsyncMock)
        self.reinit = patcher.start()
        self.addCleanup(patcher.stop)

    async def test_failed_commit_reports_its_transition_once(self) -> None:
        """ Op 31 was an empty binary frame without the transition id, and failures stacked reinits. """
        manager, socket, _ = _dave()

        await manager._handle_commit(b"\x00\x07commit")
        await manager._handle_commit(b"\x00\x07commit")

        self.assertEqual(socket.invalid_ids, [7])
        self.reinit.assert_awaited_once_with(1)

    async def test_applied_welcome_allows_the_next_recovery(self) -> None:
        manager, socket, _ = _dave()

        await manager._handle_commit(b"\x00\x07commit")
        await manager._handle_welcome(b"\x00\x08welcome")
        await manager._handle_commit(b"\x00\x09commit")

        self.assertEqual(socket.invalid_ids, [7, 9])

    async def test_proposals_only_accept_users_in_the_call(self) -> None:
        manager, _, session = _dave()

        with mock.patch("discord_http.voice.dave.davey") as davey:
            await manager._handle_proposals(b"\x00proposals")
            del davey

        self.assertEqual(sorted(session.expected or []), [42, 5678])

    async def test_persistent_decrypt_failures_recover(self) -> None:
        manager, socket, _ = _dave()
        manager._last_transition_id = 3

        with mock.patch("discord_http.voice.dave.davey"):
            for _ in range(40):
                with self.assertRaises(ValueError):
                    manager.decrypt_opus(42, b"frame")

        await asyncio.sleep(0.01)
        self.assertEqual(socket.invalid_ids, [3])

    async def test_welcome_prepares_its_transition_and_acks(self) -> None:
        """ davey 0.2 only installs keys once the transition is prepared. """
        manager, socket, session = _dave()

        await manager._handle_welcome(b"\x00\x08welcome")

        self.assertEqual(session.prepared, [(8, 1)])
        self.assertEqual(socket.ready_ids, [8])
        self.assertEqual(sorted(session.recognized or []), [42, 5678])

    async def test_ignored_commit_is_not_acknowledged(self) -> None:
        manager, socket, session = _dave()
        session.commit_result = False

        await manager._handle_commit(b"\x00\x07commit")

        self.assertEqual(session.prepared, [])
        self.assertEqual(socket.ready_ids, [])
        self.assertEqual(socket.invalid_ids, [])

    async def test_transition_zero_applies_without_ack(self) -> None:
        manager, socket, session = _dave()
        session.commit_result = True

        await manager._handle_commit(b"\x00\x00commit")

        self.assertEqual(session.prepared, [(0, 1)])
        self.assertEqual(socket.ready_ids, [])

    def test_undecryptable_frames_are_recognised(self) -> None:
        manager = DaveManager(SimpleNamespace())  # type: ignore[arg-type]
        manager._version = 1

        self.assertTrue(manager.is_undecryptable(b"ciphertext\xfa\xfa"))
        self.assertFalse(manager.is_undecryptable(b"plain opus"))


class TestReceiverDropsCiphertext(unittest.TestCase):
    def test_encrypted_frame_is_dropped_while_dave_is_not_ready(self) -> None:
        connection = mock.Mock(
            encryptor=mock.Mock(decrypt=mock.Mock(return_value=b"ciphertext\xfa\xfa")),
            can_encrypt=mock.Mock(return_value=False),
            is_undecryptable_dave_frame=mock.Mock(return_value=True),
        )
        rx = VoiceReceiver(SimpleNamespace(connection=connection))  # type: ignore[arg-type]
        sink = mock.Mock(wants_opus=mock.Mock(return_value=True))
        rx.start(sink)

        rx.unpack(bytes([0x80, 0x78]) + b"\x00\x01" + b"\x00" * 4 + (5).to_bytes(4, "big") + b"x")

        sink.write.assert_not_called()


class TestCallbackSink(unittest.IsolatedAsyncioTestCase):
    async def test_async_callback_is_awaited(self) -> None:
        done = asyncio.Event()

        async def callback(_user: int | None, _data: VoiceData) -> None:
            done.set()

        CallbackSink(callback).write(1, VoiceData(user=1, pcm=b"", opus=None, timestamp=0, ssrc=1))

        await asyncio.wait_for(done.wait(), 1)


class TestBackoff(unittest.TestCase):
    def test_many_delays_do_not_overflow(self) -> None:
        backoff = ExponentialBackoff(1.0, max_delay=5.0, jitter=False)
        for _ in range(2000):
            delay = backoff.delay()
        self.assertEqual(delay, 5.0)


if __name__ == "__main__":
    unittest.main()
