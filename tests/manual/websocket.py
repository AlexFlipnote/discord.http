import json

from discord_http.gateway import (
    Intents, GatewayCacheFlags, Reaction,
    BulkDeletePayload, AutomodExecution, PollVoteEvent,
    PlayingStatus
)
from discord_http import (
    Client, Message, Member, User,
    PartialGuild, Role, PartialRole, PartialMessage, VoiceState,
    AuditLogEntry, PartialChannel, ScheduledEvent, PartialScheduledEvent,
    AutoModRule, Guild
)


with open("./config.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    debug_events=config["debug_events"],
    guild_id=config.get("guild_id", None),
    enable_gateway=True,
    playing_status=PlayingStatus(
        name="Testing status",
        status="dnd"
    ),
    gateway_cache=(
        GatewayCacheFlags.guilds |
        GatewayCacheFlags.members |
        GatewayCacheFlags.roles |
        GatewayCacheFlags.channels |
        GatewayCacheFlags.voice_states |
        GatewayCacheFlags.presences
    ),
    intents=Intents.all(),
)


@client.listener()
async def on_guild_create(guild: Guild):
    print(f"Guild created: {guild}")


@client.listener()
async def on_message_create(msg: Message):
    print(f"Message: {msg.content}")

    if msg.content == "test:wait_for":
        msg2 = await client.wait_for(
            "message_create",
            check=lambda m: m.author.id == msg.author.id and m.content == "a",
            timeout=10
        )

        print(f"Successful wait: {msg2}")


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
async def on_guild_scheduled_event_create(event: ScheduledEvent):
    print(f"Event: {event}")


@client.listener()
async def on_guild_scheduled_event_update(event: ScheduledEvent):
    print(f"Event: {event}")


@client.listener()
async def on_guild_scheduled_event_delete(event: ScheduledEvent):
    print(f"Event: {event}")


@client.listener()
async def on_guild_scheduled_event_user_add(event: PartialScheduledEvent, user: Member):
    print(f"User added to {event}: {user}")


@client.listener()
async def on_guild_scheduled_event_user_remove(event: PartialScheduledEvent, user: Member):
    print(f"User removed from {event}: {user}")


@client.listener()
async def on_auto_moderation_rule_create(rule: AutoModRule):
    print(f"Rule created: {rule}")


@client.listener()
async def on_auto_moderation_rule_update(rule: AutoModRule):
    print(f"Rule updated: {rule}")


@client.listener()
async def on_auto_moderation_rule_delete(rule: AutoModRule):
    print(f"Rule deleted: {rule}")


@client.listener()
async def on_auto_moderation_action_execution(execution: AutomodExecution):
    print(f"Execution on {execution.user}: {execution}")


@client.listener()
async def on_message_poll_vote_add(vote: PollVoteEvent):
    print(f"Vote added: {vote}")


@client.listener()
async def on_message_poll_vote_remove(vote: PollVoteEvent):
    print(f"Vote removed: {vote}")


@client.listener()
async def on_webhooks_update(channel: PartialChannel):
    print(channel)


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


@client.listener()
async def on_guild_audit_log_entry_create(entry: AuditLogEntry):
    print(f"Audit log entry created: {entry}")


client.start(host="0.0.0.0", port=8080)
