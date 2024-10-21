from typing import Literal, NotRequired, TypedDict

from .application import IntegrationTypes
from .channels import Type as ChannelType
from .snowflake import Snowflake

# fmt: off
ApplicationCommandType = Literal[
    1,  # CHAT_INPUT
    2,  # USER
    3,  # MESSAGE
    4,  # PRIMARY_ENTRY_POINT
]
ApplicationCommandOptionType = Literal[
    1,  # SUB_COMMAND
    2,  # SUB_COMMAND_GROUP
    3,  # STRING
    4,  # INTEGER
    5,  # BOOLEAN
    6,  # USER
    7,  # CHANNEL
    8,  # ROLE
    9,  # MENTIONABLE
    10, # NUMBER
    11, # ATTACHMENT
]
EntryPointCommandHandlerType = Literal[
    1,  # APP_HANDLER
    2,  # DISCORD_LAUNCH_ACTIVITY
]
ApplicationCommandPermissionsType = Literal[
    1,  # ROLE
    2,  # USER
    3,  # CHANNEL
]
# fmt: on

class PartialApplicationCommandOption(TypedDict):
    type: ApplicationCommandOptionType
    name: str
    name_localizations: NotRequired[dict[str, str] | None]
    description: str
    description_localizations: NotRequired[dict[str, str] | None]

class OptionChoice(TypedDict):
    name: str
    name_localizations: NotRequired[dict[str, str] | None]
    value: str

class OptionChoiceApplicationCommandOption(TypedDict):
    type: Literal[3, 4, 10]
    choices: NotRequired[list[OptionChoice]]

class RequiredApplicationCommandOption(TypedDict):
    type: Literal[3, 4, 5, 6, 7, 8, 9, 10, 11]
    required: NotRequired[bool]

class AutoCompleteApplicationCommandOption(TypedDict):
    type: Literal[3, 4, 10]
    autocomplete: NotRequired[bool]

class StringApplicationCommandOption(PartialApplicationCommandOption, AutoCompleteApplicationCommandOption, OptionChoiceApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[3]
    min_length: NotRequired[int]
    max_length: NotRequired[int]

class IntegerApplicationCommandOption(PartialApplicationCommandOption, AutoCompleteApplicationCommandOption, OptionChoiceApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[4]
    min_value: NotRequired[int]
    max_value: NotRequired[int]

class NumberApplicationCommandOption(PartialApplicationCommandOption, AutoCompleteApplicationCommandOption, OptionChoiceApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[10]
    min_value: NotRequired[float]
    max_value: NotRequired[float]

class OptionsApplicationCommandOption(PartialApplicationCommandOption):
    type: Literal[1, 2]
    options: list[PartialApplicationCommandOption]

class ChannelApplicationCommandOption(PartialApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[7]
    channel_types: list[ChannelType]

class UserApplicationCommandOption(PartialApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[6]

class RoleApplicationCommandOption(PartialApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[8]

class MentionableApplicationCommandOption(PartialApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[9]

class BooleanApplicationCommandOption(PartialApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[5]

class AttachmentApplicationCommandOption(PartialApplicationCommandOption, RequiredApplicationCommandOption):
    type: Literal[11]


ChatInputApplicationCommandOption = (
    StringApplicationCommandOption
    | IntegerApplicationCommandOption
    | NumberApplicationCommandOption
    | OptionsApplicationCommandOption
    | ChannelApplicationCommandOption
    | UserApplicationCommandOption
    | RoleApplicationCommandOption
    | MentionableApplicationCommandOption
    | BooleanApplicationCommandOption
    | AttachmentApplicationCommandOption
)

class PartialApplicationCommand(TypedDict):
    id: Snowflake
    type: NotRequired[ApplicationCommandType] # defaults 1
    application_id: Snowflake
    guild_id: NotRequired[Snowflake]
    name: str
    name_localizations: NotRequired[dict[str, str] | None]
    description: str
    description_localizations: NotRequired[dict[str, str] | None]
    default_member_permissions: str | None
    nsfw: NotRequired[bool]
    integration_types: NotRequired[list[IntegrationTypes]]
    contexts: NotRequired[IntegrationTypes]
    version: int
    handler: NotRequired[EntryPointCommandHandlerType]

class ChatInputApplicationCommand(PartialApplicationCommand):
    type: Literal[1]
    options: list[ChatInputApplicationCommandOption]

class UserApplicationCommand(PartialApplicationCommand):
    type: Literal[2]

class MessageApplicationCommand(PartialApplicationCommand):
    type: Literal[3]

class PrimaryEntryPointApplicationCommand(PartialApplicationCommand):
    type: Literal[4]

ApplicationCommand = (
    ChatInputApplicationCommand
    | UserApplicationCommand
    | MessageApplicationCommand
    | PrimaryEntryPointApplicationCommand
)




class ApplicationCommandPermissions(TypedDict):
    # id of the role, user or channel
    # or a constant value
    # guild_id = all guild members
    # guild_id - 1 # all channels in the guild
    id: Snowflake 
    type: ApplicationCommandPermissionsType
    permissions: bool # true to allow, false to disallow

class GuildApplicationCommandPermissions(TypedDict):
    id: Snowflake
    application_id: Snowflake
    guild_id: Snowflake
    permissions: list[ApplicationCommandPermissions]