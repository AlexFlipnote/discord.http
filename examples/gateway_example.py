from discord_http import Context, Client, Message, PartialMessage
from discord_http.gateway import Intents

client = Client(
    token="BOT_TOKEN",
    sync=True,
    enable_gateway=True,
    intents=(
        Intents.guild_messages |
        Intents.direct_messages
    )
)


@client.command()
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")


@client.listener()
async def on_message_create(msg: Message):
    print(f"{msg.author} made a new message in {msg.channel}")


@client.listener()
async def on_message_update(msg: Message):
    print(f"{msg.author} updated a message in {msg.channel}")


@client.listener()
async def on_message_delete(msg: PartialMessage):
    print(f"Message deleted: {msg}")


client.start(host="127.0.0.1", port=8080)
