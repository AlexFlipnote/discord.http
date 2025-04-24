# discord.http
Python library that handles interactions from Discord POST requests.

## Supported installs
- [Guild application (normal bot)](/examples/ping_cmd_example.py)
- [User application (bots on user accounts)](/examples/user_command_example.py)

## Installing
> You need **Python >=3.11** to use this library.

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
    token="Your bot token here",
    application_id="Bot application ID",
    public_key="Bot public key",
    sync=True
)

@client.command()
async def ping(ctx: Context):
    """ A simple ping command """
    return ctx.response.send_message("Pong!")

client.start()
```

Need further help on how to make Discord API able to send requests to your bot?
Check out [the documentation](https://discordhttp.alexflipnote.dev/pages/getting_started.html) for more detailed information.

## Resources
- Documentations
  - [Library documentation](https://discordhttp.alexflipnote.dev)
  - [Discord API documentation](https://discord.com/developers/docs/intro)
- [Discord server](https://discord.gg/yqb7vATbjH)
- [discord.http Bot example](https://github.com/AlexFlipnote/discord_bot.http)


## Acknowledgements
This library was inspired by [discord.py](https://github.com/Rapptz/discord.py), developed by [Rapptz](https://github.com/Rapptz).
We would like to express our gratitude for their amazing work, which has served as a foundation for this project.

The project is also a fork of [joyn-gg/discord.http](https://github.com/joyn-gg/discord.http)
