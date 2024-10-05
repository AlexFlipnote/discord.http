from typing import Literal, TypedDict

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
