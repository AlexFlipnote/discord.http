from .utils import Enum

__all__ = (
    "ApplicationCommandType",
    "AuditLogType",
    "ButtonStyles",
    "ChannelType",
    "CommandOptionType",
    "ComponentType",
    "ContentFilterLevel",
    "DefaultNotificationLevel",
    "EntitlementOwnerType",
    "EntitlementType",
    "ForumLayoutType",
    "IntegrationType",
    "InteractionType",
    "InviteType",
    "MFALevel",
    "ResponseType",
    "SKUType",
    "ScheduledEventEntityType",
    "ScheduledEventPrivacyType",
    "ScheduledEventStatusType",
    "SortOrderType",
    "StickerFormatType",
    "StickerType",
    "TextStyles",
    "VerificationLevel",
    "VideoQualityType",
)


class IntegrationType(Enum):
    guild = 0
    user = 1


class InviteType(Enum):
    guild = 0
    group = 1
    dm = 2
    unknown = 3


class ApplicationCommandType(Enum):
    chat_input = 1
    user = 2
    message = 3


class DefaultNotificationLevel(Enum):
    all_messages = 0
    only_mentions = 1


class MFALevel(Enum):
    none = 0
    elevated = 1


class ContentFilterLevel(Enum):
    disabled = 0
    members_without_roles = 1
    all_members = 2


class AuditLogType(Enum):
    guild_update = 1
    channel_create = 10
    channel_update = 11
    channel_delete = 12
    channel_overwrite_create = 13
    channel_overwrite_update = 14
    channel_overwrite_delete = 15
    member_kick = 20
    member_prune = 21
    member_ban_add = 22
    member_ban_remove = 23
    member_update = 24
    member_role_update = 25
    member_move = 26
    member_disconnect = 27
    bot_add = 28
    role_create = 30
    role_update = 31
    role_delete = 32
    invite_create = 40
    invite_update = 41
    invite_delete = 42
    webhook_create = 50
    webhook_update = 51
    webhook_delete = 52
    emoji_create = 60
    emoji_update = 61
    emoji_delete = 62
    message_delete = 72
    message_bulk_delete = 73
    message_pin = 74
    message_unpin = 75
    integration_create = 80
    integration_update = 81
    integration_delete = 82
    stage_instance_create = 83
    stage_instance_update = 84
    stage_instance_delete = 85
    sticker_create = 90
    sticker_update = 91
    sticker_delete = 92
    guild_scheduled_event_create = 100
    guild_scheduled_event_update = 101
    guild_scheduled_event_delete = 102
    thread_create = 110
    thread_update = 111
    thread_delete = 112
    application_command_permission_update = 121
    auto_moderation_rule_create = 140
    auto_moderation_rule_update = 141
    auto_moderation_rule_delete = 142
    auto_moderation_block_message = 143
    auto_moderation_flag_to_channel = 144
    auto_moderation_user_communication_disabled = 145
    creator_monetization_request_created = 150
    creator_monetization_terms_accepted = 151


class ScheduledEventPrivacyType(Enum):
    guild_only = 2


class ScheduledEventEntityType(Enum):
    stage_instance = 1
    voice = 2
    external = 3


class ScheduledEventStatusType(Enum):
    scheduled = 1
    active = 2
    completed = 3
    canceled = 4


class VerificationLevel(Enum):
    none = 0
    low = 1
    medium = 2
    high = 3
    very_high = 4


class ChannelType(Enum):
    unknown = -1
    guild_text = 0
    dm = 1
    guild_voice = 2
    group_dm = 3
    guild_category = 4
    guild_news = 5
    guild_store = 6
    guild_news_thread = 10
    guild_public_thread = 11
    guild_private_thread = 12
    guild_stage_voice = 13
    guild_directory = 14
    guild_forum = 15


class CommandOptionType(Enum):
    sub_command = 1
    sub_command_group = 2
    string = 3
    integer = 4
    boolean = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10
    attachment = 11


class ResponseType(Enum):
    pong = 1
    channel_message_with_source = 4
    deferred_channel_message_with_source = 5
    deferred_update_message = 6
    update_message = 7
    application_command_autocomplete_result = 8
    modal = 9


class VideoQualityType(Enum):
    auto = 1
    full = 2


class ForumLayoutType(Enum):
    not_set = 0
    list_view = 1
    gallery_view = 2


class SortOrderType(Enum):
    latest_activity = 0
    creation_date = 1


class EntitlementType(Enum):
    purchase = 1
    premium_subscription = 2
    developer_gift = 3
    test_mode_purchase = 4
    free_purchase = 5
    user_gift = 6
    premium_purchase = 7
    application_subscription = 8


class EntitlementOwnerType(Enum):
    guild = 1
    user = 2


class SKUType(Enum):
    durable = 2
    consumable = 3
    subscription = 5
    subscription_group = 6


class InteractionType(Enum):
    ping = 1
    application_command = 2
    message_component = 3
    application_command_autocomplete = 4
    modal_submit = 5


class StickerType(Enum):
    standard = 1
    guild = 2


class StickerFormatType(Enum):
    png = 1
    apng = 2
    lottie = 3
    gif = 4


class ComponentType(Enum):
    action_row = 1
    button = 2
    string_select = 3
    text_input = 4
    user_select = 5
    role_select = 6
    mentionable_select = 7
    channel_select = 8


class ButtonStyles(Enum):
    # Original names
    primary = 1
    secondary = 2
    success = 3
    danger = 4
    link = 5
    premium = 6

    # Aliases
    blurple = 1
    grey = 2
    gray = 2
    green = 3
    destructive = 4
    red = 4
    url = 5


class TextStyles(Enum):
    short = 1
    paragraph = 2


class PermissionType(Enum):
    role = 0
    member = 1
