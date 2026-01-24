from discord_http import Context, Client, View, Button, ActionRow

client = Client(
    token="BOT_TOKEN",
    sync=True
)


@client.command()
async def button_test(ctx: Context):
    """ A simple ping command """
    view = View(
        ActionRow(
            Button(
                label="Click me",
                style="green",
                custom_id=f"user:{ctx.user.id}"
            )
        )
    )

    return ctx.response.send_message(
        "This is a nice button",
        view=view
    )


@client.interaction(r"^user:", regex=True)
async def button_test_interaction(ctx: Context):
    """
    RegEx interactions

    This allows you to partially match the custom_id
    Useful for when you want any Custom ID that matches the beginning, but has different endings
    """
    user_id = ctx.custom_id.split(":")[-1]
    return ctx.response.edit_message(
        content=f"{ctx.user} pressed the button made by {user_id}"
    )


client.start(host="127.0.0.1", port=8080)
