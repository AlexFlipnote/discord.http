from discord_http import Client, Context

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


@client.command()
async def search(ctx: Context, query: str):
    """ Search for something (totally not ignored) """
    return ctx.response.send_message(
        f"Your search for `{query}` was not found :(",
        ephemeral=True
    )


@search.autocomplete("query")
async def search_autocomplete(ctx: Context, current: str):
    print(f"Currently in the search query: {current}")
    top_result = current or "..."

    return ctx.response.send_autocomplete({
        top_result: top_result,
        "feeling_lucky_tm": "I'm feeling lucky!"
    })


client.start(host="127.0.0.1", port=8080)
