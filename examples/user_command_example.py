from discord_http import Context, Client, commands

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


@client.command(user_install=True)
@commands.allow_contexts(
    guild=True,  # Allow this command in guilds
    bot_dm=False,  # Disallow this command in bot DMs
    private_dm=True  # Allow this command in private DMs
)
# You can also use @commands.guild_only() too, which translates to:
# @commands.allow_contexts(guild=True, bot_dm=False, private_dm=False)
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")


client.start(host="127.0.0.1", port=8080)
