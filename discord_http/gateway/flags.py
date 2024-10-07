from ..flags import BaseFlag

__all__ = (
    "GatewayCacheFlags",
    "Intents",
    "ActivityFlags",
)


class ActivityFlags(BaseFlag):
    instance = 1 << 0
    join = 1 << 1
    spectate = 1 << 2
    join_request = 1 << 3
    sync = 1 << 4
    play = 1 << 5
    party_privacy_friends = 1 << 6
    party_privacy_voice_channel = 1 << 7
    embedded = 1 << 8


class Intents(BaseFlag):
    guilds = 1 << 0
    guild_members = 1 << 1
    guild_moderation = 1 << 2
    guild_expressions = 1 << 3
    guild_integrations = 1 << 4
    guild_webhooks = 1 << 5
    guild_invites = 1 << 6
    guild_voice_states = 1 << 7
    guild_presences = 1 << 8
    guild_messages = 1 << 9
    guild_message_reactions = 1 << 10
    guild_message_typing = 1 << 11
    direct_messages = 1 << 12
    direct_message_reactions = 1 << 13
    direct_message_typing = 1 << 14
    message_content = 1 << 15
    guild_scheduled_events = 1 << 16
    auto_moderation_configuration = 1 << 20
    auto_moderation_execution = 1 << 21
    guild_message_polls = 1 << 24
    direct_message_polls = 1 << 25


class GatewayCacheFlags(BaseFlag):
    partial_guilds = 1 << 0
    partial_members = 1 << 1
    partial_channels = 1 << 2
    partial_threads = 1 << 3
    partial_roles = 1 << 4
    partial_emojis = 1 << 5
    partial_stickers = 1 << 6
    partial_voice_states = 1 << 7
    guilds = 1 << 50
    members = 1 << 51
    channels = 1 << 52
    threads = 1 << 53
    roles = 1 << 54
    emojis = 1 << 55
    stickers = 1 << 56
    voice_states = 1 << 57
    presences = 1 << 100
