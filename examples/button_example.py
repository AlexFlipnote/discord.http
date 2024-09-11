from discord_http import Context, Client, View, Button

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


def lovely_button(disabled: bool = False) -> View:
    return View(
        Button(
            label="Click me!",
            custom_id="button_click",
            disabled=disabled
        )
    )


@client.command()
async def button(ctx: Context):
    """ Create a button """
    return ctx.response.send_message(
        "Hey there, click this fancy button",
        view=lovely_button()
    )


@client.interaction("button_click")
async def button_interaction(ctx: Context):
    return ctx.response.edit_message(
        content="You clicked the button!",
        view=lovely_button(disabled=True)
    )


client.start(host="127.0.0.1", port=8080)
