from typing import Literal, NotRequired, TypedDict
from .snowflake import Snowflake

__all__ = (
    "ThreadMember",
    "ThreadMemberWithMember",
)

# fmt: off
PrivacyLevel = Literal[
    2,  # GUILD_ONLY
]
EntityType = Literal[
    1,  # STAGE_INSTANCE
    2,  # VOICE
    3,  # EXTERNAL
]
EventStatus = Literal[
    1,  # SCHEDULED
    2,  # ACTIVE
    3,  # COMPLETED
    4,  # CANCELLED
]
# fmt: on


class ThreadMember(TypedDict):
    id: int
    user_id: int  # not available while GUILD_CREATE
    join_timestamp: str
    flags: int
    member: NotRequired[dict]  # member obj


class ThreadMemberWithMember(ThreadMember):
    member: dict  # member obj

class GuildScheduleEvent(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    channel_id: Snowflake | None
    creator_id: NotRequired[Snowflake | None]
    name: str
    description: NotRequired[str | None]
    scheduled_start_time: str # ISO8601 timestamp
    scheduled_end_time: str | None # ISO8601 timestamp
    privacy_level: PrivacyLevel
    status: EventStatus
    entity_type: EntityType
    entity_metadata: NotRequired[dict | None]
