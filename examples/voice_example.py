import asyncio

from discord_http import BaseChannel, Client, Context, PartialChannel, VoiceClient, WaveSink
from discord_http.gateway import GatewayCacheFlags, Intents

# Voice requires a gateway connection (to send the voice-state update) and the
# guild_voice_states intent (so the bot receives its own voice server/state updates).
#
# To follow whoever ran a command, the bot also needs to *cache* voice states: the
# guild_voice_states intent only makes Discord SEND the updates, while gateway_cache
# decides what the library keeps. Without GatewayCacheFlags.voice_states (and a guild
# cache to hang them on), get_member_voice_state() is always empty and the bot will
# think nobody is in a channel.
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
    ),
    gateway_cache=(
        GatewayCacheFlags.guilds |
        GatewayCacheFlags.voice_states
    )
)


def caller_voice_channel(ctx: Context) -> "BaseChannel | PartialChannel | None":
    """
    Resolve the voice channel the invoking member is currently sitting in.

    This reads the member's cached voice state (populated from the gateway via the
    guild_voice_states intent) instead of relying on a hard-coded channel id, so the
    bot always follows whoever ran the command.
    """
    if ctx.guild is None or ctx.author is None:
        return None

    voice_state = ctx.guild.get_member_voice_state(ctx.author.id)
    if voice_state is None or voice_state.channel_id is None:
        return None

    # ``VoiceState`` exposes the resolved ``channel`` directly; the partial variant only
    # carries the id, so fall back to a partial channel that ``connect()`` can act on.
    return getattr(voice_state, "channel", None) or client.get_partial_channel(
        voice_state.channel_id, guild_id=ctx.guild.id
    )


@client.command()
async def join(ctx: Context):
    """ Join the caller's voice channel and play a song """
    channel = caller_voice_channel(ctx)
    if channel is None:
        return ctx.response.send_message("Join a voice channel first, then try again.")

    vc: VoiceClient = await channel.connect()

    # Play a local file (mp3 -> opus passthrough, ffmpeg only).
    vc.play("song.mp3")

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
    vc.play("song.mp3")
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
