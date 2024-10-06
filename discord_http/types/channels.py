from typing import NotRequired, TypedDict

from .guilds import ThreadMember, ThreadMemberWithMember


class ThreadListSync(TypedDict):
    guild_id: int
    threads: list[dict] # channel objs
    members: list[ThreadMember] # thread member objs
    channel_ids: NotRequired[list[int]]

class ThreadMemberUpdate(ThreadMember):
    guild_id: int

class ThreadMembersUpdate(TypedDict):
    id: int
    guild_id: int
    member_count: int
    added_members: NotRequired[list[ThreadMemberWithMember]]
    removed_member_ids: NotRequired[list[int]]
