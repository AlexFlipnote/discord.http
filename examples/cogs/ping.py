from discord_http import commands, Client, Context


class Ping(commands.Cog):
    pong = commands.SubGroup(name="pong")

    def __init__(self, bot):
        self.bot: Client = bot

    @commands.command()
    async def ping(self, ctx: Context):
        """ Ping command """
        return ctx.response.send_message(
            "pong"
        )

    @pong.command(name="ping")
    async def ping2(self, ctx: Context):
        """ Ping command, but subcommand """
        return ctx.response.send_message(
            "pong, but from subcommand"
        )

    @pong.command(name="autocomplete")
    async def ping3(self, ctx: Context, test: str):
        """ Ping command, but subcommand """
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
