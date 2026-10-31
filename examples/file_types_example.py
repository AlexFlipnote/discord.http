from discord_http import Context, Client, Attachment, commands

client = Client(
    token="BOT_TOKEN"
)


@client.command()
@commands.file_types(file=["image"])
async def upload_image(ctx: Context, file: Attachment):
    return ctx.response.send_message(
        f"Thanks for the image, **{file.filename}**!"
    )


@client.command()
@commands.describe(file="Any picture or short clip")
@commands.file_types(file=["image", "video"])
async def upload_media(ctx: Context, file: Attachment):
    return ctx.response.send_message(
        f"Received **{file.filename}** ({file.content_type})"
    )


@client.command()
@commands.file_types(file=[".png", ".jpeg", ".jpg", "audio"])
async def upload_mixed(ctx: Context, file: Attachment):
    return ctx.response.send_message(
        f"Got a mix of image and audio types, thanks for **{file.filename}**!"
    )


client.start(host="127.0.0.1", port=8080)
