![discord.http](https://raw.githubusercontent.com/AlexFlipnote/discord.http/master/.github/branding/banner.png)

A Python library for Discord bots using HTTP interactions, with optional WebSocket support and full cache control.

- Runs over HTTP, the gateway or both, the library detects which on boot.
- Nothing is cached unless you ask for it, and what is cached is stored compactly, even in thousands of servers.
- Act on anything by ID without fetching it first.
- Offline mode for scripts and cron jobs, use the API without running a bot at all.
- Plain Python types like `str`, `int` and `datetime`, with builders only where it is genuinely complex, like embeds or components.
- Supports guild and user installs, fully type-hinted and kept in sync with the Discord API.
- Small, deliberate dependency set, every dependency has to earn its place.
- Familiar API for anyone coming from [discord.py](https://github.com/Rapptz/discord.py), so there is little to relearn.

## Is it the right fit?
discord.http is built for bots that mostly answer slash commands, and that care about what they cost to run as they grow. Replies are sent back on the same HTTP request the command arrived on, so the first reply to a command does not even cost an API call. Small bots work just as well, the savings simply add up the more servers you are in.

It is probably not the right pick if you need voice connections (not supported for now, demand is low).

## Requirements
- Python 3.11 to 3.14
- A public HTTPS endpoint for Discord to send interactions to, usually a reverse proxy (nginx, apache2, etc.) in front of your bot

> [!NOTE]
> No HTTPS endpoint? Leave the Interactions Endpoint URL empty in your bot's application page and the library auto-detects it, running in websocket-only mode instead (like most other Discord libraries do). Pass `enable_gateway=True` to the client to make it intentional and remove the warning logs for it.

## Installing
Install with `pip install discord.http` (or `python -m pip install discord.http` if `pip` is not on your path).

> [!NOTE]
> Want to test the latest changes before the next release? Install the beta with `git+https://github.com/AlexFlipnote/discord.http@master` instead of `discord.http`. It can be unstable and unreliable, so use it at your own risk.

## Quick example
```py <!-- DOCS: quick_example -->
from discord_http import Context, Client

client = Client(
    token="Your bot token here"
)

@client.command()
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")

client.start()
```

### With the gateway
Want to also listen to gateway events? Pass `enable_gateway=True` to the client along with your desired `intents`.

```py <!-- DOCS: gateway_example -->
from discord_http import Client, Message
from discord_http.gateway import Intents

client = Client(
    token="Your bot token here",
    enable_gateway=True,
    intents=Intents.guild_messages
)

@client.listener()
async def on_message_create(msg: Message):
    print(f"{msg.author} sent a message in {msg.channel}")

client.start()
```

### Offline mode
Not every job needs a running bot. `offline_run()` logs in, runs your function once and exits, with no HTTP server, no gateway connection and no public endpoint needed. Great for cron jobs, one-off scripts and admin tools.

```py <!-- DOCS: offline_example -->
from discord_http import Client

client = Client(
    token="Your bot token here"
)

async def main():
    channel = client.get_partial_channel(123456789012345678)
    await channel.send("Nightly backup finished!")

client.offline_run(main)
```

Need further help on how to make Discord API able to send requests to your bot?
Check out [the documentation](https://discordhttp.alexflipnote.dev/pages/getting_started.html) for more detailed information.

## Contributing
Contributions are welcome! Have a look at the [contributing guide](https://discordhttp.alexflipnote.dev/pages/contribute.html) and the [style guide](https://discordhttp.alexflipnote.dev/pages/format.html) before opening a pull request.

Automated tests use Python's built-in `unittest` module, run them from the project root with:
- `make test`
- or `python -m unittest discover -s tests -p "test_*.py"`

## Resources
- Documentations
  - [Library documentation](https://discordhttp.alexflipnote.dev)
  - [Discord API documentation](https://docs.discord.com/developers/intro)
- [Discord server](https://discord.gg/yqb7vATbjH)
- [discord.http Bot example](https://github.com/AlexFlipnote/discord_bot.http)
