"""
Manual voice testing, put .mp3 files in ./audio and they show up as choices in /voice_play
Needs ffmpeg on PATH, receiving (/voice_listen) works without libopus since it counts raw opus packets
"""

import asyncio
import json
import logging
import os
import time

from discord_http import (
    Context, Client, VoiceChannel, CallbackSink,
    commands
)
from discord_http.gateway import Intents, GatewayCacheFlags

with open("./config.json") as f:
    config = json.load(f)

client = Client(
    token=config["token"],
    debug_events=config["debug_events"],
    guild_id=config.get("guild_id", None),
    logging_level=logging.DEBUG,
    intents=(
        Intents.guilds |
        Intents.guild_voice_states
    ),
    gateway_cache=(
        GatewayCacheFlags.guilds |
        GatewayCacheFlags.voice_states
    )
)

audio_files = sorted(f for f in os.listdir("./audio") if f.endswith(".mp3"))


async def join_caller(ctx: Context):
    """ Connect to the caller's voice channel, or return the existing voice client """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is not None:
        # Another command may still be connecting it
        for _ in range(100):
            if vc.is_connected():
                break
            await asyncio.sleep(0.1)
        return vc

    voice_state = ctx.guild.get_member_voice_state(ctx.user.id)
    if voice_state is None or voice_state.channel is None:
        return None

    return await voice_state.channel.connect()


@client.command()
async def voice_join(ctx: Context):
    """ Join your voice channel """
    async def call_after():
        vc = await join_caller(ctx)
        if vc is None:
            return await ctx.edit_original_response(content="Join a voice channel first")
        await ctx.edit_original_response(content=f"Joined <#{vc.connection.channel_id}>")

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.command()
@commands.choices(file={f: f for f in audio_files})
async def voice_play(ctx: Context, file: commands.Choice[str]):
    """ Play one of the mp3 files from ./audio """
    async def call_after():
        vc = await join_caller(ctx)
        if vc is None:
            return await ctx.edit_original_response(content="Join a voice channel first")

        started = time.perf_counter()
        vc.play(
            f"./audio/{file.key}",
            after=lambda e: print(f"Finished {file.key} after {time.perf_counter() - started:.1f}s, error: {e}")
        )
        await ctx.edit_original_response(content=f"Now playing **{file.key}**")

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.command()
async def voice_pause(ctx: Context):
    """ Pause or resume playback """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    if vc.is_paused():
        vc.resume()
        return ctx.response.send_message("Resumed")

    vc.pause()
    return ctx.response.send_message("Paused")


@client.command()
async def voice_stop(ctx: Context):
    """ Stop playback but stay connected """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    vc.stop()
    return ctx.response.send_message("Stopped")


@client.command()
async def voice_move(ctx: Context, channel: VoiceChannel):
    """ Move the bot to another voice channel, audio should keep playing """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    async def call_after():
        await vc.move_to(channel)
        await ctx.edit_original_response(content=f"Moving to {channel.mention}")

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.command()
async def voice_reconnect(ctx: Context):
    """ Force a reconnect like a dropped connection would, audio should keep playing """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    started = time.perf_counter()
    vc.connection._on_socket_closed(1006)

    async def call_after():
        for _ in range(100):
            await asyncio.sleep(0.1)
            if vc.is_connected():
                break

        await ctx.edit_original_response(
            content=(
                f"Reconnected: **{vc.is_connected()}** in {time.perf_counter() - started:.2f}s, "
                f"still playing: **{vc.is_playing()}**"
            )
        )

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.command()
@commands.describe(seconds="How long to listen for")
async def voice_listen(ctx: Context, seconds: int = 10):
    """ Count received audio packets per user, talk while it runs """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    async def call_after():
        packets: dict[int | None, int] = {}

        def on_audio(user: int | None, data):
            packets[user] = packets.get(user, 0) + 1

        vc.listen(CallbackSink(on_audio, opus=True))
        await asyncio.sleep(seconds)
        vc.stop_listening()

        if not packets:
            return await ctx.edit_original_response(content=f"Received nothing in {seconds}s")

        lines = "\n".join(
            f"- <@{user}>: {count} packets (~{count / seconds:.0f}/s)"
            for user, count in packets.items()
        )
        await ctx.edit_original_response(content=f"Received in {seconds}s:\n{lines}")

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.command()
async def voice_status(ctx: Context):
    """ Show the voice connection state """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    conn = vc.connection
    return ctx.response.send_message(
        f"Channel: <#{conn.channel_id}>\n"
        f"Connected: **{vc.is_connected()}**, playing: **{vc.is_playing()}**, "
        f"paused: **{vc.is_paused()}**, listening: **{vc.is_listening()}**\n"
        f"Latency: **{vc.latency * 1000:.1f}ms** (avg {vc.average_latency * 1000:.1f}ms)\n"
        f"Mode: `{conn.mode}`, DAVE version: **{conn.dave_protocol_version}**, ssrc: `{conn.ssrc}`"
    )


@client.command()
async def voice_leave(ctx: Context):
    """ Stop playback and leave """
    vc = client.get_voice_client(ctx.guild.id)
    if vc is None:
        return ctx.response.send_message("Not connected")

    async def call_after():
        await vc.disconnect()
        await ctx.edit_original_response(content="Disconnected")

    return ctx.response.defer(thinking=True, call_after=call_after)


@client.listener()
async def on_ready(user):
    print(f"Logged in as {user}, audio files: {audio_files}")


client.start(host="0.0.0.0", port=8080)
