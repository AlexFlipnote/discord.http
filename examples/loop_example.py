from discord_http import Client, tasks

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


@tasks.loop(seconds=5)
async def test_loop():
    print("Hi there, I will run every 5 seconds!")


client.start(host="127.0.0.1", port=8080)
