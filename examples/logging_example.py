# discord.http provides a nice logging tool to help you debug your bot.
# If you want to use the same format, this is how you can set it up.
import logging

from discord_http import Context, Client

client = Client(
    token="BOT_TOKEN"
)

# Logging has to be set up after the client is created
# Since Client.__init__ sets up the logger
_log = logging.getLogger("discord_http")


@client.command()
async def hello(ctx: Context):
    """ A simple ping command """
    _log.info(f"{ctx.user} said hello!")
    return ctx.response.send_message("Hi there!")


client.start(host="127.0.0.1", port=8080)
