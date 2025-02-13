from discord_http import Context, Client, Member, User, Message

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


# This will appear when you right click on a user
@client.user_command(name="test_user")
async def test_user(ctx: Context, user: Member | User):
    return ctx.response.send_message(
        f"You successfully targeted {user}",
        ephemeral=True
    )


# This will appear when you right click on a message
@client.message_command(name="test_message")
async def test_message(ctx: Context, message: Message):
    return ctx.response.send_message(
        f"> Message content\n{message.content}",
        ephemeral=True
    )


client.start(host="127.0.0.1", port=8080)
