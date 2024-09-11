import os

from discord_http import Client


class CustomClient(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config: dict = {"hello": True}

    async def setup_hook(self):
        for file in os.listdir("./cogs"):
            if not file.endswith(".py"):
                continue
            await self.load_extension(f"cogs.{file[:-3]}")


client = CustomClient(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)

client.start(host="127.0.0.1", port=8080)
