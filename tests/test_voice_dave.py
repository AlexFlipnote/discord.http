import asyncio
import unittest

from unittest.mock import AsyncMock, patch

from discord_http.voice.dave import DaveManager

class _FakeSocket:
    """Records the transition ids acknowledged with TRANSITION_READY."""

    def __init__(self) -> None:
        self.ready_ids: list[int] = []

    async def send_transition_ready(self, transition_id: int) -> None:
        self.ready_ids.append(transition_id)


class _FakeSession:
    """A stand-in for davey.DaveSession that reports itself ready."""

    def __init__(self) -> None:
        self.ready = True
        self.passthrough: bool | None = None

    def set_passthrough_mode(self, passthrough_mode: bool) -> None:
        self.passthrough = passthrough_mode


class _FakeConnection:
    """The minimal connection surface DaveManager's transition handling touches."""

    def __init__(self, channel_id: int | None = 1234) -> None:
        self.socket = _FakeSocket()
        self.channel_id = channel_id
        self.user_id = 5678
        self.dave_protocol_version = 0


def _manager(channel_id: int | None = 1234) -> tuple[DaveManager, _FakeSocket]:
    connection = _FakeConnection(channel_id)
    manager = DaveManager(connection)  # type: ignore[arg-type]
    return manager, connection.socket


class TestDaveTransitions(unittest.TestCase):
    def test_prepare_records_pending_and_acks(self) -> None:
        manager, socket = _manager()

        asyncio.run(manager._handle_prepare_transition({"transition_id": 5, "protocol_version": 1}))

        self.assertEqual(manager._pending_transitions, {5: 1})
        self.assertEqual(socket.ready_ids, [5])

    def test_execute_applies_pending_version_and_pops(self) -> None:
        manager, _ = _manager()

        asyncio.run(manager._handle_prepare_transition({"transition_id": 5, "protocol_version": 1}))
        asyncio.run(manager._handle_execute_transition({"transition_id": 5}))

        self.assertEqual(manager._version, 1)
        self.assertEqual(manager._pending_transitions, {})

    def test_execute_unknown_transition_is_ignored(self) -> None:
        manager, _ = _manager()

        asyncio.run(manager._handle_execute_transition({"transition_id": 9}))

        self.assertEqual(manager._version, 0)
        self.assertEqual(manager._pending_transitions, {})

    def test_overlapping_transitions_do_not_clobber(self) -> None:
        # Two transitions pending at once (e.g. member churn) must each keep
        # their own target version until their EXECUTE_TRANSITION arrives.
        manager, socket = _manager()

        asyncio.run(manager._handle_prepare_transition({"transition_id": 1, "protocol_version": 1}))
        asyncio.run(manager._handle_prepare_transition({"transition_id": 2, "protocol_version": 0}))
        self.assertEqual(manager._pending_transitions, {1: 1, 2: 0})
        self.assertEqual(socket.ready_ids, [1, 2])

        asyncio.run(manager._handle_execute_transition({"transition_id": 1}))
        self.assertEqual(manager._version, 1)
        self.assertEqual(manager._pending_transitions, {2: 0})

        asyncio.run(manager._handle_execute_transition({"transition_id": 2}))
        self.assertEqual(manager._version, 0)
        self.assertEqual(manager._pending_transitions, {})

    def test_transition_id_zero_executes_immediately_without_ack(self) -> None:
        manager, socket = _manager()

        asyncio.run(manager._handle_prepare_transition({"transition_id": 0, "protocol_version": 0}))

        self.assertEqual(manager._pending_transitions, {})
        self.assertEqual(socket.ready_ids, [])

    def test_downgrade_to_version_zero_disables_encryption(self) -> None:
        # A live, ready session is not enough: after transitioning down to
        # protocol version 0 nothing is encrypted any more, and can_encrypt()
        # must say so or the receiver drops plain Opus packets.
        manager, _ = _manager()
        manager._session = _FakeSession()  # type: ignore[assignment]
        manager._version = 1
        self.assertTrue(manager.can_encrypt())

        asyncio.run(manager._handle_prepare_transition({"transition_id": 3, "protocol_version": 0}))
        asyncio.run(manager._handle_execute_transition({"transition_id": 3}))

        self.assertEqual(manager._version, 0)
        self.assertTrue(manager.ready)
        self.assertFalse(manager.can_encrypt())

    def test_prepare_epoch_one_reinitializes_new_group(self) -> None:
        """ Reinitialize DAVE when epoch one announces a new MLS group. """
        manager, _ = _manager()

        with patch.object(DaveManager, "reinit", new_callable=AsyncMock) as reinit:
            asyncio.run(manager._handle_prepare_epoch({"epoch": 1, "protocol_version": 1}))

        self.assertEqual(manager._connection.dave_protocol_version, 1)
        reinit.assert_awaited_once_with(1)

    def test_later_prepare_epoch_keeps_current_group(self) -> None:
        """ Keep the current DAVE session for later epochs in the same MLS group. """
        manager, _ = _manager()

        with patch.object(DaveManager, "reinit", new_callable=AsyncMock) as reinit:
            asyncio.run(manager._handle_prepare_epoch({"epoch": 2, "protocol_version": 1}))

        self.assertEqual(manager._connection.dave_protocol_version, 0)
        reinit.assert_not_awaited()

    def test_reinit_without_channel_resets_version(self) -> None:
        # No channel means no session; the version must not stay non-zero, or
        # encrypt_opus would pass plaintext into a channel Discord treats as E2EE.
        manager, _ = _manager(channel_id=None)

        asyncio.run(manager.reinit(1))

        self.assertIsNone(manager._session)
        self.assertEqual(manager._version, 0)
        self.assertFalse(manager.can_encrypt())

    def test_reinit_clears_pending_transitions(self) -> None:
        manager, _ = _manager()

        asyncio.run(manager._handle_prepare_transition({"transition_id": 5, "protocol_version": 1}))
        asyncio.run(manager.reinit(0))

        self.assertEqual(manager._pending_transitions, {})
        self.assertIsNone(manager._session)


if __name__ == "__main__":
    unittest.main()


class _RecordingSession:
    """ A stand-in for davey.DaveSession recording the external senders it was given. """

    def __init__(self, *args) -> None:
        self.external_senders: list[bytes] = []
        self.ready = False

    def set_external_sender(self, payload: bytes) -> None:
        self.external_senders.append(payload)

    def get_serialized_key_package(self) -> bytes:
        return b"key-package"

    def process_welcome(self, welcome: bytes) -> None:
        raise ValueError("Failed to process welcome: NoExternalSender")


class _FakeDavey:
    DaveSession = _RecordingSession


def _davey_manager() -> DaveManager:
    manager, socket = _manager()
    socket.send_binary = AsyncMock()  # type: ignore[attr-defined]
    return manager


class TestDaveExternalSender(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        for patcher in (patch("discord_http.voice.dave.davey", _FakeDavey), patch("discord_http.voice.dave.has_dave", True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_external_sender_survives_reinit(self) -> None:
        """ Op 25 is sent once per voice session, every new MLS group needs it again. """
        manager = _davey_manager()
        await manager.reinit(1)
        first = manager._session
        manager._handle_external_sender(b"sender")

        await manager.reinit(1)

        self.assertIsNot(manager._session, first)
        self.assertEqual(first.external_senders, [b"sender"])
        self.assertEqual(manager._session.external_senders, [b"sender"])

    async def test_external_sender_before_session_is_applied_on_reinit(self) -> None:
        manager = _davey_manager()
        manager._handle_external_sender(b"sender")

        await manager.reinit(1)

        self.assertEqual(manager._session.external_senders, [b"sender"])

    async def test_external_sender_failure_is_logged_not_raised(self) -> None:
        manager = _davey_manager()
        await manager.reinit(1)
        manager._session.set_external_sender = lambda _: (_ for _ in ()).throw(ValueError("bad"))

        with self.assertLogs("discord_http.voice.dave", "WARNING"):
            manager._handle_external_sender(b"sender")

    async def test_mls_failure_is_a_warning(self) -> None:
        """ A failed welcome ends in a 4006 and the bot leaving, so it must be visible. """
        manager = _davey_manager()
        await manager.reinit(1)

        with self.assertLogs("discord_http.voice.dave", "WARNING") as logs:
            await manager._handle_welcome(b"\x00\x01welcome")

        self.assertIn("Failed to process MLS welcome", logs.output[0])
