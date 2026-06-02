from ..enums import BaseEnum

__all__ = (
    "SUPPORTED_MODES",
    "VoiceOp",
)

SUPPORTED_MODES: tuple[str, ...] = ("aead_aes256_gcm_rtpsize",)


class VoiceOp(BaseEnum):
    """ Represents the opcode type of a voice gateway payload. """
    identify = 0
    select_protocol = 1
    ready = 2
    heartbeat = 3
    session_description = 4
    speaking = 5
    heartbeat_ack = 6
    resume = 7
    hello = 8
    resumed = 9
    clients_connect = 11
    client_connect = 12
    client_disconnect = 13
    dave_prepare_transition = 21
    dave_execute_transition = 22
    dave_transition_ready = 23
    dave_prepare_epoch = 24
    dave_mls_external_sender = 25
    dave_mls_key_package = 26
    dave_mls_proposals = 27
    dave_mls_commit_welcome = 28
    dave_mls_announce_commit_transition = 29
    dave_mls_welcome = 30
    dave_mls_invalid_commit_welcome = 31
