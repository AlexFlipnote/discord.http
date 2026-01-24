from discord_http import Context, Client, View, Button, NotFound, ActionRow

client = Client(
    token="BOT_TOKEN",
    sync=True
)


@client.command()
async def confirm(ctx: Context):
    """ Prompt to be 100% sure """
    view = View(
        ActionRow(
            Button(label="Yes", custom_id="yes", style="green"),
            Button(label="No", custom_id="no", style="red")
        )
    )

    async def call_after():
        choice = await view.wait(ctx, call_after=view_callback, timeout=10)
        if not choice:
            try:
                msg = await ctx.original_response()
            except NotFound:
                return None  # message was deleted

            await msg.edit(
                content="You took too long to respond!",
                view=None
            )

    async def view_callback(ctx: Context):
        """
        Callback for the view
        Since it's a new interaction, the callback produces a new context
        Which is why we have a new ctx inside this function
        """
        match ctx.custom_id:
            case "yes":
                output = "Glad you are 100% sure!"

            case "no":
                output = "Oh no, maybe try again later?"

            case _:
                output = "should never get here, otherwise something's really wrong"

        return ctx.response.edit_message(content=output, view=None)

    return ctx.response.send_message(
        "Hey, are you 100% sure that you are sure?",
        view=view, call_after=call_after
    )


client.start(host="127.0.0.1", port=8080)
