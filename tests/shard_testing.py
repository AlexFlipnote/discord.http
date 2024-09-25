import json

from discord_http.gateway import Intents, GatewayCacheFlags
from discord_http import (
    Client, Message, Reaction, Member, User, BulkDeletePayload,
    PartialGuild, Role, PartialRole, PartialMessage, VoiceState
)


with open("./config.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    application_id=config["application_id"],
    public_key=config["public_key"],
    debug_events=config["debug_events"],
    guild_id=config.get("guild_id", None),
    enable_gateway=True,
    gateway_cache=(
        GatewayCacheFlags.guilds |
        GatewayCacheFlags.members |
        GatewayCacheFlags.roles |
        GatewayCacheFlags.channels |
        GatewayCacheFlags.voice_states
    ),
    intents=(
        Intents.guilds |
        Intents.guild_members |
        Intents.guild_messages |
        Intents.direct_messages |
        Intents.message_content |
        Intents.guild_message_reactions |
        Intents.guild_voice_states
    ),
)


@client.listener()
async def on_message_create(msg: Message):
    print(f"Message: {msg.content}")


@client.listener()
async def on_message_delete(msg: PartialMessage):
    print(f"Message deleted: {msg}")


@client.listener()
async def on_message_delete_bulk(payload: BulkDeletePayload):
    print(f"Bulk delete: {payload.messages}")


@client.listener()
async def on_message_reaction_add(reaction: Reaction):
    print(f"Reaction: {reaction.emoji}")


@client.listener()
async def on_message_reaction_remove(reaction: Reaction):
    print(f"Reaction: {reaction.emoji}")


@client.listener()
async def on_guild_member_add(guild: PartialGuild, member: Member):
    print(f"Member joined {guild}: {member.name}")


@client.listener()
async def on_guild_member_remove(guild: PartialGuild, member: User):
    print(f"Member left {guild}: {member.name}")


@client.listener()
async def on_guild_member_update(guild: PartialGuild, member: Member):
    print(f"Member updated {guild}: {member.display_name}")


@client.listener()
async def on_guild_role_create(role: Role):
    print(f"Role created in {role.guild_id}: {role.name}")


@client.listener()
async def on_guild_role_update(role: Role):
    print(f"Role updated in {role.guild_id}: {role.name}")


@client.listener()
async def on_guild_role_delete(role: PartialRole):
    print(f"Role deleted in {role.guild_id}: {role}")


@client.listener()
async def on_voice_state_update(voice_state: VoiceState):
    print(f"Voice state updated: {voice_state.channel_id}")


client.start(host="0.0.0.0", port=8080)
