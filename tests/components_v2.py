# To test this code, there are two ways:
# 1. pip install git+https://github.com/AlexFlipnote/discord.http.git@feat/components_v2
# 2. Download/Git Clone this repository and install

import json

from io import BytesIO
from discord_http import (
    Client, Context, View, TextDisplayComponent,
    SeparatorComponent, MessageFlags, MessageResponse,
    SectionComponent, Button, ThumbnailComponent,
    ContainerComponent, ActionRow, FileComponent, File,
    MediaGalleryComponent, MediaGalleryItem
)

with open("./config.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    application_id=config["application_id"],
    public_key=config["public_key"],
    sync=True,
    guild_id=1317206872763404478
)


@client.command()
async def test_command(ctx: Context):
    text = TextDisplayComponent(
        content="Hello World!"
    )

    text2 = TextDisplayComponent(
        content="Hello World! Hello World! Hello World! Hello World! Hello World!"
    )

    raw_img1 = File(
        "./images/boomer.png",
        filename="img1.png"
    )

    raw_img2 = File(
        "./images/zoomer.png",
        filename="img2.png"
    )

    img1 = MediaGalleryItem(
        url="attachment://img1.png",
        description="This is a test"
    )

    img2 = MediaGalleryItem(
        url="attachment://img2.png",
        description="This is a test",
        spoiler=True
    )

    gal = MediaGalleryComponent(
        img1, img2
    )

    text_encode = BytesIO("This is a test".encode("utf-8"))
    text_file_raw = File(
        text_encode,
        filename="test.txt"
    )

    text_file = FileComponent(
        "attachment://test.txt",
    )

    view = View(
        ContainerComponent(
            SectionComponent(
                text, text2, text,
                accessory=Button(label="Press me", custom_id="press_me")
            ),
            SeparatorComponent(divider=True),
            text,
            SeparatorComponent(),
            text2,
            colour=0xFF0000,
            row=2
        ),
        ContainerComponent(
            text_file,
            SectionComponent(
                text,
                accessory=ThumbnailComponent(
                    url=ctx.user.display_avatar
                )
            ),
            ActionRow(
                Button(label="Test bottom"),
                Button(label="Test bottom 2"),
            ),
            gal
        ),
    )

    test = MessageResponse(
        view=view,
        flags=MessageFlags.is_components_v2
    )

    with open("./debug.json", "w", encoding="utf-8") as f:
        json.dump(test.to_dict(), f, indent=2)

    async def call_after():
        await ctx.send(
            view=view,
            files=[text_file_raw, raw_img1, raw_img2],
            flags=MessageFlags.is_components_v2
        )

    return ctx.response.send_empty(call_after=call_after)


@client.interaction("press_me")
async def press_me(ctx: Context):
    view = ctx.message.view
    new_btn = Button(label="Nice", disabled=True)

    for g in view.items:
        if not isinstance(g, ContainerComponent):
            continue
        for c in g.items:
            if not isinstance(c, SectionComponent):
                continue
            if not isinstance(c.accessory, Button):
                continue
            if c.accessory.custom_id == "press_me":
                c.accessory = new_btn

    async def call_after():
        test = MessageResponse(
            view=view,
            flags=MessageFlags.is_components_v2
        )

        with open("./debug2.json", "w", encoding="utf-8") as f:
            json.dump(test.to_dict(), f, indent=2)

        await ctx.message.edit(
            view=view,
            flags=MessageFlags.is_components_v2
        )

    return ctx.response.defer(call_after=call_after)


client.start(host="0.0.0.0", port=8080)
