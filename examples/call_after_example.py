import asyncio

from discord_http import Context, Client

client = Client(
    token="BOT_TOKEN",
    sync=True
)


@client.command()
async def followup_example(ctx: Context):
    """ My name jeff """
    async def call_after():
        await asyncio.sleep(3)
        await ctx.edit_original_response(
            content="Hey, I have entered the chat!"
        )

    return ctx.response.defer(thinking=True, call_after=call_after)


client.start(host="127.0.0.1", port=8080)
