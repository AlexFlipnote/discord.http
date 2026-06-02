import logging

from typing import TYPE_CHECKING, Any

try:
    import davey  # type: ignore[import-not-found]
    has_dave = True
except ImportError:
    davey = None
    has_dave = False

from .enums import VoiceOpType

if TYPE_CHECKING:
    from .connection import VoiceConnection

# The ``davey`` session object is dynamically typed (the package may be absent and its
# exact API is not statically known here), so it is treated as ``Any`` to keep static
# analysis clean without scattering per-access suppressions.
_Session = Any

__all__ = (
    "DaveManager",
    "has_dave",
    "max_protocol_version",
)

_log = logging.getLogger(__name__)


def max_protocol_version() -> int:
    """
    The maximum DAVE protocol version this installation can negotiate.

    Returns
    -------
        The ``davey.DAVE_PROTOCOL_VERSION`` when the optional ``davey`` package is
        installed, otherwise ``0`` (signalling that only transport encryption is available).
    """
    if has_dave and davey is not None:
        return int(davey.DAVE_PROTOCOL_VERSION)
    return 0


class DaveManager:
    """
    Manages DAVE (Discord Audio/Video End-to-end Encryption) for a voice connection.

    DAVE layers end-to-end encryption on top of Discord's transport encryption using
    the MLS (Messaging Layer Security) protocol, provided by the optional ``davey``
    package. When ``davey`` is not installed, this manager degrades gracefully: every
    method becomes a safe no-op and audio is passed through unchanged so that the base
    library keeps working with transport encryption only.

    The manager wraps a single ``davey.DaveSession`` and is driven by the voice
    connection and socket, which forward the negotiated protocol version and the binary
    MLS opcodes (21-31) received from the voice gateway. Outbound MLS messages are sent
    back through ``connection.socket.send_binary(opcode, payload)``.

    Parameters
    ----------
    connection:
        The voice connection this manager operates on. Used to read ``user_id`` and
        ``channel_id``, to send binary MLS operations, and to learn the negotiated version.
    """

    __slots__ = (
        "_connection",
        "_pending_transition",
        "_session",
        "_version",
    )

    def __init__(self, connection: "VoiceConnection"):
        self._connection: "VoiceConnection" = connection
        self._session: _Session | None = None
        self._version: int = 0
        self._pending_transition: tuple[int, int] | None = None

    @property
    def ready(self) -> bool:
        """ Whether the underlying MLS session has completed its handshake. """
        if self._session is not None:
            try:
                return bool(self._session.ready)
            except AttributeError:
                return False
        return False

    @property
    def voice_privacy_code(self) -> str | None:
        """ The privacy code users can compare out-of-band to verify the E2EE session, if any. """
        if self._session is not None:
            try:
                code = self._session.voice_privacy_code
            except AttributeError:
                return None
            return str(code) if code is not None else None
        return None

    def can_encrypt(self) -> bool:
        """ Whether end-to-end encryption is currently active and usable. """
        return self._version > 0 and self._session is not None and self.ready

    async def reinit(self, version: int) -> None:
        """
        Create or reinitialise the MLS session for a given protocol version.

        When ``version`` is greater than ``0`` but ``davey`` is not installed, a clear,
        actionable :class:`RuntimeError` is raised telling the user how to install the
        optional dependency. When a session is created, its serialized MLS key package is
        sent to the voice gateway.

        Parameters
        ----------
        version:
            The negotiated DAVE protocol version. ``0`` disables end-to-end encryption.

        Raises
        ------
        RuntimeError
            If a non-zero DAVE version is requested but ``davey`` is not installed.
        """
        self._version = version

        if version <= 0:
            self._session = None
            return

        if not has_dave or davey is None:
            raise RuntimeError(
                "Discord negotiated DAVE end-to-end encryption "
                f"(protocol version {version}), but the optional 'davey' package is not "
                'installed. Install it with: pip install "discord.http[voice]"'
            )

        try:
            self._session = davey.DaveSession(
                version,
                self._connection.user_id,
                self._connection.channel_id,
            )
        except Exception as exc:
            _log.warning(f"Failed to initialise DAVE session: {exc}")
            self._session = None
            return

        await self._send_key_package()

    async def _send_key_package(self) -> None:
        """ Serialize and send our MLS key package to the voice gateway. """
        if self._session is None:
            return

        try:
            key_package = self._session.get_serialized_key_package()
        except AttributeError:
            return

        await self._connection.socket.send_binary(
            int(VoiceOpType.dave_mls_key_package), key_package
        )

    def set_passthrough_mode(self, enabled: bool) -> None:
        """
        Toggle passthrough mode on the MLS session.

        While in passthrough mode the session does not transform media, allowing audio to
        flow during transitions where some participants are not yet on the new epoch.

        Parameters
        ----------
        enabled:
            ``True`` to pass media through unchanged, ``False`` to resume encryption.
        """
        if self._session is None:
            return

        try:
            self._session.set_passthrough_mode(enabled)
        except AttributeError:
            pass

    def encrypt_opus(self, opus: bytes) -> bytes:
        """
        End-to-end encrypt an outbound Opus frame.

        Parameters
        ----------
        opus:
            The plaintext Opus frame.

        Returns
        -------
            The encrypted frame, or the input unchanged when E2EE is not active.
        """
        if not self.can_encrypt() or self._session is None:
            return opus
        try:
            return bytes(self._session.encrypt_opus(opus))
        except AttributeError:
            return opus

    def decrypt_opus(self, user_id: int, opus: bytes) -> bytes:
        """
        End-to-end decrypt an inbound Opus frame from a given user.

        Parameters
        ----------
        user_id:
            The user the frame originated from.
        opus:
            The received Opus frame.

        Returns
        -------
            The decrypted frame, or the input unchanged when E2EE is not active.
        """
        if not self.can_encrypt() or self._session is None:
            return opus
        try:
            return bytes(self._session.decrypt_opus(user_id, opus))
        except AttributeError:
            return opus

    async def handle_binary(self, opcode: int, payload: bytes) -> None:
        """
        Dispatch a binary DAVE/MLS operation (opcodes 21-31) received from the gateway.

        Parameters
        ----------
        opcode:
            The voice opcode, expected to be one of the DAVE ops 21-31.
        payload:
            The raw binary payload following the opcode.
        """
        match opcode:
            case VoiceOpType.dave_prepare_transition:
                await self._handle_prepare_transition(payload)
            case VoiceOpType.dave_execute_transition:
                await self._handle_execute_transition(payload)
            case VoiceOpType.dave_prepare_epoch:
                await self._handle_prepare_epoch(payload)
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

    async def _handle_prepare_transition(self, payload: bytes) -> None:
        """ Handle PREPARE_TRANSITION (21): record the pending transition and acknowledge. """
        transition_id, version = self._parse_transition(payload)
        self._pending_transition = (transition_id, version)

        if transition_id == 0:
            await self._execute_transition(transition_id, version)
        else:
            await self._connection.socket.send_transition_ready(transition_id)

    async def _handle_execute_transition(self, payload: bytes) -> None:
        """ Handle EXECUTE_TRANSITION (22): apply the pending version and passthrough state. """
        transition_id, _ = self._parse_transition(payload)

        if self._pending_transition is not None:
            pending_id, version = self._pending_transition
            if pending_id == transition_id:
                await self._execute_transition(transition_id, version)
                return

        _log.debug(f"Received EXECUTE_TRANSITION for unknown transition {transition_id}")

    async def _execute_transition(self, transition_id: int, version: int) -> None:
        """ Apply a transition: switch protocol version and update passthrough mode. """
        self._version = version
        self.set_passthrough_mode(version == 0)
        self._pending_transition = None
        _log.debug(f"Executed DAVE transition {transition_id} to version {version}")

    async def _handle_prepare_epoch(self, payload: bytes) -> None:
        """ Handle PREPARE_EPOCH (24): reinitialise the session for a new MLS epoch. """
        _epoch, version = self._parse_transition(payload)
        await self.reinit(version)

    def _handle_external_sender(self, payload: bytes) -> None:
        """ Handle MLS_EXTERNAL_SENDER (25): register the gateway's external sender. """
        if self._session is not None:
            try:
                self._session.set_external_sender(payload)
            except AttributeError:
                pass

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

        optype = payload[0]
        proposals = payload[1:]
        operation_type = (
            davey.ProposalsOperationType.append
            if optype == 0
            else davey.ProposalsOperationType.revoke
        )

        try:
            result = self._session.process_proposals(operation_type, proposals)
        except AttributeError:
            return
        except Exception as exc:
            _log.warning(f"Failed to process MLS proposals: {exc}")
            await self._recover_from_invalid_commit()
            return

        commit_welcome = self._extract_commit_welcome(result)
        if commit_welcome is not None:
            await self._connection.socket.send_binary(
                int(VoiceOpType.dave_mls_commit_welcome), commit_welcome
            )

    async def _handle_commit(self, payload: bytes) -> None:
        """
        Handle MLS_ANNOUNCE_COMMIT_TRANSITION (29): apply the announced commit.

        The payload is ``transition_id(2B big-endian) + commit``.
        """
        if self._session is None:
            return

        transition_id = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 0
        commit = payload[2:]

        try:
            self._session.process_commit(commit)
        except AttributeError:
            return
        except Exception as exc:
            _log.warning(f"Failed to process MLS commit: {exc}")
            await self._recover_from_invalid_commit()
            return

        if transition_id != 0:
            self._pending_transition = (transition_id, self._version)
            await self._connection.socket.send_transition_ready(transition_id)

    async def _handle_welcome(self, payload: bytes) -> None:
        """
        Handle MLS_WELCOME (30): join the group from the received welcome message.

        The payload is ``transition_id(2B big-endian) + welcome``.
        """
        if self._session is None:
            return

        transition_id = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 0
        welcome = payload[2:]

        try:
            self._session.process_welcome(welcome)
        except AttributeError:
            return
        except Exception as exc:
            _log.warning(f"Failed to process MLS welcome: {exc}")
            await self._recover_from_invalid_commit()
            return

        if transition_id != 0:
            self._pending_transition = (transition_id, self._version)
            await self._connection.socket.send_transition_ready(transition_id)

    async def _recover_from_invalid_commit(self) -> None:
        """ Notify the gateway of an invalid commit/welcome and reinitialise the session. """
        await self._connection.socket.send_binary(
            int(VoiceOpType.dave_mls_invalid_commit_welcome), b""
        )
        await self.reinit(self._version)

    @staticmethod
    def _extract_commit_welcome(result: _Session) -> bytes | None:
        """
        Extract the bytes to send for a ``davey.CommitWelcome`` result.

        ``davey``'s ``process_proposals`` returns a ``CommitWelcome`` carrying a
        ``commit`` and an optional ``welcome``. Discord expects them concatenated
        as ``commit + welcome`` (commit alone when there is no welcome). This also
        tolerates raw bytes or a ``None`` result.

        Parameters
        ----------
        result:
            The (dynamically typed) value returned by ``davey``'s proposal processing.

        Returns
        -------
            The serialized commit/welcome bytes, or ``None`` when there is nothing to send.
        """
        if result is None:
            return None
        if isinstance(result, (bytes, bytearray)):
            return bytes(result)

        commit = getattr(result, "commit", None)
        if commit is not None:
            welcome = getattr(result, "welcome", None)
            if welcome:
                return bytes(commit) + bytes(welcome)
            return bytes(commit)

        if hasattr(result, "serialize"):
            try:
                return bytes(result.serialize())
            except Exception:
                return None
        return None

    @staticmethod
    def _parse_transition(payload: bytes) -> tuple[int, int]:
        """
        Parse a transition payload into ``(transition_id, version)``.

        Transition payloads carry a 2-byte big-endian transition id optionally followed by
        a 1-byte protocol version. Missing fields default to ``0``.
        """
        transition_id = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 0
        version = payload[2] if len(payload) >= 3 else 0
        return transition_id, version
