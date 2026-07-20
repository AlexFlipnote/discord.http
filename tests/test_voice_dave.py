import asyncio
import unittest

from discord_http.voice.dave import DaveManager


class _FakeSocket:
    """Records the transition ids acknowledged with TRANSITION_READY."""

    def __init__(self) -> None:
        self.ready_ids: list[int] = []

    async def send_transition_ready(self, transition_id: int) -> None:
        self.ready_ids.append(transition_id)


class _FakeConnection:
    """The minimal connection surface DaveManager's transition handling touches."""

    def __init__(self) -> None:
        self.socket = _FakeSocket()


def _manager() -> tuple[DaveManager, _FakeSocket]:
    connection = _FakeConnection()
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

    def test_reinit_clears_pending_transitions(self) -> None:
        manager, _ = _manager()

        asyncio.run(manager._handle_prepare_transition({"transition_id": 5, "protocol_version": 1}))
        asyncio.run(manager.reinit(0))

        self.assertEqual(manager._pending_transitions, {})
        self.assertIsNone(manager._session)


if __name__ == "__main__":
    unittest.main()
