![discord.http](https://raw.githubusercontent.com/AlexFlipnote/discord.http/master/.github/branding/banner.png)

A Python library for Discord bots using HTTP interactions, with optional WebSocket support and full cache control.

- Lightweight and fully customisable, no bloat or forced abstractions
- HTTP-first with optional WebSocket support when you need it
- Full cache control, you decide what gets stored and what does not
- Barebone and developer-first, designed to get out of your way
- Supports both guild install and user install bot types

The API is designed to feel familiar if you are coming from [discord.py](https://github.com/Rapptz/discord.py), so switching between the two should not require much relearning.

## Requirements & Installing
- Python 3.11 or newer
- A web server to receive HTTP requests from Discord (nginx, Apache, etc.)

Install by using `pip install discord.http` in the terminal.
If `pip` does not work, there are other ways to install as well, most commonly:
- `python -m pip install discord.http`
- `python3 -m pip install discord.http`
- `pip3 install discord.http`

### Installing beta
Do you live on the edge and want to test before the next version is released?
You can install it by using `git+https://github.com/AlexFlipnote/discord.http@master` instead of `discord.http` when running `pip install`.

> [!NOTE]
> It can be unstable and unreliable, so use it at your own risk.

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

## Running tests
Automated tests use Python's built-in `unittest` module.

Run all tests from the project root:
- `make test`
- or `python -m unittest discover -s tests -p "test_*.py"`

## Resources
- Documentations
  - [Library documentation](https://discordhttp.alexflipnote.dev)
  - [Discord API documentation](https://discord.com/developers/docs/intro)
- [Discord server](https://discord.gg/yqb7vATbjH)
- [discord.http Bot example](https://github.com/AlexFlipnote/discord_bot.http)
