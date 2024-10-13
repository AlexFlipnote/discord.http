from typing import Literal, NotRequired, TypedDict
from .snowflake import Snowflake, SnowflakeList

# fmt: off
EventType = Literal[
    1,  # MESSAGE_SEND
    2,  # MEMBER_UPDATE
]
KeywordPresetType = Literal[
    1,  # PROVANITY
    2,  # SEXUAL_CONTENT
    3,  # SLUTS
]
TriggerType = Literal[
    1,  # KEYWORD
    3,  # SPAM
    4,  # KEYWORD_PRESET
    5,  # MENTION_SPAM
    6,  # MEMBER_PROFILE
]
ActionType = Literal[
    1,  # BLOCK_MESSAGE
    2,  # SEND_ALERT_MESSAGE
    3,  # TIMEOUT
    4,  # BLOCK_MEMBER_INTERACTION
]
# fmt: on

class SendAlertMessageActionMetdata(TypedDict):
    channel_id: Snowflake

class TimeoutActionMetdata(TypedDict):
    duration_seconds: int

class BlockMessageActionMetdata(TypedDict):
    custom_message: NotRequired[str]

class AutoModerationAction(TypedDict):
    type: ActionType

class AutoModerationActionWithSendAlertMetadata(AutoModerationAction):
    type: Literal[2]
    metadata: SendAlertMessageActionMetdata

class AutoModerationActionWithSendAlertMessageMetadata(AutoModerationAction):
    type: Literal[3]
    metadata: TimeoutActionMetdata

class AutoModerationActionWithBlockMessageMetadata(TypedDict):
    type: Literal[4]
    metadata: BlockMessageActionMetdata


_AutoModerationAction = (
    AutoModerationAction
    | AutoModerationActionWithSendAlertMetadata
    | AutoModerationActionWithSendAlertMessageMetadata
    | AutoModerationActionWithBlockMessageMetadata
)


class KeywordTriggerMetadata(TypedDict):
    keyword_filter: list[str]
    regex_patterns: list[str]


class KeywordPresetTriggerMetadata(TypedDict):
    presets: list[KeywordPresetType]
    allow_list: list[str]


class MemberProfileTriggerMetadata(KeywordTriggerMetadata):
    allow_list: list[str]

class MentionSpamTriggerMetadata(TypedDict):
    nention_total_limit: int
    mention_raid_protection_enabled: bool

AutoModerationRuleTriggerMetadata = (
    KeywordTriggerMetadata
    | KeywordPresetTriggerMetadata
    | MemberProfileTriggerMetadata
    | MentionSpamTriggerMetadata
)

class AutoModerationRule(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    name: str
    creator_id: Snowflake
    event_type: EventType
    trigger_type: TriggerType
    trigger_metadata: AutoModerationRuleTriggerMetadata
    actions: _AutoModerationAction
    enabled: bool
    exempt_roles: SnowflakeList
    exempt_channels: SnowflakeList

class AutoModerationRuleWithKeywordTriggerMetadata(AutoModerationRule):
    event_type: Literal[1]
    trigger_metadata: KeywordTriggerMetadata

class AutoModerationRuleWithKeywordPresetriggerMetadata(AutoModerationRule):
    event_type: Literal[4]
    trigger_metadata: KeywordPresetTriggerMetadata

class AutoModerationRuleWithMentionSpamTriggerMetadata(AutoModerationRule):
    event_type: Literal[5]
    trigger_metadata: MentionSpamTriggerMetadata

class AutoModerationRuleWithMemberProfileTriggerMetadata(AutoModerationRule):
    event_type: Literal[6]
    trigger_metadata: MemberProfileTriggerMetadata

