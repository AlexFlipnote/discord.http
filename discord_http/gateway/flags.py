from ..flags import BaseFlag

__all__ = (
    "GatewayCacheFlags",
    "Intents",
)


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
    guilds = 1 << 10
    members = 1 << 11
    channels = 1 << 12
    threads = 1 << 13
    roles = 1 << 14
    emojis = 1 << 15
    stickers = 1 << 16
    voice_states = 1 << 17
