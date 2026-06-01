from ..enums import BaseEnum

__all__ = (
    "ActivityType",
    "PayloadType",
    "PollVoteActionType",
    "ShardCloseType",
    "StatusType",
)


class PayloadType(BaseEnum):
    """ Represents the opcode type of a gateway payload. """
    dispatch = 0
    heartbeat = 1
    identify = 2
    presence = 3
    voice_state = 4
    voice_ping = 5
    resume = 6
    reconnect = 7
    request_guild_members = 8
    invalidate_session = 9
    hello = 10
    heartbeat_ack = 11
    guild_sync = 12


class ShardCloseType(BaseEnum):
    """ Represents the close type of a gateway shard. """
    resume = 0
    reconnect = 1
    invalid_session = 2
    normal_crash = 100
    hard_crash = 101


class StatusType(BaseEnum):
    """ Represents the online status of a user or bot. """
    offline = 0
    online = 1
    idle = 2
    dnd = 3
    streaming = 4


class ActivityType(BaseEnum):
    """ Represents the type of a gateway presence activity. """
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5
    hang = 6


class PollVoteActionType(BaseEnum):
    """ Represents whether a poll vote was added or removed. """
    add = 0
    remove = 1
