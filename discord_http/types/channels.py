from typing import Literal, NotRequired, TypedDict

from .guilds import ThreadMember, ThreadMemberWithMember

__all__ = (
    "StageInstance",
    "ThreadListSync",
    "ThreadMemberUpdate",
    "ThreadMembersUpdate",
)

PrivacyLevel = Literal[
    1,  # PUBLIC
    2,  # GUILD_ONLY
]


class StageInstance(TypedDict):
    id: int | str
    guild_id: int | str
    channel_id: int | str
    topic: str
    privacy_level: PrivacyLevel
    guild_scheduled_event_id: int | str | None


class ThreadListSync(TypedDict):
    guild_id: int
    threads: list[dict]  # channel objs
    members: list[ThreadMember]  # thread member objs
    channel_ids: NotRequired[list[int]]


class ThreadMemberUpdate(ThreadMember):
    guild_id: int


class ThreadMembersUpdate(TypedDict):
    id: int
    guild_id: int
    member_count: int
    added_members: NotRequired[list[ThreadMemberWithMember]]
    removed_member_ids: NotRequired[list[int]]
