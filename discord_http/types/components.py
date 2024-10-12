from typing import Literal, NotRequired, TypedDict

from .emojis import PartialEmoji
from .channels import Type as ChannelType

# fmt: off
ComponentType = Literal[
    1,  # action row
    2,  # button
    3,  # string select
    4,  # text input
    5,  # user select
    6,  # role select
    7,  # mentionable select
    8,  # channel select
]
ButtonStyle = Literal[
    1,  # primary
    2,  # secondary
    3,  # success
    4,  # danger
    5,  # link
    6,  # premium
]
SelectDefaultValueType = Literal[
    "user",
    "role",
    "channel",
]
TextInputStyle = Literal[
    1,  # short
    2,  # paragraph
]
# fmt: on


class PartialButton(TypedDict):
    type: Literal[2]
    style: ButtonStyle


class Button(PartialButton):
    label: NotRequired[str]
    emoji: NotRequired[PartialEmoji]
    custom_id: NotRequired[str]
    disabled: NotRequired[bool]  # default false


class PremiumButton(PartialButton):
    sku_id: int


class URLButton(Button):
    url: str


class StringSelectMenuOption(TypedDict):
    label: str
    value: str
    description: NotRequired[str]
    emoji: NotRequired[PartialEmoji]
    default: NotRequired[bool]


class SelectDefaultValue(TypedDict):
    id: int  # id of a user, role or channel
    type: SelectDefaultValueType


class PartialSelectMenu(TypedDict):
    type: Literal[3, 5, 6, 7, 8]
    custom_id: str
    placeholder: NotRequired[str]
    min_values: NotRequired[int]
    max_values: NotRequired[int]
    disabled: NotRequired[bool]  # default false


class AutopopulatedSelectMenu(PartialSelectMenu):
    type: Literal[5, 6, 7, 8]
    default_values: list[SelectDefaultValue]


class StringSelectMenu(PartialSelectMenu):
    type: Literal[3]
    options: list[dict[str, str]]


class ChannelSelectMenu(PartialSelectMenu):
    type: Literal[8]
    channel_types: list[ChannelType]


class UserSelectMenu(PartialSelectMenu):
    type: Literal[5]


class RoleSelectMenu(PartialSelectMenu):
    type: Literal[6]


class MentionableSelectMenu(PartialSelectMenu):
    type: Literal[7]


class TextInput(TypedDict):
    type: Literal[4]
    custom_id: str
    style: TextInputStyle
    label: str
    min_lenght: NotRequired[int]
    max_length: NotRequired[int]
    required: NotRequired[bool]  # default true
    value: NotRequired[str]
    placeholder: NotRequired[str]


Component = (
    Button
    | URLButton
    | PremiumButton
    | StringSelectMenu
    | ChannelSelectMenu
    | UserSelectMenu
    | RoleSelectMenu
    | MentionableSelectMenu
    | TextInput
)


class ActionRow(TypedDict):
    type: Literal[1]
    components: list[Component]
