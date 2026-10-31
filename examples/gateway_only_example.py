from discord_http import Context, Client, Message, User
from discord_http.gateway import Intents, Reaction

# Runs on the gateway alone, no HTTP server or public endpoint needed.
# Leave the Interactions Endpoint URL empty in your app's settings,
# otherwise Discord keeps sending interactions there instead of the gateway.
client = Client(
    token="BOT_TOKEN",
    disable_http_server=True,
    intents=(
        Intents.guild_messages |
        Intents.guild_message_reactions |
        Intents.direct_messages
    )
)


@client.listener()
async def on_ready(user: User):
    print(f"Logged in as {user}, running on the gateway only")


@client.command()
async def ping(ctx: Context):
    """ A simple ping command, received over the gateway """
    return ctx.response.send_message("Pong!")


@client.listener()
async def on_message_create(msg: Message):
    # msg.content is empty in guilds without Intents.message_content (privileged),
    # except for DMs and messages that mention the bot
    if msg.author.bot:
        return

    if any(u.id == client.user.id for u in msg.mentions):
        await msg.add_reaction("👋")


@client.listener()
async def on_message_reaction_add(reaction: Reaction):
    print(f"User {reaction.user_id} reacted with {reaction.emoji} on message {reaction.message_id}")


# No host or port, there is no HTTP server to bind
client.start()
