import json

from discord_http import Client, Message
from discord_http.gateway import Intents, GatewayCacheFlags


with open("./config.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    application_id=config["application_id"],
    public_key=config["public_key"],
    debug_events=config["debug_events"],
    guild_id=config.get("guild_id", None),
    enable_gateway=True,
    gateway_cache=GatewayCacheFlags.guild,
    intents=(
        Intents.guilds |
        Intents.guild_members |
        Intents.guild_messages |
        Intents.direct_messages |
        Intents.message_content
    ),
)


"""@client.listener()
async def on_shard_ready(shard: Shard):
    print(f"Shard {shard.shard_id} is ready")


@client.listener()
async def on_guild_create(guild: Guild):
    print(f"Guild {guild.name} created")"""


@client.listener()
async def on_message_create(msg: Message):
    print(f"Message: {msg.content}")


client.start(host="0.0.0.0", port=8080)
