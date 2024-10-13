from typing import NotRequired, TypedDict
from .snowflake import Snowflake

class PartialEmoji(TypedDict):
    id: Snowflake | None
    name: str
    animated: bool | None

class Emoji(PartialEmoji):
    roles: NotRequired[list[int]]
    user: NotRequired[dict]  # user obj
    require_colons: NotRequired[bool]
    managed: NotRequired[bool]
    available: NotRequired[bool]
