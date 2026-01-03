from discord_http import commands, Client, Context

# This is only for type hinting without causing circular imports
# Again, this is optional, remove it if you don't want it
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..cog_example import CustomClient

class Ping(commands.Cog):
    pong = commands.SubGroup(name="pong")

    def __init__(self, bot):
        self.bot: "CustomClient" = bot

    @commands.command()
    async def ping(self, ctx: Context):
        """ Ping command """
        return ctx.response.send_message(
            # Accessing the hello_world attribute from the bot/client
            # If you kept the example as-is, this will work
            self.bot.hello_world
        )

    @pong.command(name="ping")
    async def ping2(self, ctx: Context):
        """ Ping command, but subcommand """
        return ctx.response.send_message(
            "pong, but from subcommand"
        )

    @pong.command(name="autocomplete")
    async def ping3(self, ctx: Context, test: str):
        """ Ping command, but subcommand of subcommand with autocomplete """
        return ctx.response.send_message(str(test))

    @ping3.autocomplete(name="test")
    async def ping3_autocomplete(self, ctx: Context, current: str):
        nice_list = {
            "option1": "Hello",
            "option2": "World"
        }

        return ctx.response.send_autocomplete({
            key: value for key, value in nice_list.items()
            if current.lower() in value.lower()
        })


async def setup(bot: Client):
    await bot.add_cog(Ping(bot))
