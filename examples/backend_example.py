from aiohttp import web
from discord_http import Client, Context

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


async def custom_test(_request: web.Request) -> web.Response:
    return web.json_response({
        "information": f"Logged in as {client.user}"
    })


@client.command()
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")


# This will create http://localhost:8080/test
# It also has to be added before the client starts
client.backend.router.add_get("/test", custom_test)

client.start(host="127.0.0.1", port=8080)
