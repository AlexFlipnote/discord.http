"""
This code is used to test the bulk of the library
You can also use this is a reference for how to use the library
But honestly, this thing might change a lot, so I wouldn't recommend it
"""

import asyncio
import json
import logging
import secrets

from datetime import time, timedelta
from typing import Union, Optional

from discord_http import (
    Context, Embed, File, Member,
    View, Client, Message,
    Button, Role, commands, Link,
    AllowedMentions, Modal, ButtonStyles,
    errors, Permissions, Colour,
    utils, VoiceChannel, Select,
    TextStyles, User, UserSelect, tasks,
    TextChannel, Attachment, PermissionOverwrite,
    Poll
)

with open("./config.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    application_id=config["application_id"],
    public_key=config["public_key"],
    debug_events=config["debug_events"],
    guild_id=config.get("guild_id", None),
    sync=True,
    logging_level=logging.DEBUG,
    disable_oauth_hint=True,
    allowed_mentions=AllowedMentions(
        everyone=False, roles=False, users=True
    )
)


test_group = client.add_group(name="test_group")
test_group_command2 = test_group.add_group(name="test2")
now = utils.utcnow()


@tasks.loop(seconds=5)
async def test_loop():
    print("Hi there")


@tasks.loop(time=[
    time(hour=now.hour, minute=now.minute, second=i)
    for i in [10, 20, 30, 40, 50]
])
async def test_loop_static_1():
    print("I woke up to give you this lovely ping, cool right?")


@client.backend.before_serving
async def before_serving():
    # test_loop.start()
    test_loop_static_1.start()


@test_loop.before_loop()
async def before_test_loop():
    print("Entered before test loop")
    await client.wait_until_ready()
    print("Client is ready from before test loop")


@test_loop.after_loop()
async def after_test_loop():
    print("Called after test loop")


@test_loop_static_1.before_loop()
async def test_loop_static_before():
    print("Started static time test before loop")


@client.command()
@commands.cooldown(2, 10.0, type=commands.BucketType.user)
async def test_cooldown(ctx: Context):
    print(ctx.command.cooldown._cache)
    return ctx.response.send_message("Not on cooldown yet...")


@client.command()
async def test_multi_channel(
    ctx: Context,
    channel: Union[TextChannel, VoiceChannel]
):
    """ Test multiple channel types """
    return ctx.response.send_message(f"You chose {channel}")


@client.command()
async def test_background_task(ctx: Context, toggle: bool):
    if toggle:
        test_loop.start()
    else:
        test_loop.cancel()

    return ctx.response.send_message("Check console")


@test_group.command(name="test1")
async def test_group_command(ctx: Context):
    """ Normal subcommand """
    return ctx.response.send_message("Hello there from test1")


@test_group_command2.command(name="test3")
async def test_group_command3(ctx: Context, test: str):
    """ Subcommand in subcommand """
    return ctx.response.send_message(
        f"Hello there from sub in sub (test3) with text {test}"
    )


@client.command()
@commands.describe(user="The user to mention in command")
async def test_followup(ctx: Context, user: Member):
    """ My name jeff """
    async def pong():
        msg = await ctx.followup.send(f"Hello there {user.mention}")
        print(msg.user_mentions)

    return ctx.response.defer(thinking=True, call_after=pong)


@client.command()
async def test_reply(ctx: Context):
    async def call_after():
        msg = await ctx.original_response()
        await msg.reply("Indeed a nice test")

    return ctx.response.send_message("Nice test", call_after=call_after)


@client.command()
async def test_remove_command(ctx: Context):
    client.remove_command(test_reply)
    return ctx.response.send_message("Removed command")


@client.command()
async def test_poll(ctx: Context):
    """ Create poll for testing """
    poll = Poll(
        text="Is this a test?",
        duration=timedelta(days=1)
    )

    poll.add_answer(text="Yes", emoji="👍")
    poll.add_answer(text="No")

    async def call_after():
        await asyncio.sleep(5)
        # Time for me to vote
        msg = await ctx.original_response()

        for a in msg.poll.answers:
            if a.count == 0:
                continue
            async for u in msg.fetch_poll_voters(a):
                print(repr(u))

        await msg.expire_poll()

    return ctx.response.send_message(
        "Nice poll test incoming!",
        poll=poll,
        call_after=call_after
    )


@client.command()
async def test_publish(ctx: Context):
    async def call_after():
        msg = await ctx.channel.send("Hi there")
        test = await msg.publish()
        print(test)

    return ctx.response.send_message(
        "Working on it...",
        ephemeral=True,
        call_after=call_after
    )


@client.command()
async def test_guild(ctx: Context):
    guild = await ctx.guild.fetch()
    return ctx.response.send_message(guild.name)


@client.command()
async def test_create_webhook(ctx: Context, name: str, avatar: Optional[Attachment] = None):
    """ Test creating webhook """
    webhook = await ctx.channel.create_webhook(
        name=name,
        avatar=await avatar.to_file() if avatar else None
    )
    return ctx.response.send_message(f"Webhook: {webhook}")


@client.command()
async def test_fetch_members(ctx: Context, guild_id: str):
    if not guild_id.isdigit():
        return ctx.response.send_message("Guild ID must be a number")

    async def call_after():
        guild = ctx.bot.get_partial_guild(int(guild_id))

        members: list[Member] = [
            m async for m in guild.fetch_members(limit=None)
        ]

        print("\n".join([str(m) for m in members]))
        await ctx.followup.send(f"Members: {len(members):,}")

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.command()
async def test_fetch_roles(ctx: Context):
    """ Fetch roles """
    roles = await ctx.guild.fetch_roles()
    return ctx.response.send_message(
        f"Roles: {roles}"
    )


@client.command()
async def test_save(ctx: Context, message_id: str):
    if not message_id.isdigit():
        return ctx.response.send_message("Message ID must be a number")

    msg = await ctx.channel.fetch_message(int(message_id))

    if not msg.attachments:
        return ctx.response.send_message("Message has no attachments")

    await msg.attachments[0].save("./save.png")
    return ctx.response.send_message("Saved")


@client.command()
async def test_webhook(ctx: Context):
    async def after():
        webhook = ctx.bot.get_partial_webhook(
            config["webhook_id"],
            webhook_token=config["webhook_token"]
        )

        msg = await webhook.send(
            "This is a test",
            username=str(ctx.user),
            avatar_url=str(ctx.user.avatar),
            file=File("./images/boomer.png", filename="test.png")
        )

        await asyncio.sleep(3)
        new_msg = await msg.edit(content="lol it was edited")
        await asyncio.sleep(3)
        await new_msg.delete()

    return ctx.response.send_message(
        "Sending webhook...",
        ephemeral=True,
        call_after=after
    )


@client.command()
async def test_ban(ctx: Context, member: Member, reason: str):
    """ Ban a member """
    await member.ban(reason=reason)
    return ctx.response.send_message(
        f"Banned {member} for {reason}"
    )


@client.command()
async def test_unban(ctx: Context, member: str, reason: str):
    """ Unban a member """
    await ctx.guild.unban(int(member), reason=reason)
    return ctx.response.send_message(
        f"Unbanned {member} for {reason}"
    )


@client.command()
async def test_invite(ctx: Context, code: str):
    """ Check if an invite is valid """
    pi = ctx.bot.get_partial_invite(code)
    invite = await pi.fetch()
    return ctx.response.send_message(
        f"Invite: {invite} with {invite.uses} uses, made by {invite.inviter}"
    )


@client.command()
async def test_partial_message(ctx: Context, channel: TextChannel, message_id: str):
    if not message_id.isdigit():
        return ctx.response.send_message("Message ID must be a number")

    msg = ctx.bot.get_partial_message(int(message_id), channel.id)
    msg = await msg.fetch()
    print(msg.jump_urls)
    return ctx.response.send_message(f"Message: {msg.content} | Jump: {msg.jump_url}")


@client.command()
async def test_partial_member(ctx: Context):
    member = ctx.bot.get_partial_member(ctx.user.id, ctx.guild.id)
    member = await member.fetch()
    return ctx.response.send_message(f"Member: {member}")


@client.command()
async def test_public_flags(ctx: Context):
    return ctx.response.send_message(f"{ctx.user.public_flags.to_names()}")


@client.command()
async def test_emoji(ctx: Context):
    """ Upload an emoji """
    async def followup():
        emoji = await ctx.guild.create_emoji(
            name="test",
            image=File("./images/boomer.png")
        )

        msg = await ctx.followup.send(f"Emoji created: {emoji}")

        await asyncio.sleep(3)
        await emoji.delete()
        await msg.edit(content=f"{msg.content}, then deleted it lol")

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
async def test_sticker(ctx: Context):
    async def followup():
        sticker = await ctx.guild.create_sticker(
            name="test",
            description="test",
            emoji="🤔",
            file=File("./images/boomer.png", filename="test.png"),
            reason="lol"
        )
        await ctx.followup.send(
            f"Sticker {sticker.name} created\n"
            f"{sticker.url}"
        )

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
@commands.choices(
    choice={
        "hello": "Hello there!",
        "goodbye": "Goodbye!"
    }
)
async def test_list_str(ctx: Context, choice: commands.Choice[str]):
    return ctx.response.send_message(
        f"You chose **{choice.value}** which has key value: **{choice.key}**"
    )


@client.command()
@commands.choices(
    choice={
        23: "Nice",
        55: "meme"
    }
)
async def test_list_int(ctx: Context, choice: commands.Choice[int]):
    return ctx.response.send_message(
        f"You chose **{choice.value}** ({type(choice.value)}) "
        f"which has key value: **{choice.key}** ({type(choice.key)})"
    )


@client.command()
async def test_int(ctx: Context, number: int):
    """ Just a simple int tester """
    return ctx.response.send_message(f"You chose {number:,} {type(number)}")


@client.command()
async def test_range(ctx: Context, text: commands.Range[int, 1, 4]):
    return ctx.response.send_message(f"You typed: {text} {type(text)}")


@client.command()
async def test_followup_file(ctx: Context):
    """ My name jeff """
    async def pong():
        await ctx.followup.send(
            "Hello there",
            file=File("./images/boomer.png", filename="test.png")
        )

    return ctx.response.defer(thinking=True, call_after=pong)


@client.command()
async def test_local_view(ctx: Context):
    """ Testing a local view lmao """
    view = View(
        Button(label="Hello world", custom_id="test_local_1"),
        Button(label="Goodbye world", custom_id="test_local_2"),
    )

    async def call_after():
        test = await view.wait(ctx, call_after=view_callback, timeout=10)
        if not test:
            print("Timed out")

    async def view_callback(ctx: Context):
        if ctx.custom_id == "test_local_1":
            output = "Hello world"

        elif ctx.custom_id == "test_local_2":
            output = "Goodbye world"

        else:
            output = "Unknown"

        embed = Embed(description=f"You pressed the '{output}' button")

        return ctx.response.edit_message(
            content=None,
            view=None,
            embed=embed
        )

    return ctx.response.send_message(
        "My name jeff", view=view, call_after=call_after
    )


@client.command()
@commands.describe(text="This is just an autocomplete test")
async def test_autocomplete(ctx: Context, text: int):
    return ctx.response.send_message(f"You chose {text}")


@test_autocomplete.autocomplete(name="text")
async def test_text_autocomplete(ctx: Context, current: str):
    print(current)
    nice_list = {
        50000: "Hello",
        3000: "World"
    }

    return ctx.response.send_autocomplete(nice_list)


@client.command()
async def test_embed(ctx: Context):
    embed = Embed(
        title=f"Hello {ctx.user}",
        description="This is a description",
        colour=0xFF00FF,
        timestamp=utils.utcnow()
    )

    embed.add_field(
        name="Field 1",
        value="Some random stuff",
        inline=False
    )

    embed.set_thumbnail(url=ctx.user.global_avatar)

    return ctx.response.send_message(embed=embed)


@client.command()
async def test_file(ctx: Context):
    return ctx.response.send_message(
        "Pong, here's an image!",
        file=File("./images/boomer.png", filename="test.png")
    )


@client.command()
async def test_file_edit(ctx: Context):
    async def followup():
        await asyncio.sleep(3)
        msg = await ctx.original_response()
        await msg.edit(
            attachment=File("./images/zoomer.png", filename="test2.png")
        )

    return ctx.response.send_message(
        "Have an image",
        file=File("./images/boomer.png", filename="test.png"),
        call_after=followup
    )


@client.command()
async def test_role(ctx: Context, role: Role):
    return ctx.response.send_message(f"You chose {role}, which comes from {role.guild.id}")


@client.command()
async def test_create_role(ctx: Context, name: str):
    async def followup():
        role = await ctx.guild.create_role(
            name=name,
            colour=Colour.random(),
            permissions=Permissions.from_names(
                "send_messages", "manage_messages"
            )
        )
        await ctx.followup.send(f"Created role {role}")

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
async def test_fetch_channels(ctx: Context):
    async def followup():
        channels = await ctx.guild.fetch_channels()
        print(channels)
        await ctx.followup.send(f"Fetched {len(channels)} channels")

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
async def test_edit_role(ctx: Context, role: Role, new_name: str):
    r = await role.edit(name=new_name)
    return ctx.response.send_message(f"Edited role {r.name}")


@client.command()
async def test_create_category(ctx: Context, name: str):
    category = await ctx.guild.create_category(
        name=name,
        overwrites=[
            PermissionOverwrite(
                ctx.user,
                allow=Permissions.from_names("send_messages")
            )
        ]
    )

    test1 = await category.create_text_channel(name="test")
    await category.create_voice_channel(name="test")

    await test1.set_permission(
        ctx.user,
        overwrite=PermissionOverwrite(
            ctx.user,
            allow=Permissions.from_names("send_messages", "embed_links")
        )
    )

    return ctx.response.send_message(f"Created category {category}")


@client.command()
async def test_typing(ctx: Context):
    """ type like there is no tomorrow """
    async def call_after():
        await asyncio.sleep(1)
        await ctx.channel.typing()

    return ctx.response.send_message(
        "Triggered typing indicator",
        call_after=call_after
    )


@client.command()
async def test_delete_role(ctx: Context, role: Role):
    await role.delete()
    return ctx.response.send_message(f"Deleted role {role.name}")


@client.command()
async def test_channel(ctx: Context, channel: VoiceChannel):
    return ctx.response.send_message(f"You chose {channel} {repr(channel)}")


@client.command()
async def test_search_member(ctx: Context, query: str):
    members = await ctx.guild.search_members(query)
    return ctx.response.send_message(f"Found {members}")


@client.command()
@commands.describe(
    member="The member to edit",
)
async def test_member_edit(ctx: Context, member: Member):
    await member.edit(
        nick="lmao",
        communication_disabled_until=10
    )
    return ctx.response.send_message("I did a thing")


@client.command()
async def test_kick(ctx: Context, member: Member):
    await member.kick(reason="Le funny")
    return ctx.response.send_message(f"Kicked {member}")


@client.command()
async def test_dm(ctx: Context):
    """ Test DMs """

    async def followup():
        await ctx.user.send("Hello there")
        await ctx.followup.send("Sent DM now yes yes")

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
async def test_ratelimit(ctx: Context):
    async def followup():
        await ctx.followup.send("Hello, it is time to spam!")
        await asyncio.sleep(2)
        for i in range(15):
            await ctx.channel.send(f"hi there {i}")
        print("Done spamming")

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
async def test_create_channel(ctx: Context, name: str):
    async def followup():
        channel = await ctx.guild.create_text_channel(name=name)
        edit_channel = await channel.edit(name="test2", nsfw=True)
        await ctx.followup.send(
            f"Created channel {channel}, "
            f"then renamed it to {edit_channel.name}"
        )

    return ctx.response.defer(thinking=True, call_after=followup)


@client.user_command(name="Test user cmd")
async def test_user_cmd(ctx: Context, user: Union[Member, User]):
    return ctx.response.send_message(
        f"You successfully targeted {user}",
        ephemeral=True
    )


@client.message_command(name="Test msg cmd")
async def test_msg_cmd(ctx: Context, message: Message):
    return ctx.response.send_message(
        f"> Message content\n{message.content}",
        ephemeral=True
    )


@client.command()
@commands.locales({
    # Norwegian
    "no": {
        "_": ("ping", "Sender en melding tilbake som pinger deg"),
        "le_funny": ("den_morsome", "Bare en tilfeldig ting")
    }
})
async def test_ping(ctx: Context):
    """ Sends a message back which pings you """
    ping_cmd = ctx.bot.commands["test_ping"]
    return ctx.response.send_message(f"Hi there {ctx.user.mention} {ping_cmd.mention}")


@client.command()
async def test_button(ctx: Context):
    select_menu = Select(
        placeholder="testing...",
        custom_id="test_select::3",
        disabled=True
    )

    select_menu.add_item(
        label="No options found...",
        value="test:hi",
        description="This is a description, yes yes",
        default=True
    )

    view = View(
        select_menu,
        Button(label="funny", custom_id="funny:1337"),
        Button(label="modal test", custom_id="test_send_modal_local"),
        Link(url="https://alexflipnote.dev", label="Test", emoji="👍"),
        Link(
            url="https://alexflipnote.dev",
            label="Test, but custom",
            emoji="<:AlexHeart:785620361118875729>",
            row=2,
        ),
        Link(
            url="https://alexflipnote.dev",
            label="Test, but animated custom",
            emoji="<a:aAlexClap:1074318927250870322>",
            row=2,
        ),
        Link(
            url="https://alexflipnote.dev",
            label="Test, but custom",
            emoji="<:AlexHeart:785620361118875729>",
            row=3,
        ),
        Link(
            url="https://alexflipnote.dev",
            label="Test, but animated custom",
            emoji="<a:aAlexClap:1074318927250870322>",
            row=3,
        )
    )

    test = ctx.response.send_message("Hi there", view=view)
    return test


@client.command()
async def test_select(ctx: Context):
    select = Select(placeholder="testing...", custom_id="test_select")
    select.add_item(label="Hi", value="test:hi", description="This is a description")
    view = View(select)
    return ctx.response.send_message("Hi there", view=view)


async def check_if_me(ctx: Context):
    await asyncio.sleep(1)
    return ctx.user.id == 864777797170667522


@client.command()
@commands.check(check_if_me)
async def test_custom_check(ctx: Context):
    return ctx.response.send_message("You are cool")


@client.command()
async def test_user_select(ctx: Context):
    view = View(
        UserSelect(
            placeholder="testing users..",
            custom_id="test_user_select"
        )
    )

    return ctx.response.send_message(
        "Hi there", view=view
    )


@client.command()
@commands.default_permissions("manage_messages")
@commands.bot_has_permissions("manage_messages")
async def test_bool(ctx: Context, prompt: bool):
    return ctx.response.send_message(f"Prompt is {prompt}")


@client.command()
async def test_history(ctx: Context, limit: Optional[int] = None):
    async def followup():
        msgs = []
        async for msg in ctx.channel.fetch_history(limit=limit):
            msgs.append(msg)
        print("\n".join([
            f"{m.created_at}: {m.content}"
            for m in msgs
        ]))
        await ctx.followup.send(f"Got {len(msgs)} messages")

    return ctx.response.defer(thinking=True, call_after=followup)


@client.command()
async def test_reaction(ctx: Context):
    async def followup():
        msg = await ctx.original_response()
        for e in ["👍", "👎"]:
            await msg.add_reaction(e)
        await asyncio.sleep(1)
        await ctx.edit_original_response(content="now vote")
        await asyncio.sleep(3)
        await ctx.delete_original_response()

    return ctx.response.send_message("Hello world", call_after=followup)


@client.command()
async def test_modal(ctx: Context):
    modal = Modal(title="Testing...", custom_id="test_modal_test")
    for g in range(5):
        modal.add_item(
            label=f"Test {g}",
            custom_id=f"test_modal:{g}",
            default=secrets.token_hex(6),
            style=TextStyles.random(),
        )

    return ctx.response.send_modal(modal)


@client.command()
async def test_button_change(ctx: Context):
    buttons = [
        Button(
            label=str(i),
            custom_id=f"test_button_change:{i}",
            style=ButtonStyles.gray
        )
        for i in range(5 * 5)
    ]

    return ctx.response.send_message(
        "Random colours, go!",
        view=View(*buttons)
    )


@client.interaction(r"test_button_change:[0-9]{1}", regex=True)
async def on_test_button_change(ctx: Context):
    view = ctx.message.view

    for b in view.items:
        if not isinstance(b, Button):
            continue
        b.style = ButtonStyles.random()
        if b.style == ButtonStyles.url:
            b.style = ButtonStyles.green

    return ctx.response.edit_message(view=view)


@client.command()
async def test_decoration(ctx: Context):
    return ctx.response.send_message(
        f"Decoration: {ctx.user.avatar_decoration}"
    )


@client.interaction(r"funny:", regex=True)
async def test_interaction(ctx: Context):
    print(ctx.bot.listeners)
    return ctx.response.edit_message(
        content=f"Button pressed by {ctx.user} on message by {ctx.author}",
        attachments=[File("./images/boomer.png", filename="test.png")]
    )


@client.interaction("test_modal_test")
async def test_interaction_modal(ctx: Context):
    print(ctx.modal_values)
    return ctx.response.defer()


@client.interaction("test_user_select")
async def test_interaction_user_select(ctx: Context):
    return ctx.response.edit_message(
        content=f"Selected: {ctx.select_values.members}",
        view=ctx.message.view
    )


@client.interaction("test_send_modal")
async def test_interaction_modal2(ctx: Context):
    modal = Modal(title="Testing...", custom_id="test_modal_test2")
    for g in range(5):
        modal.add_item(
            label=f"Test {g}",
            custom_id=f"test_modal:{g}",
            default=secrets.token_hex(6),
            style=TextStyles.random(),
        )

    return ctx.response.send_modal(modal)


@client.interaction("test_send_modal_local")
async def test_interaction_modal_local(ctx: Context):
    modal = Modal(title="Testing...", custom_id="iusdhfiosuhjdf")
    for g in range(5):
        modal.add_item(
            label=f"Test {g}",
            custom_id=f"test_modal:{g}",
            default=secrets.token_hex(6),
            style=TextStyles.random(),
        )

    async def call_after():
        test = await modal.wait(ctx, call_after=call_success, timeout=10)
        if not test:
            print("Timed out")

    async def call_success(ctx: Context):
        return ctx.response.send_message("You submitted, nice")

    return ctx.response.send_modal(modal, call_after=call_after)


@client.interaction("test_select")
async def test_interaction2(ctx: Context):
    return ctx.response.edit_message(
        content=(
            f"Select used by {ctx.user} on message by "
            f"{ctx.author} {ctx.select_values.strings[0]}"
        )
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
