![discord.http](https://raw.githubusercontent.com/AlexFlipnote/discord.http/master/.github/branding/banner.png)

A Python library for Discord bots using HTTP interactions, with optional WebSocket support and full cache control.

- Lightweight and memory efficient, built to stay small even in large bots
- HTTP-first, with the gateway available when you actually need events
- Respects your cache level, nothing is stored unless you ask for it
- Act on anything by ID without fetching it first
- Minimal dependency footprint, only what is truly needed
- Supports both guild install and user install bots
- Fully type-hinted and kept in sync with the Discord API

## Why discord.http?
Most bots only answer slash commands, which does not need a connection to Discord running around the clock. discord.http starts from HTTP interactions, so your bot only works when someone uses it. Need events? Turn on the gateway and choose exactly what gets cached. Whatever you do cache is stored as compactly as possible, so even bots in thousands of servers stay lean.

Coming from [discord.py](https://github.com/Rapptz/discord.py)? The API will feel familiar, so there is little to relearn. (Trust me, I made the jump myself with a 30,000+ line bot, the last thing I wanted was to rewrite everything...)

### Blueprints, not hand-holding
You stay in control, instead of fighting the library. Arguments and attributes use plain Python types like `str`, `int` and `datetime`, with builders only where an argument is genuinely complex, like embeds or components. No forced abstractions and no opinions on how your bot should be structured, just the building blocks.

> [!NOTE]
> discord.http does not support voice connections as of now, it may come but, demand is low for now.

## Requirements & Installing
- Python 3.11 or newer
- A public HTTPS endpoint for Discord to send interactions to, usually a reverse proxy (nginx, apache2, etc.) in front of your bot

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

Want to also listen to gateway events? Pass `enable_gateway=True` to the client along with your desired `intents`.

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
