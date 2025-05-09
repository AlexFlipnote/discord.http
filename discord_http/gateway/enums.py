from ..enums import BaseEnum

__all__ = (
    "ActivityType",
    "PayloadType",
    "PollVoteActionType",
    "ShardCloseType",
    "StatusType",
)


class PayloadType(BaseEnum):
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
    resume = 0
    reconnect = 1
    invalid_session = 2
    normal_crash = 100
    hard_crash = 101


class StatusType(BaseEnum):
    offline = 0
    online = 1
    idle = 2
    dnd = 3
    streaming = 4


class ActivityType(BaseEnum):
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5


class PollVoteActionType(BaseEnum):
    add = 0
    remove = 1
