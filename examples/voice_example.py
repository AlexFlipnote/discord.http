import asyncio

from discord_http import BaseChannel, Client, Context, VoiceClient, WaveSink
from discord_http.gateway import Intents

# Voice requires a gateway connection (to send the voice-state update) and the
# guild_voice_states intent (so the bot receives its own voice server/state updates).
#
# Codec notes:
#   * Passing an ``.mp3``/``.opus`` file plays through ffmpeg -> Ogg/Opus and needs
#     ONLY ffmpeg installed (no libopus) -- the audio is sent as opus passthrough.
#   * PCM encode/decode (raw PCM sources, volume transforms, or receiving/decoding
#     other users' audio) additionally needs libopus loaded (``discord_http.voice.load_opus``).
#   * DAVE end-to-end encryption (MLS) is optional and needs: pip install "discord.http[voice]"
client = Client(
    token="BOT_TOKEN",
    enable_gateway=True,
    intents=(
        Intents.guild_messages |
        Intents.guild_voice_states
    )
)


@client.command()
async def join(ctx: Context):
    """ Join the caller's voice channel and play a song """
    if ctx.guild is None or ctx.author is None:
        return ctx.response.send_message("This command can only be used in a guild.")

    # Resolve a voice channel to connect to (here a hard-coded id for brevity).
    channel = await client.fetch_channel(1234567890, guild_id=ctx.guild.id)
    if not isinstance(channel, BaseChannel):
        return ctx.response.send_message("Could not find that channel.")

    vc: VoiceClient = await channel.connect()

    # Play a local file (mp3 -> opus passthrough, ffmpeg only).
    await vc.play("song.mp3")

    return ctx.response.send_message(f"Now playing, latency: {vc.latency:.1f}ms")


@client.command()
async def pause(ctx: Context):
    """ Pause / resume the current track """
    vc = client._get_voice_client(ctx.guild.id) if ctx.guild else None
    if vc is None:
        return ctx.response.send_message("Not connected.")

    if vc.is_paused():
        vc.resume()
        return ctx.response.send_message("Resumed.")

    vc.pause()
    return ctx.response.send_message("Paused.")


@client.command()
async def leave(ctx: Context):
    """ Stop playback and disconnect """
    vc = client._get_voice_client(ctx.guild.id) if ctx.guild else None
    if vc is None:
        return ctx.response.send_message("Not connected.")

    vc.stop()
    await vc.disconnect()
    return ctx.response.send_message("Disconnected.")


async def voice_demo(channel: BaseChannel, move_to: BaseChannel) -> None:
    """
    A standalone walkthrough of the voice API.

    Parameters
    ----------
    channel:
        The voice channel to connect to first.
    move_to:
        A second voice channel to move into mid-session.
    """
    vc: VoiceClient = await channel.connect()

    # Playback controls.
    await vc.play("song.mp3")
    vc.pause()
    vc.resume()

    # Hop to another channel without disconnecting.
    await vc.move_to(move_to)

    # Receiving: write everyone's audio into a single WAV file.
    # (decoding opus -> PCM for the WAV needs libopus loaded.)
    vc.listen(WaveSink("out.wav"))
    await asyncio.sleep(10)
    vc.stop_listening()

    print(f"voice latency: {vc.latency:.1f}ms (avg {vc.average_latency:.1f}ms)")

    vc.stop()
    await vc.disconnect()


client.start(host="127.0.0.1", port=8080)
