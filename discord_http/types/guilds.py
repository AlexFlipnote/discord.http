from typing import NotRequired, TypedDict


class ThreadMember(TypedDict):
    id: int
    user_id: int # not available while GUILD_CREATE
    join_timestamp: str
    flags: int
    member: NotRequired[dict] # member obj


class ThreadMemberWithMember(ThreadMember):
    member: dict # member obj
