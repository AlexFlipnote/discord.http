import json
import logging
import secrets


from discord_http import (
    Context, Client, AllowedMentions, Modal, errors,
    utils, TextStyles, User, TextInputComponent,
    FileUploadComponent, Attachment, commands,
    View, ActionRow, Button, SectionComponent, ContainerComponent,
    TextDisplayComponent, OverflowMenuComponent, OverflowMenuGroup,
    MenuActionItem, MenuActionItemStyles, MessageFlags
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
async def test_command(ctx: Context):
    """ Nice test command """
    return ctx.response.send_message(
        view=View(
            TextDisplayComponent("Hi there"),
            ActionRow(Button(
                label="Please edit me",
                custom_id="edit_me_please"
            ))
        ),
        flags=MessageFlags.is_components_v2
    )


@client.interaction("edit_me_please")
async def int_test_command(ctx: Context):
    async def call_after():
        try:
            return await ctx.edit_original_response(content="Hi there", view=None)
        except Exception as e:
            return await ctx.edit_original_response(
                view=View(TextDisplayComponent(str(e))),
                flags=MessageFlags.is_components_v2
            )

    return ctx.response.defer(call_after=call_after)


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


def _overflow_view(status: str) -> View:
    """ Builds a view with an overflow menu in both allowed places. """
    return View(
        ContainerComponent(
            SectionComponent(
                "## Overflow menu test\n"
                "The ⋯ beside this text is a section accessory.",
                accessory=OverflowMenuComponent(
                    OverflowMenuGroup(
                        MenuActionItem(
                            label="Edit", custom_id="overflow:edit",
                            description="A default item with a description", emoji="✏️"
                        ),
                        MenuActionItem(
                            label="Delete", custom_id="overflow:delete",
                            style=MenuActionItemStyles.danger, emoji="🗑️"
                        ),
                        label="Manage",
                    ),
                    OverflowMenuGroup(
                        MenuActionItem(
                            label="Disabled item", custom_id="overflow:disabled",
                            disabled=True
                        ),
                        MenuActionItem(
                            label="Open discord.com", url="https://discord.com",
                            style=MenuActionItemStyles.link
                        ),
                        label="The dumb menu",
                    ),
                ),
            ),
            TextDisplayComponent(f"-# {status}"),
        ),
        ActionRow(
            Button(label="Normal button", custom_id="overflow:button"),
            OverflowMenuComponent(
                OverflowMenuGroup(
                    MenuActionItem(label="Row item A", custom_id="overflow:row_a"),
                    MenuActionItem(label="Row item B", custom_id="overflow:row_b"),
                ),
            ),
        ),
        ActionRow(
            Button(label="Normal button, v2", custom_id="overflow:button2"),
            OverflowMenuComponent(
                MenuActionItem(label="This has", custom_id="overflow:row_a2"),
                MenuActionItem(label="no groups in code", custom_id="overflow:row_b2"),
            ),
        ),
    )


@client.command()
async def test_overflow_menu(ctx: Context):
    """ Test overflow menus (type 25) and menu action items (type 26) """
    return ctx.response.send_message(
        view=_overflow_view("Nothing clicked yet"),
        flags=MessageFlags.is_components_v2,
    )


@client.interaction(r"^overflow:", regex=True)
async def int_overflow_menu(ctx: Context):
    print(ctx._data)
    print(f"Overflow click: custom_id={ctx.custom_id!r} user={ctx.user} values={ctx.select_values.strings}")
    return ctx.response.edit_message(
        view=_overflow_view(f"Last clicked: `{ctx.custom_id}` by {ctx.user}"),
        flags=MessageFlags.is_components_v2,
    )


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
