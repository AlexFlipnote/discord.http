import asyncio
import logging

from typing import TYPE_CHECKING

try:
    import davey
    has_dave = True
except ImportError:
    davey = None
    has_dave = False

if TYPE_CHECKING:
    # ``davey`` is an optional runtime dependency, but it is always present in
    # the type-check environments (it is part of ``--all-extras``), so its own
    # type stubs are the authority on the session API.
    from davey import DaveSession

    from .connection import VoiceConnection

from .enums import VoiceOpType

__all__ = (
    "DaveManager",
    "has_dave",
    "max_protocol_version",
)

_log = logging.getLogger(__name__)

# Every DAVE-encrypted frame ends with this marker
_DAVE_MAGIC_MARKER = b"\xfa\xfa"

# How long decryptors keep accepting plaintext after a downgrade is announced, in seconds
_DOWNGRADE_PASSTHROUGH_EXPIRY = 24

# Consecutive frames from one user that may fail to decrypt before we assume
# our MLS state is out of sync and ask Discord to re-add us to the group
_DECRYPT_FAILURE_TOLERANCE = 36


def max_protocol_version() -> int:
    """ The maximum DAVE protocol version this installation can negotiate (``0`` if davey is absent). """
    if has_dave and davey is not None:
        return int(davey.DAVE_PROTOCOL_VERSION)
    return 0


class DaveManager:
    """ Manages DAVE (E2EE) for a voice connection, degrading to a no-op when davey is absent. """

    __slots__ = (
        "_connection",
        "_decrypt_failures",
        "_external_sender",
        "_last_transition_id",
        "_pending_transitions",
        "_recovery_task",
        "_reinitializing",
        "_session",
        "_version",
    )

    def __init__(self, connection: "VoiceConnection"):
        self._connection: "VoiceConnection" = connection
        self._session: "DaveSession | None" = None
        self._version: int = 0
        # MLS_EXTERNAL_SENDER (25) is sent once per voice session, but every new
        # MLS group (reinit) needs it, so keep it to re-apply
        self._external_sender: bytes | None = None
        # transition_id -> protocol version. A dict rather than a single slot so
        # overlapping transitions (e.g. during member churn) cannot clobber each
        # other before their EXECUTE_TRANSITION arrives.
        self._pending_transitions: dict[int, int] = {}
        # Set while we wait to be re-added after reporting a broken commit or
        # welcome, so further failures in the same transition don't stack
        # another reinit and key package on top
        self._reinitializing: bool = False
        self._last_transition_id: int | None = None
        # user_id -> consecutive decrypt failures, only users currently failing
        self._decrypt_failures: dict[int, int] = {}
        self._recovery_task: asyncio.Task | None = None

    @property
    def ready(self) -> bool:
        """ Whether the underlying MLS session has completed its handshake. """
        return self._session is not None and bool(self._session.ready)

    @property
    def voice_privacy_code(self) -> str | None:
        """ The privacy code users can compare out-of-band to verify the E2EE session, if any. """
        if self._session is None:
            return None
        code = self._session.voice_privacy_code
        return str(code) if code is not None else None

    def can_encrypt(self) -> bool:
        """ Whether end-to-end encryption is currently active and usable. """
        return self._version > 0 and self._session is not None and self.ready

    def is_undecryptable(self, opus: bytes) -> bool:
        """
        Whether ``opus`` is end-to-end encrypted but our session can't decrypt it yet.

        Parameters
        ----------
        opus
            The received Opus payload.
        """
        return self._version > 0 and not self.ready and opus.endswith(_DAVE_MAGIC_MARKER)

    def remove_user(self, user_id: int) -> None:
        """
        Forget per-user state for a user that left the call.

        Parameters
        ----------
        user_id
            The user that left.
        """
        self._decrypt_failures.pop(user_id, None)

    async def reinit(self, version: int) -> None:
        """
        Create or reinitialise the MLS session for a given protocol version.

        When ``version`` is greater than ``0`` but ``davey`` is not installed, a clear,
        actionable :class:`RuntimeError` is raised telling the user how to install the
        optional dependency. When a session is created, its serialized MLS key package is
        sent to the voice gateway.

        Parameters
        ----------
        version
            The negotiated DAVE protocol version. ``0`` disables end-to-end encryption.

        Raises
        ------
        RuntimeError
            If a non-zero DAVE version is requested but ``davey`` is not installed.
        """
        self._version = version
        # Any pending transitions belong to the previous session; drop them.
        self._pending_transitions.clear()
        self._decrypt_failures.clear()

        if version <= 0:
            self._session = None
            return

        # Checked before davey: with no channel there is nothing to encrypt for,
        # whether or not the optional package is installed.
        channel_id = self._connection.channel_id
        if channel_id is None:
            self._session = None
            self._version = 0
            return

        if not has_dave or davey is None:
            # Same reset as the failed-session branch below
            self._session = None
            self._version = 0
            raise RuntimeError(
                "Discord negotiated DAVE end-to-end encryption "
                f"(protocol version {version}), but the optional 'davey' package is not "
                'installed. Install it with: pip install "discord.http[voice]"'
            )

        try:
            self._session = davey.DaveSession(
                version,
                self._connection.user_id,
                channel_id,
            )
        except Exception as exc:
            # Reset the version too: leaving it non-zero would make can_encrypt()
            # depend solely on a session that does not exist, and the encrypt
            # helpers would silently pass plaintext into a channel Discord
            # believes is end-to-end encrypted.
            _log.warning(f"Failed to initialise DAVE session: {exc}")
            self._session = None
            self._version = 0
            return

        if self._external_sender is not None:
            self._apply_external_sender()

        await self._send_key_package()

    async def _send_key_package(self) -> None:
        """ Serialize and send our MLS key package to the voice gateway. """
        if self._session is None:
            return

        socket = self._connection.socket
        if socket is None:
            return

        key_package = self._session.get_serialized_key_package()
        await socket.send_binary(int(VoiceOpType.dave_mls_key_package), key_package)

    def set_passthrough_mode(self, enabled: bool, expiry: int | None = None) -> None:
        """
        Toggle passthrough mode on the MLS session.

        While in passthrough mode the session does not transform media, allowing audio to
        flow during transitions where some participants are not yet on the new epoch.

        Parameters
        ----------
        enabled
            ``True`` to pass media through unchanged, ``False`` to resume encryption.
        expiry
            How long, in seconds, plaintext keeps being accepted after the change.
            ``None`` uses davey's default.
        """
        if self._session is None:
            return

        self._session.set_passthrough_mode(enabled, expiry)

    def encrypt_opus(self, opus: bytes) -> bytes:
        """
        End-to-end encrypt an outbound Opus frame.

        Parameters
        ----------
        opus
            The plaintext Opus frame.

        Returns
        -------
            The encrypted frame, or the input unchanged when E2EE is not active.
        """
        if not self.can_encrypt() or self._session is None:
            return opus
        return bytes(self._session.encrypt_opus(opus))

    def decrypt_opus(self, user_id: int, opus: bytes) -> bytes:
        """
        End-to-end decrypt an inbound Opus frame from a given user.

        Parameters
        ----------
        user_id
            The user the frame originated from.
        opus
            The received Opus frame.

        Returns
        -------
            The decrypted frame, or the input unchanged when E2EE is not active.
        """
        if not self.can_encrypt() or self._session is None or davey is None:
            return opus

        try:
            decrypted = bytes(self._session.decrypt(user_id, davey.MediaType.audio, opus))
        except Exception as exc:
            # Plaintext from a member still joining is expected, not a desync
            if "UnencryptedWhenPassthroughDisabled" not in str(exc):
                failures = self._decrypt_failures.get(user_id, 0) + 1
                self._decrypt_failures[user_id] = failures
                if failures > _DECRYPT_FAILURE_TOLERANCE:
                    self._schedule_decrypt_recovery()
            raise

        self._decrypt_failures.pop(user_id, None)
        return decrypted

    def _schedule_decrypt_recovery(self) -> None:
        """ Ask to be re-added to the MLS group after persistent decrypt failures. """
        if self._reinitializing or self._last_transition_id is None:
            return
        if self._recovery_task is not None and not self._recovery_task.done():
            return

        transition_id = self._last_transition_id
        _log.warning(
            f"DAVE decryption keeps failing in guild {self._connection.guild_id}; "
            "asking Discord to re-add us to the group"
        )
        self._decrypt_failures.clear()
        self._recovery_task = asyncio.create_task(
            self._locked_recover(transition_id),
            name=f"discord.http/voice/dave-{self._connection.guild_id}/recover"
        )

    async def _locked_recover(self, transition_id: int) -> None:
        """ Run :meth:`_recover_from_invalid_commit` outside a frame handler, holding the DAVE lock. """
        try:
            async with self._connection._dave_lock:
                await self._recover_from_invalid_commit(transition_id)
        except Exception:
            _log.exception("Failed to recover the DAVE session")

    async def handle_binary(self, opcode: int, payload: bytes) -> None:
        """
        Dispatch a binary DAVE/MLS operation (opcodes 21-31) received from the gateway.

        Parameters
        ----------
        opcode
            The voice opcode, expected to be one of the DAVE ops 21-31.
        payload
            The raw binary payload following the opcode.
        """
        match opcode:
            case VoiceOpType.dave_mls_external_sender:
                self._handle_external_sender(payload)
            case VoiceOpType.dave_mls_proposals:
                await self._handle_proposals(payload)
            case VoiceOpType.dave_mls_announce_commit_transition:
                await self._handle_commit(payload)
            case VoiceOpType.dave_mls_welcome:
                await self._handle_welcome(payload)
            case _:
                _log.debug(f"Unhandled DAVE binary opcode {opcode}")

    async def handle_json(self, opcode: int, data: dict) -> None:
        """
        Dispatch a JSON DAVE control op (21, 22, 24) received from the gateway.

        Unlike the MLS data ops (25-31), the transition/epoch control ops arrive as
        regular JSON text frames rather than binary frames, so they are routed here
        with the decoded ``d`` payload instead of raw bytes.

        Parameters
        ----------
        opcode
            The voice opcode, expected to be one of 21, 22 or 24.
        data
            The decoded JSON ``d`` payload of the frame.
        """
        match opcode:
            case VoiceOpType.dave_prepare_transition:
                await self._handle_prepare_transition(data)
            case VoiceOpType.dave_execute_transition:
                await self._handle_execute_transition(data)
            case VoiceOpType.dave_prepare_epoch:
                await self._handle_prepare_epoch(data)
            case _:
                _log.debug(f"Unhandled DAVE JSON opcode {opcode}")

    async def _handle_prepare_transition(self, data: dict) -> None:
        """ Handle PREPARE_TRANSITION (21): record the pending transition and acknowledge. """
        transition_id = int(data.get("transition_id", 0) or 0)
        version = int(data.get("protocol_version", 0) or 0)
        self._pending_transitions[transition_id] = version

        if transition_id == 0:
            await self._execute_transition(transition_id, version)
            return

        if version == 0:
            # Members that already downgraded send plaintext before our
            # EXECUTE_TRANSITION arrives, accept it instead of dropping it
            self.set_passthrough_mode(True, _DOWNGRADE_PASSTHROUGH_EXPIRY)

        socket = self._connection.socket
        if socket is not None:
            await socket.send_transition_ready(transition_id)

    async def _handle_execute_transition(self, data: dict) -> None:
        """ Handle EXECUTE_TRANSITION (22): apply the pending version and passthrough state. """
        transition_id = int(data.get("transition_id", 0) or 0)

        version = self._pending_transitions.get(transition_id)
        if version is not None:
            await self._execute_transition(transition_id, version)
            return

        _log.debug(f"Received EXECUTE_TRANSITION for unknown transition {transition_id}")

    async def _execute_transition(self, transition_id: int, version: int) -> None:
        """ Apply a transition: switch protocol version and update passthrough mode. """
        self._version = version
        self._connection.dave_protocol_version = version
        self.set_passthrough_mode(version == 0)
        self._pending_transitions.pop(transition_id, None)
        if transition_id != 0:
            self._last_transition_id = transition_id
        _log.debug(f"Executed DAVE transition {transition_id} to version {version}")

    async def _handle_prepare_epoch(self, data: dict) -> None:
        """ Handle PREPARE_EPOCH (24), creating a session only for a new MLS group. """
        # Epoch 1 is the server's explicit signal that this is a new MLS group.
        # Later epochs are normal membership transitions within the same group and
        # must not discard the current session or send a replacement key package.
        if int(data.get("epoch", 0) or 0) != 1:
            return

        version = int(data.get("protocol_version", 0) or 0)
        self._connection.dave_protocol_version = version
        # A brand new group starts clean, whatever recovery was in progress
        self._reinitializing = False
        await self.reinit(version)

    def _handle_external_sender(self, payload: bytes) -> None:
        """ Handle MLS_EXTERNAL_SENDER (25): store and register the gateway's external sender. """
        self._external_sender = bytes(payload)
        if self._session is not None:
            self._apply_external_sender()

    def _apply_external_sender(self) -> None:
        """ Register the stored external sender on the current MLS session. """
        if self._session is None or self._external_sender is None:
            return

        try:
            self._session.set_external_sender(self._external_sender)
        except Exception as exc:
            _log.warning(f"Failed to set DAVE external sender: {exc}")

    async def _handle_proposals(self, payload: bytes) -> None:
        """
        Handle MLS_PROPOSALS (27): process proposals and forward any commit/welcome.

        The payload is ``operation_type(1B) + proposals``: the first byte selects
        append (``0``) vs revoke, and the remainder is the serialized proposals.
        """
        if self._session is None or davey is None:
            return

        if len(payload) < 1:
            return

        # Payload is ``operation_type(1B) + proposals``: first byte selects append (0) vs revoke.
        optype = payload[0]
        proposals = payload[1:]
        operation_type = (
            davey.ProposalsOperationType.append
            if optype == 0
            else davey.ProposalsOperationType.revoke
        )

        # Only accept proposals adding users Discord told us are in the call,
        # that is what stops the voice server quietly adding someone to the group
        expected_user_ids = [*self._connection.connected_user_ids, self._connection.user_id]

        try:
            result = self._session.process_proposals(operation_type, proposals, expected_user_ids=expected_user_ids)
        except Exception as exc:
            # No transition to report yet, the commit that follows will fail
            # too and recover with its transition id
            _log.warning(f"Failed to process MLS proposals: {exc}")
            return

        commit_welcome = self._extract_commit_welcome(result)
        socket = self._connection.socket
        if commit_welcome is not None and socket is not None:
            await socket.send_binary(int(VoiceOpType.dave_mls_commit_welcome), commit_welcome)

    async def _handle_commit(self, payload: bytes) -> None:
        """
        Handle MLS_ANNOUNCE_COMMIT_TRANSITION (29): apply the announced commit.

        The payload is ``transition_id(2B big-endian) + commit``.
        """
        if self._session is None:
            return

        # Payload is ``transition_id(2B big-endian) + commit``.
        transition_id = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 0
        commit = payload[2:]

        try:
            self._session.process_commit(commit)
        except Exception as exc:
            _log.warning(f"Failed to process MLS commit: {exc}")
            await self._recover_from_invalid_commit(transition_id)
            return

        self._reinitializing = False

        if transition_id != 0:
            self._pending_transitions[transition_id] = self._pending_transition_version(transition_id)
            socket = self._connection.socket
            if socket is not None:
                await socket.send_transition_ready(transition_id)

    async def _handle_welcome(self, payload: bytes) -> None:
        """
        Handle MLS_WELCOME (30): join the group from the received welcome message.

        The payload is ``transition_id(2B big-endian) + welcome``.
        """
        if self._session is None:
            return

        # Payload is ``transition_id(2B big-endian) + welcome``.
        transition_id = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 0
        welcome = payload[2:]

        try:
            self._session.process_welcome(welcome)
        except Exception as exc:
            _log.warning(f"Failed to process MLS welcome: {exc}")
            await self._recover_from_invalid_commit(transition_id)
            return

        self._reinitializing = False

        if transition_id != 0:
            self._pending_transitions[transition_id] = self._pending_transition_version(transition_id)
            socket = self._connection.socket
            if socket is not None:
                await socket.send_transition_ready(transition_id)

    def _pending_transition_version(self, transition_id: int) -> int:
        """
        Resolve the protocol version to record for a transition.

        The transition is driven by an incoming commit/welcome. When
        ``DAVE_PREPARE_TRANSITION`` already recorded the negotiated target
        version for this ``transition_id``, preserve it so the later
        ``EXECUTE_TRANSITION`` applies the negotiated epoch rather than the
        current version. Otherwise (no matching pending transition, e.g. the
        commit/welcome arrived first) fall back to the current version.
        """
        return self._pending_transitions.get(transition_id, self._version)

    async def _recover_from_invalid_commit(self, transition_id: int) -> None:
        """
        Report a commit/welcome we couldn't apply and start over with a fresh session.

        Discord then removes us from the MLS group and adds us back with a new
        welcome. Only done once per failure, later failures are ignored until
        a commit or welcome applies again.

        Parameters
        ----------
        transition_id
            The transition whose commit or welcome failed.
        """
        if self._reinitializing:
            return

        socket = self._connection.socket
        if socket is None:
            return

        version = self._version or self._connection.dave_protocol_version
        if version <= 0:
            return

        self._reinitializing = True
        await socket.send_invalid_commit_welcome(transition_id)
        await self.reinit(version)

    @staticmethod
    def _extract_commit_welcome(result: object) -> bytes | None:
        """
        Extract the bytes to send for a ``davey.CommitWelcome`` result.

        ``davey``'s ``process_proposals`` returns ``None`` or a ``CommitWelcome``
        carrying a ``commit`` and an optional ``welcome``. Discord expects them
        concatenated as ``commit + welcome`` (commit alone when there is no welcome).

        Parameters
        ----------
        result
            The value returned by ``davey``'s proposal processing.

        Returns
        -------
            The serialized commit/welcome bytes, or ``None`` when there is nothing to send.
        """
        commit = getattr(result, "commit", None)
        if commit is None:
            return None

        welcome = getattr(result, "welcome", None)
        if welcome:
            return bytes(commit) + bytes(welcome)
        return bytes(commit)
