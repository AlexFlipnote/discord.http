from ..enums import BaseEnum

__all__ = (
    "PayloadType",
    "ShardCloseType",
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
