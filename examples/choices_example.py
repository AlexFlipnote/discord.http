from discord_http import Context, Client, commands

client = Client(
    token="BOT_TOKEN",
    sync=True
)


@client.command()
@commands.choices(
    choice={
        "hello": "Hello there!",
        "goodbye": "Goodbye!"
    }
)
async def choices_str(ctx: Context, choice: commands.Choice[str]):
    return ctx.response.send_message(
        f"You chose **{choice.value}** which has key value: **{choice.key}**"
    )


@client.command()
@commands.choices(
    choice={
        23: "Nice",
        55: "meme"
    }
)
async def choices_int(ctx: Context, choice: commands.Choice[int]):
    return ctx.response.send_message(
        f"You chose **{choice.value}** ({type(choice.value)}) "
        f"which has key value: **{choice.key}** ({type(choice.key)})"
    )


client.start(host="127.0.0.1", port=8080)
