from discord_http import (
    Client, Context, View,
    SeparatorComponent, MessageFlags,
    SectionComponent, ThumbnailComponent, Member,
    AllowedMentions, DiscordTimestamp
)

client = Client(
    token="BOT_TOKEN",
    application_id=1337,
    public_key="PUBLIC_KEY",
    sync=True
)


@client.command()
async def profile(ctx: Context):
    """ Simple profile command. """
    # Credit to example: souji
    view = View(
        SectionComponent(
            "## User details\n"
            f"Username: {ctx.user.name}\n"
            f"ID: {ctx.user.id}\n"
            f"Created: {DiscordTimestamp(ctx.user.created_at)}",
            accessory=ThumbnailComponent(
                ctx.user.global_avatar or
                ctx.user.default_avatar
            )
        )
    )

    if isinstance(ctx.user, Member):
        pretty_roles = "".join([g.mention for g in ctx.user.roles])
        split = SeparatorComponent(divider=True)
        guild_data = SectionComponent(
            "## Guild details\n"
            f"Nickname: {ctx.user.nick or 'None'}\n"
            f"Joined: {DiscordTimestamp(ctx.user.joined_at)}\n"
            f"Roles ({len(ctx.user.roles)}): {pretty_roles}\n",
            accessory=ThumbnailComponent(
                ctx.user.display_avatar
            )
        )

        view.add_item(split)
        view.add_item(guild_data)

    return ctx.response.send_message(
        view=view,
        flags=MessageFlags.is_components_v2,
        allowed_mentions=AllowedMentions.none()
    )


@client.command("demo_conversation")
async def demo_conversation(ctx: Context):
    """ Demonstrates a conversation. """
    view = View()

    user = SectionComponent(
        "What's the meaning of life?",
        accessory=ThumbnailComponent(
            ctx.user.display_avatar
        )
    )

    split = SeparatorComponent(divider=True)

    bot = SectionComponent(
        "Ah, the classic question! 🤔 The meaning of life can vary for each person. "
        "Some find meaning in connections with others, pursuing passions, or seeking knowledge, "
        "while others might reflect on spirituality or enjoy life's little moments! "
        "🌟 What do you think gives life meaning?",
        accessory=ThumbnailComponent(
            ctx.bot.user.display_avatar
        )
    )

    view.add_item(user)
    view.add_item(split)
    view.add_item(bot)

    return ctx.response.send_message(view=view, flags=MessageFlags.is_components_v2)


client.start(host="127.0.0.1", port=8080)
