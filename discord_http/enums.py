import random
import numbers

from typing import Self
from enum import Enum as _Enum

__all__ = (
    "ApplicationCommandType",
    "AuditLogType",
    "AutoModRuleActionType",
    "AutoModRuleEventType",
    "AutoModRulePresetType",
    "AutoModRuleTriggerType",
    "BaseEnum",
    "ButtonStyles",
    "ChannelType",
    "CommandOptionType",
    "ComponentType",
    "ContentFilterLevel",
    "DefaultAvatarType",
    "DefaultNotificationLevel",
    "EntitlementOwnerType",
    "EntitlementType",
    "ExpireBehaviour",
    "ForumLayoutType",
    "IntegrationType",
    "InteractionType",
    "InviteType",
    "MFALevel",
    "MessageReferenceType",
    "MessageType",
    "PermissionType",
    "PrivacyLevelType",
    "ReactionType",
    "ResponseType",
    "SKUType",
    "ScheduledEventEntityType",
    "ScheduledEventStatusType",
    "SeparatorSpacingType",
    "SortOrderType",
    "StickerFormatType",
    "StickerType",
    "TextStyles",
    "VerificationLevel",
    "VideoQualityType",
    "WebhookType",
)


class BaseEnum(_Enum):
    """ Enum, but with more comparison operators to make life easier. """
    @classmethod
    def random(cls) -> Self:
        """ Return a random enum. """
        return random.choice(list(cls))

    def __str__(self) -> str:
        """ Return the name of the enum. """
        return self.name

    def __int__(self) -> int:
        """ Return the value of the enum. """
        return self.value

    def __hash__(self) -> int:
        """ Return the hash of the enum. """
        return hash(self.value)

    def __gt__(self, other: Self) -> bool:
        """ Greater than. """
        try:
            return self.value > other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value > other
        except Exception:
            pass
        return NotImplemented

    def __lt__(self, other: Self) -> bool:
        """ Less than.  """
        try:
            return self.value < other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value < other
        except Exception:
            pass
        return NotImplemented

    def __ge__(self, other: Self) -> bool:
        """ Greater than or equal to. """
        try:
            return self.value >= other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value >= other
            if isinstance(other, str):
                return self.name == other
        except Exception:
            pass
        return NotImplemented

    def __le__(self, other: Self) -> bool:
        """ Less than or equal to. """
        try:
            return self.value <= other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value <= other
            if isinstance(other, str):
                return self.name == other
        except Exception:
            pass
        return NotImplemented

    def __eq__(self, other: Self) -> bool:
        """ Equal to. """
        if self.__class__ is other.__class__:
            return self.value == other.value
        try:
            return self.value == other.value
        except Exception:
            pass
        try:
            if isinstance(other, numbers.Real):
                return self.value == other
            if isinstance(other, str):
                return self.name == other
        except Exception:
            pass
        return NotImplemented


class IntegrationType(BaseEnum):
    guild = 0
    user = 1


class DefaultAvatarType(BaseEnum):
    blurple = 0
    grey = 1
    gray = 1
    green = 2
    orange = 3
    red = 4
    pink = 5


class InviteType(BaseEnum):
    guild = 0
    group = 1
    dm = 2
    unknown = 3


class ApplicationCommandType(BaseEnum):
    chat_input = 1
    user = 2
    message = 3


class ReactionType(BaseEnum):
    normal = 0
    burst = 1


class DefaultNotificationLevel(BaseEnum):
    all_messages = 0
    only_mentions = 1


class MFALevel(BaseEnum):
    none = 0
    elevated = 1


class MessageType(BaseEnum):
    default = 0
    recipient_add = 1
    recipient_remove = 2
    call = 3
    channel_name_change = 4
    channel_icon_change = 5
    channel_pinned_message = 6
    user_join = 7
    guild_boost = 8
    guild_boost_tier_1 = 9
    guild_boost_tier_2 = 10
    guild_boost_tier_3 = 11
    channel_follow_add = 12
    guild_discovery_disqualified = 14
    guild_discovery_requalified = 15
    guild_discovery_grace_period_initial_warning = 16
    guild_discovery_grace_period_final_warning = 17
    thread_created = 18
    reply = 19
    chat_input_command = 20
    thread_starter_message = 21
    guild_invite_reminder = 22
    context_menu_command = 23
    auto_moderation_action = 24
    role_subscription_purchase = 25
    interaction_premium_upsell = 26
    stage_start = 27
    stage_end = 28
    stage_speaker = 29
    stage_topic = 31
    guild_application_premium_subscription = 32
    premium_referal = 35
    guild_incident_alert_mode_enabled = 36
    guild_incident_alert_mode_disabled = 37
    guild_incident_report_raid = 38
    guild_incident_report_false_alarm = 39
    guild_deadchat_revive_prompt = 40
    custom_gift = 41
    guild_gaming_stats_prompt = 42
    purchase_notification = 44
    poll_result = 46
    changelog = 47
    nitro_notification = 48
    channel_linked_to_lobby = 49
    gifting_prompt = 50
    in_game_message_nux = 51
    guild_join_request_accept_notification = 52
    guild_join_request_reject_notification = 53
    guild_join_request_withdrawn_notification = 54
    hd_streaming_upgraded = 55
    report_to_mod_deleted_message = 58
    report_to_mod_timeout_user = 59
    report_to_mod_kick_user = 60
    report_to_mod_ban_user = 61
    report_to_mod_closed_report = 62
    emoji_added = 63


class MessageReferenceType(BaseEnum):
    default = 0
    forward = 1


class ContentFilterLevel(BaseEnum):
    disabled = 0
    members_without_roles = 1
    all_members = 2


class AuditLogType(BaseEnum):
    # Unknown value is only here because Discord
    # might add new audit log without documenting it
    unknown = -1

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
    auto_moderation_quarantine_user = 146
    creator_monetization_request_created = 150
    creator_monetization_terms_accepted = 151
    onboarding_prompt_create = 163
    onboarding_prompt_update = 164
    onboarding_prompt_delete = 165
    onboarding_create = 166
    onboarding_update = 167
    home_settings_create = 190
    home_settings_update = 191
    voice_channel_status_create = 192
    voice_channel_status_delete = 193
    guild_scheduled_event_exception_create = 200
    guild_scheduled_event_exception_update = 201
    guild_scheduled_event_exception_delete = 202

    @property
    def target_type(self) -> str | None:
        """ The type of the target of the audit log entry. """
        category_map: dict[int, str] = {
            -1: "all",
            73: "channel"
        }

        range_map: list[tuple[int, int, str]] = [
            (0, 9, "guild"),
            (10, 19, "channel"),
            (20, 29, "user"),
            (30, 39, "role"),
            (40, 49, "invite"),
            (50, 59, "webhook"),
            (60, 69, "emoji"),
            (70, 79, "message"),
            (80, 82, "integration"),
            (83, 89, "stage_instance"),
            (90, 92, "sticker"),
            (93, 102, "guild_scheduled_event"),
            (103, 112, "thread"),
            (113, 121, "integration_or_app_command"),
            (140, 142, "auto_moderation"),
            (143, 145, "user"),
            (146, 151, "creator_monetization")
        ]

        if self.value in category_map:
            return category_map[self.value]

        return next((
            category
            for start, end, category in range_map
            if start <= self.value <= end
        ), None)


class Locale(BaseEnum):
    american_english = "en-US"
    british_english = "en-GB"
    bulgarian = "bg"
    chinese = "zh-CN"
    taiwan_chinese = "zh-TW"
    croatian = "hr"
    czech = "cs"
    indonesian = "id"
    danish = "da"
    dutch = "nl"
    finnish = "fi"
    french = "fr"
    german = "de"
    greek = "el"
    hindi = "hi"
    hungarian = "hu"
    italian = "it"
    japanese = "ja"
    korean = "ko"
    latin_american_spanish = "es-419"
    lithuanian = "lt"
    norwegian = "no"
    polish = "pl"
    brazil_portuguese = "pt-BR"
    romanian = "ro"
    russian = "ru"
    spain_spanish = "es-ES"
    swedish = "sv-SE"
    thai = "th"
    turkish = "tr"
    ukrainian = "uk"
    vietnamese = "vi"


class ScheduledEventEntityType(BaseEnum):
    stage_instance = 1
    voice = 2
    external = 3


class ScheduledEventStatusType(BaseEnum):
    scheduled = 1
    active = 2
    completed = 3
    canceled = 4


class VerificationLevel(BaseEnum):
    none = 0
    low = 1
    medium = 2
    high = 3
    very_high = 4


class ExpireBehaviour(BaseEnum):
    remove_role = 0
    kick = 1


class ChannelType(BaseEnum):
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
    guild_media = 16


class CommandOptionType(BaseEnum):
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


class WebhookType(BaseEnum):
    incoming = 1
    channel_follower = 2
    application = 3


class ResponseType(BaseEnum):
    pong = 1
    channel_message_with_source = 4
    deferred_channel_message_with_source = 5
    deferred_update_message = 6
    update_message = 7
    application_command_autocomplete_result = 8
    modal = 9
    premium_required = 10
    launch_activity = 12


class VideoQualityType(BaseEnum):
    auto = 1
    full = 2


class ForumLayoutType(BaseEnum):
    not_set = 0
    list_view = 1
    gallery_view = 2


class SortOrderType(BaseEnum):
    latest_activity = 0
    creation_date = 1


class EntitlementType(BaseEnum):
    purchase = 1
    premium_subscription = 2
    developer_gift = 3
    test_mode_purchase = 4
    free_purchase = 5
    user_gift = 6
    premium_purchase = 7
    application_subscription = 8
    free_staff_purchase = 9
    quest_reward = 10
    fractional_redemption = 11
    virtual_currency_redemption = 12
    guild_powerup = 13


class AutoModRuleTriggerType(BaseEnum):
    keyword = 1
    harmful_link = 2
    spam = 3
    keyword_preset = 4
    mention_spam = 5
    member_profile = 6


class AutoModRuleEventType(BaseEnum):
    message_send = 1
    member_update = 2


class AutoModRuleActionType(BaseEnum):
    block_message = 1
    send_alert_message = 2
    timeout = 3
    block_member_interactions = 4


class AutoModRulePresetType(BaseEnum):
    profanity = 1
    sexual_content = 2
    slurs = 3


class EntitlementOwnerType(BaseEnum):
    guild = 1
    user = 2


class SKUType(BaseEnum):
    durable = 2
    consumable = 3
    subscription = 5
    subscription_group = 6


class InteractionType(BaseEnum):
    ping = 1
    application_command = 2
    message_component = 3
    application_command_autocomplete = 4
    modal_submit = 5


class StickerType(BaseEnum):
    standard = 1
    guild = 2


class StickerFormatType(BaseEnum):
    png = 1
    apng = 2
    lottie = 3
    gif = 4


class ComponentType(BaseEnum):
    action_row = 1

    # Components v1
    button = 2
    string_select = 3
    text_input = 4
    user_select = 5
    role_select = 6
    mentionable_select = 7
    channel_select = 8

    # Components v2
    section = 9
    text_display = 10
    thumbnail = 11
    media_gallery = 12
    file = 13
    separator = 14
    content_inventory_entry = 16  # Can't be used by bots
    container = 17
    label = 18


class SeparatorSpacingType(BaseEnum):
    small = 1
    large = 2


class ButtonStyles(BaseEnum):
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


class TextStyles(BaseEnum):
    short = 1
    paragraph = 2


class PermissionType(BaseEnum):
    role = 0
    member = 1


class PrivacyLevelType(BaseEnum):
    public = 1
    guild_only = 2
