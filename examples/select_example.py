from discord_http import Client, Context, View, Select, ActionRow


client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


def selection_menu(disabled: bool = False) -> View:
    select = Select(
        placeholder="Select a colour...",
        custom_id="select",
        disabled=disabled
    )

    select.add_item(label="Red", value="red")
    select.add_item(label="Green", value="green")
    select.add_item(label="Blue", value="blue")
    select.add_item(label="Yellow", value="yellow")

    return View(ActionRow(select))


@client.command()
async def select(ctx: Context):
    """ Create your favourite colour """
    return ctx.response.send_message(
        "Hey there, what's your favourite colour?",
        view=selection_menu()
    )


@client.interaction("select")
async def button_interaction(ctx: Context):
    return ctx.response.edit_message(
        content=(
            f"Your favourite colour is {ctx.select_values.strings[0]}?\n"
            "That's a nice colour!"
        ),
        view=selection_menu(disabled=True)
    )


client.start(host="127.0.0.1", port=8080)
