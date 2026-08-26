from typing import cast

from ..flags import BaseFlag

__all__ = (
    "ActivityFlags",
    "GatewayCacheFlags",
    "GatewayCapabilities",
    "Intents",
)


class ActivityFlags(BaseFlag):
    """ Represents the flags of a gateway presence activity. """
    __slots__ = ()

    instance = cast("ActivityFlags", 1 << 0)
    join = cast("ActivityFlags", 1 << 1)
    spectate = cast("ActivityFlags", 1 << 2)
    join_request = cast("ActivityFlags", 1 << 3)
    sync = cast("ActivityFlags", 1 << 4)
    play = cast("ActivityFlags", 1 << 5)
    party_privacy_friends = cast("ActivityFlags", 1 << 6)
    party_privacy_voice_channel = cast("ActivityFlags", 1 << 7)
    embedded = cast("ActivityFlags", 1 << 8)


class Intents(BaseFlag):
    """ Represents the gateway intents for the bot. """
    __slots__ = ()

    guilds = cast("Intents", 1 << 0)
    guild_members = cast("Intents", 1 << 1)
    guild_moderation = cast("Intents", 1 << 2)
    guild_expressions = cast("Intents", 1 << 3)
    guild_integrations = cast("Intents", 1 << 4)
    guild_webhooks = cast("Intents", 1 << 5)
    guild_invites = cast("Intents", 1 << 6)
    guild_voice_states = cast("Intents", 1 << 7)
    guild_presences = cast("Intents", 1 << 8)
    guild_messages = cast("Intents", 1 << 9)
    guild_message_reactions = cast("Intents", 1 << 10)
    guild_message_typing = cast("Intents", 1 << 11)
    direct_messages = cast("Intents", 1 << 12)
    direct_message_reactions = cast("Intents", 1 << 13)
    direct_message_typing = cast("Intents", 1 << 14)
    message_content = cast("Intents", 1 << 15)
    guild_scheduled_events = cast("Intents", 1 << 16)
    auto_moderation_configuration = cast("Intents", 1 << 20)
    auto_moderation_execution = cast("Intents", 1 << 21)
    guild_message_polls = cast("Intents", 1 << 24)
    direct_message_polls = cast("Intents", 1 << 25)


class GatewayCapabilities(BaseFlag):
    """ Represents the opt-in capabilities bitfield sent in the Gateway Identify payload. """
    __slots__ = ()

    private_channel_obfuscation = cast("GatewayCapabilities", 1 << 15)


class GatewayCacheFlags(BaseFlag):
    """ Represents what the gateway should cache. """
    __slots__ = ()

    partial_guilds = cast("GatewayCacheFlags", 1 << 0)
    partial_members = cast("GatewayCacheFlags", 1 << 1)
    partial_channels = cast("GatewayCacheFlags", 1 << 2)
    partial_threads = cast("GatewayCacheFlags", 1 << 3)
    partial_roles = cast("GatewayCacheFlags", 1 << 4)
    partial_emojis = cast("GatewayCacheFlags", 1 << 5)
    partial_stickers = cast("GatewayCacheFlags", 1 << 6)
    partial_voice_states = cast("GatewayCacheFlags", 1 << 7)
    guilds = cast("GatewayCacheFlags", 1 << 50)
    members = cast("GatewayCacheFlags", 1 << 51)
    channels = cast("GatewayCacheFlags", 1 << 52)
    threads = cast("GatewayCacheFlags", 1 << 53)
    roles = cast("GatewayCacheFlags", 1 << 54)
    emojis = cast("GatewayCacheFlags", 1 << 55)
    stickers = cast("GatewayCacheFlags", 1 << 56)
    voice_states = cast("GatewayCacheFlags", 1 << 57)
    presences = cast("GatewayCacheFlags", 1 << 100)
