# An example of how you can use discord.http to simply do API requests only
# Instead of having a bot online
import asyncio

from discord_http import Client

client = Client(token="BOT_TOKEN")


async def main():
    user = await client.fetch_user(86477779717066752)
    print(repr(user))


asyncio.run(main())
