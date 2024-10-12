from typing import Literal, NotRequired, TypedDict


class PartialEmoji(TypedDict):
    id: int | None
    name: str
    animated: bool | None

class Emoji(PartialEmoji):
    roles: NotRequired[list[int]]
    user: NotRequired[dict]  # user obj
    require_colons: NotRequired[bool]
    managed: NotRequired[bool]
    available: NotRequired[bool]
