from typing import Any, Literal, NotRequired, TypedDict

from .application import IntegrationTypes
from .commands import ApplicationCommandType, ApplicationCommandOptionType
from .components import ComponentType, Component

# fmt: off
InteractionType = Literal[
    1,  # PING
    2,  # APPLICATION_COMMAND
    3,  # MESSAGE_COMPONENT
    4,  # APPLICATION_COMMAND_AUTOCOMPLETE
    5,  # MODAL_SUBMIT
]
InteractionContextType = Literal[
    0,  # GUILD
    1,  # BOT_DM
    2,  # PRIVATE_CHANNEL
]
# fmt: on

class ResolvedDataChannel(TypedDict):
    id: int
    name: str
    type: int
    permissions: int

class ResolvedDataThread(ResolvedDataChannel):
    thread_metadata: dict
    parent_id: int

class ResolvedData(TypedDict):
    users: NotRequired[dict[int, dict]] # int: user object
    members: NotRequired[dict[int, dict]] # int: partial guild member object
    roles: NotRequired[dict[int, dict]] # int: role object
    channels: NotRequired[dict[int, ResolvedDataChannel | ResolvedDataThread]] # int: partial channel object
    messages: NotRequired[dict[int, dict]] # int: partial message object
    attachments: NotRequired[dict[int, dict]] # int: attachment object

class ApplicationCommandDataOption(TypedDict):
    name: str
    type: ApplicationCommandOptionType
    value: NotRequired[dict] # string | int | float | bool
    options: NotRequired[list["ApplicationCommandDataOption"]]
    focused: NotRequired[bool] # 'true' if this option is the currently focused option for autocomplete

class ApplicationCommandData(TypedDict):
    id: int
    name: str
    type: ApplicationCommandType
    resolved: NotRequired[ResolvedData]
    options: NotRequired[list[ApplicationCommandDataOption]] # can be partial if autocomplete
    target_id: NotRequired[int] # target user or message id

class MessageComponentData(TypedDict):
    custom_id: str
    component_type: ComponentType
    values: NotRequired[list[Any]]  # select values
    resolved: NotRequired[ResolvedData]

class ModalSubmitData(TypedDict):
    custom_id: str
    components: NotRequired[list[Component]]  # value submitted by the user

InteractionData = (
    ApplicationCommandData
    | MessageComponentData
    | ModalSubmitData
)

class PartialInteraction(TypedDict):
    id: int
    application_id: int
    type: InteractionType
    data: NotRequired[InteractionData]
    guild: NotRequired[dict]  # partial guild object
    channel: NotRequired[dict]  # partial channel object
    channel_id: NotRequired[int]
    member: NotRequired[dict]  # guild member object
    user: NotRequired[dict]  # user object if invoked by in a dm
    token: str
    version: int
    message: NotRequired[dict]  # message object
    app_permissions: str
    locale: NotRequired[str]
    entitlements: NotRequired[dict]  # entitlements object
    # https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object-authorizing-integration-owners-object
    authorizing_integration_owners: NotRequired[dict[IntegrationTypes, Any]]  # TODO:
    contexts: NotRequired[InteractionContextType]

class DMInteraction(PartialInteraction):
    user: dict  # user object
    context: Literal[1, 2]

class GuildInteraction(PartialInteraction):
    guild: dict  # guild object
    context: Literal[0]

class ApplicationCommandInteraction(DMInteraction, GuildInteraction, PartialInteraction):
    type: Literal[2, 4]
    data: ApplicationCommandData
    locale: str

class MessageComponentInteraction(DMInteraction, GuildInteraction, PartialInteraction):
    type: Literal[3]
    data: MessageComponentData
    locale: str

class ModalSubmitInteraction(DMInteraction, GuildInteraction, PartialInteraction):
    type: Literal[5]
    data: ModalSubmitData
    locale: str

class PingInteraction(DMInteraction, GuildInteraction, PartialInteraction):
    type: Literal[1]
