from typing import Any, Literal, NotRequired, TypedDict

from .automoderation import AutoModerationRule
from .commands import ApplicationCommand

# fmt: off
AuditLogEvent = Literal[
    # VALUE - EVENT - OBJECT
    1,  # GUILD_UPDATE - guild
    10,  # CHANNEL_CREATE - channel
    11,  # CHANNEL_UPDATE - channel
    12,  # CHANNEL_DELETE - channel
    13,  # CHANNEL_OVERWRITE_CREATE - channel
    14,  # CHANNEL_OVERWRITE_UPDATE - channel
    15,  # CHANNEL_OVERWRITE_DELETE - channel
    20,  # MEMBER_KICK - None
    21,  # MEMBER_PRUNE - None
    22,  # MEMBER_BAN_ADD - None
    23,  # MEMBER_BAN_REMOVE - None
    24,  # MEMBER_UPDATE - member
    25,  # MEMBER_ROLE_UPDATE - partial role
    26,  # MEMBER_MOVE - None
    27,  # MEMBER_DISCONNECT - None
    28,  # BOT_ADD - None
    30,  # ROLE_CREATE - role
    31,  # ROLE_UPDATE - role
    32,  # ROLE_DELETE - role
    40,  # INVITE_CREATE - invite
    41,  # INVITE_UPDATE - invite
    42,  # INVITE_DELETE - invite and metadata
    50,  # WEBHOOK_CREATE - webhook
    51,  # WEBHOOK_UPDATE - webhook
    52,  # WEBHOOK_DELETE - webhook
    60,  # EMOJI_CREATE - emoji
    61,  # EMOJI_UPDATE - emoji
    62,  # EMOJI_DELETE - emoji
    72,  # MESSAGE_DELETE - none
    73,  # MESSAGE_BULK_DELETE - none
    74,  # MESSAGE_PIN - none
    75,  # MESSAGE_UNPIN - none
    80,  # INTEGRATION_CREATE - integration
    81,  # INTEGRATION_UPDATE - integration
    82,  # INTEGRATION_DELETE - integration
    83,  # STAGE_INSTANCE_CREATE - stage instance
    84,  # STAGE_INSTANCE_UPDATE - stage instance
    85,  # STAGE_INSTANCE_DELETE - stage instance
    90,  # STICKER_CREATE - sticker
    91,  # STICKER_UPDATE - sticker
    92,  # STICKER_DELETE - sticker
    100, # GUILD_SCHEDULED_EVENT_CREATE - guild scheduled event
    101, # GUILD_SCHEDULED_EVENT_UPDATE - guild scheduled event
    102, # GUILD_SCHEDULED_EVENT_DELETE - guild scheduled event
    110, # THREAD_CREATE - thread
    111, # THREAD_UPDATE - thread
    112, # THREAD_DELETE - thread
    121, # APPLICATION_COMMAND_PERMISSION_UPDATE - application command permissions
    130, # SOUNDBOARD_SOUND_CREATE - soundboard sound
    131, # SOUNDBOARD_SOUND_UPDATE - soundboard sound
    132, # SOUNDBOARD_SOUND_DELETE - soundboard sound
    140, # AUTO_MODERATION_RULE_CREATE - auto moderation rule
    141, # AUTO_MODERATION_RULE_UPDATE - auto moderation rule
    142, # AUTO_MODERATION_RULE_DELETE - auto moderation rule
    143, # AUTO_MODERATION_BLOCK_MESSAGE - none
    144, # AUTO_MODERATION_FLAG_TO_CHANNEL - none
    145, # AUTO_MODERATION_USER_COMMUNICATION_DISABLED - none
    150, # CREATOR_MONETIZATION_REQUEST_CREATED - none
    151, # CREATOR_MONETIZATION_TERMS_ACCEPTED - none
    163, # ONBOARDING_PROMPT_CREATE - onboarding prompt
    164, # ONBOARDING_PROMPT_UPDATE - onboarding prompt
    165, # ONBOARDING_PROMPT_DELETE - onboarding prompt
    166, # ONBOARDING_CREATE - guild onboarding
    167, # ONBOARDING_UPDATE - guild onboarding
    190, # HOME_SETTINGS_CREATE - none
    191, # HOME_SETTINGS_UPDATE - none

]


# fmt: on


# APPLICATION_COMMAND_PERMISSION_UPDATE
class OptionalApplicationCommandPermissionsUpdateAuditEntryInfo(TypedDict):
    application_id: int


# AUTO_MODERATION_BLOCK_MESSAGE & AUTO_MODERATION_FLAG_TO_CHANNEL & AUTO_MODERATION_USER_COMMUNICATION_DISABLED
class OptionalAutoModerationAuditEntryInfo(TypedDict):
    auto_moderation_rule_name: str
    auto_moderation_rule_trigger_type: str


# MEMBER_MOVE & MESSAGE_PIN & MESSAGE_UNPIN & MESSAGE_DELETE & STAGE_INSTANCE_CREATE & STAGE_INSTANCE_UPDATE & STAGE_INSTANCE_DELETE & AUTO_MODERATION_BLOCK_MESSAGE & AUTO_MODERATION_FLAG_TO_CHANNEL & AUTO_MODERATION_USER_COMMUNICATION_DISABLED
class OptionalChannelAuditEntryInfo(TypedDict):
    channel_id: int


# MESSAGE_DELETE & MESSAGE_BULK_DELETE & MEMBER_DISCONNECT & MEMBER_MOVE
class OptionalCountAuditEntryInfo(TypedDict):
    count: str


# MEMBER_PRUNE
class OptionalMembersPruneAuditEntryInfo(TypedDict):
    delete_member_days: str
    members_removed: str

# CHANNEL_OVERWRITE_CREATE & CHANNEL_OVERWRITE_UPDATE & CHANNEL_OVERWRITE_DELETE
class OptionalIDAuditEntryInfo(TypedDict):
    id: int


# CHANNEL_OVERWRITE_CREATE & CHANNEL_OVERWRITE_UPDATE & CHANNEL_OVERWRITE_DELETE
class OptionalOverwriteAuditEntryInfo(OptionalIDAuditEntryInfo, TypedDict):
    type: Literal["0", "1"]  # 0 = role, 1 = member


# CHANNEL_OVERWRITE_CREATE & CHANNEL_OVERWRITE_UPDATE & CHANNEL_OVERWRITE_DELETE
class OptionalRoleOverwriteAuditEntryInfo(OptionalOverwriteAuditEntryInfo):
    type: Literal["0"]
    role_name: str


# CHANNEL_OVERWRITE_CREATE & CHANNEL_OVERWRITE_UPDATE & CHANNEL_OVERWRITE_DELETE
class OptionalMemberAuditEntryInfo(OptionalOverwriteAuditEntryInfo):
    integration_type: str



# MESSAGE_PIN & MESSAGE_UNPIN
class OptionalMessageIDAuditEntryInfo(TypedDict):
    message_id: int


AuditLogEntryOptions = (
    OptionalApplicationCommandPermissionsUpdateAuditEntryInfo
    | OptionalAutoModerationAuditEntryInfo
    | OptionalChannelAuditEntryInfo
    | OptionalCountAuditEntryInfo
    | OptionalMembersPruneAuditEntryInfo
    | OptionalIDAuditEntryInfo
    | OptionalMessageIDAuditEntryInfo
    | OptionalOverwriteAuditEntryInfo
    | OptionalRoleOverwriteAuditEntryInfo
    | OptionalMemberAuditEntryInfo
)


class AuditLogChange(TypedDict):
    new_value: NotRequired[Any]
    old_value: NotRequired[Any]
    key: str

class AuditLogEntry(TypedDict):
    target_id: int
    changes: list[AuditLogChange]
    user_id: int | None
    id: int
    action_type: AuditLogEvent
    options: NotRequired[dict[str, Any]]
    reason: NotRequired[str]


class ApplicationCommandPermissionsUpdateAuditLogEntry(AuditLogEntry):
    action_type: Literal[121]
    options: OptionalApplicationCommandPermissionsUpdateAuditEntryInfo

class AutoModerationBlockMessageAuditLogEntry(AuditLogEntry):
    action_type: Literal[143, 144, 145]
    options: OptionalAutoModerationAuditEntryInfo

class WithChannelAuditLogEntry(AuditLogEntry):
    action_type: Literal[26, 74, 75, 72, 83, 84, 85, 143, 144, 145]
    options: OptionalChannelAuditEntryInfo

class WithCountAuditLogEntry(AuditLogEntry):
    action_type: Literal[72, 73, 27, 26]
    options: OptionalCountAuditEntryInfo

class WithDMembersPruneAuditEntryInfo(AuditLogEntry):
    action_type: Literal[21]
    options: OptionalMembersPruneAuditEntryInfo

class WithOverwriteAuditLogEntry(AuditLogEntry):
    action_type: Literal[13, 14, 15]
    options: OptionalIDAuditEntryInfo | OptionalRoleOverwriteAuditEntryInfo | OptionalMemberAuditEntryInfo

class WithMessageIDAuditLogEntry(AuditLogEntry):
    action_type: Literal[74, 75]
    options: OptionalMessageIDAuditEntryInfo

OptionalAuditLogEntry = (
    ApplicationCommandPermissionsUpdateAuditLogEntry
    | AutoModerationBlockMessageAuditLogEntry
    | WithChannelAuditLogEntry
    | WithCountAuditLogEntry
    | WithDMembersPruneAuditEntryInfo
    | WithOverwriteAuditLogEntry
    | WithMessageIDAuditLogEntry
    | AuditLogEntry
)

class AuditLog(TypedDict):
    application_commands: list[ApplicationCommand]
    audit_log_entries: list[OptionalAuditLogEntry]
    auto_moderation_rules: list[AutoModerationRule]
    guild_scheduled_events: list[dict]
    integrations: list[dict]
    threads: list[dict]
    users: list[dict]
    webhooks: list[dict]