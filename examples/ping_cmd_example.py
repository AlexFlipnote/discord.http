from discord_http import Context, Client

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


@client.command()
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")


client.start(host="127.0.0.1", port=8080)
