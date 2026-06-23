import json
import logging
import secrets


from discord_http import (
    Context, Client, AllowedMentions, Modal, errors,
    utils, TextStyles, User, TextInputComponent,
    FileUploadComponent, Attachment, commands
)

with open("./config_v2.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    debug_events=config["debug_events"],
    guild_id=config.get("guild_id", None),
    logging_level=logging.DEBUG,
    allowed_mentions=AllowedMentions(
        everyone=False, roles=False, users=True
    )
)


@client.command()
@commands.describe(file="Nice file test yes yes")
@commands.file_types(file=[".jpg", ".png"])
async def test_command(ctx: Context, file: Attachment):
    """ Nice test command """


@client.command()
async def test_modal(ctx: Context):
    """ Nice test command """
    modal = Modal(title="Testing...", custom_id="test_modal_test")
    for g in range(2):
        modal.add_item(TextInputComponent(
            label=f"Test {g}",
            custom_id=f"test_modal:{g}",
            default=secrets.token_hex(6),
            style=TextStyles.random(),
        ))
    modal.add_item(FileUploadComponent(
        label="Nice test",
        file_types=["audio", ".pdf"]
    ))

    return ctx.response.send_modal(modal)


# @client.listener()
async def on_raw_interaction(data: dict):
    print(data)


# @client.listener()
async def on_interaction_error(ctx: Context, error: errors.DiscordException):
    print(utils.traceback_maker(error))


# @client.listener()
async def on_ready(user: User):
    print(f"Logged in as {user}")


client.start(host="0.0.0.0", port=8080)
