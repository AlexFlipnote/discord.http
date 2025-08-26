from discord_http import Context, Client, Modal, TextInputComponent

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


@client.command()
async def submit(ctx: Context):
    """ Create a button """
    modal = Modal(
        title="Submit request",
        custom_id="submit_request"
    )

    modal.add_item(TextInputComponent(
        label="Your input",
        custom_id="user_input"
    ))

    return ctx.response.send_modal(modal)


@client.interaction("submit_request")
async def button_interaction(ctx: Context):
    response = ctx.modal_values["user_input"]
    return ctx.response.send_message(
        f"You submitted: {response}"
    )


client.start(host="127.0.0.1", port=8080)
