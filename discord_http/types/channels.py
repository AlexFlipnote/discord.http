from typing import Literal, NotRequired, TypedDict

from .guilds import ThreadMember, ThreadMemberWithMember

__all__ = (
    "StageInstance",
    "ThreadListSync",
    "ThreadMemberUpdate",
    "ThreadMembersUpdate",
)

# fmt: off
PrivacyLevel = Literal[
    1,  # PUBLIC
    2,  # GUILD_ONLY
]
Type = Literal[
    0,  # GUILD_TEXT
    1,  # DM
    2,  # GUILD_VOICE
    3,  # GROUP_DM
    4,  # GUILD_CATEGORY
    5,  # GUILD_ANNOUNCEMENT
    10, # ANNOUNCEMENT_THREAD
    11, # PUBLIC_THREAD
    12, # PRIVATE_THREAD
    13, # GUILD_STAGE_VOICE
    14, # GUILD_DIRECTORY
    15, # GUILD_FORUM
    16, # GUILD_MEDIA
]


# fmt: on

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
