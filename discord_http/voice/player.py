import abc
import asyncio
import contextlib
import io
import logging
import math
import os
import shlex
import shutil

from array import array
from collections import deque
from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING

from ..errors import FFmpegError
from .oggparse import _HEADER_STRUCT, _OGG_MAGIC, OggPage
from .opus import OPUS_SILENCE
from .sinks import _schedule_if_awaitable

if TYPE_CHECKING:
    from .client import VoiceClient

__all__ = (
    "AudioPlayer",
    "AudioSource",
    "AudioSourceInput",
    "FFmpegOpusAudio",
    "FFmpegPCMAudio",
    "PCMAudio",
    "PCMVolumeTransformer",
)

_log = logging.getLogger(__name__)


# The size of a single 20ms PCM frame, in bytes (48kHz, stereo, s16le).
FRAME_SIZE = 3840

# The number of bytes pulled from ffmpeg stdout per read when parsing Ogg/Opus.
_OGG_READ_CHUNK = 8192

# The signed 16-bit value range, used when clamping scaled PCM samples.
_INT16_MIN = -32768
_INT16_MAX = 32767

# How many trailing lines of ffmpeg's stderr to keep for error messages
_STDERR_TAIL_LINES = 10

# Falling this far behind the pacing schedule (a slow source) re-anchors it
# instead of sending the backlog in one burst, which Discord would mostly drop
_MAX_PACING_LAG = 0.2

# Keeps ffmpeg reaping tasks alive after their source is gone
_reap_tasks: set[asyncio.Task] = set()


class AudioSource(abc.ABC):
    """ An abstract audio source yielding one 20ms frame per :meth:`read` (Opus packet or 3840-byte s16le PCM). """

    @abc.abstractmethod
    async def read(self) -> bytes:
        """ Read the next 20ms frame (Opus packet or 3840-byte PCM), or empty bytes at end of stream. """
        raise NotImplementedError

    def is_opus(self) -> bool:
        """ Whether :meth:`read` yields pre-encoded Opus packets rather than PCM. """
        return False

    def cleanup(self) -> None:
        """ Release any resources held by the source. """
        return


class PCMAudio(AudioSource):
    """ An audio source that reads raw s16le 48kHz stereo PCM frames from a binary stream. """

    def __init__(self, stream: io.IOBase) -> None:
        self.stream = stream

    async def read(self) -> bytes:
        """ Read one 3840-byte PCM frame, or empty bytes at end of stream. """
        if isinstance(self.stream, io.BytesIO):
            ret = self.stream.read(FRAME_SIZE)
        else:
            # Off the loop, a real file or slow stream would stall pacing and heartbeats
            ret = await asyncio.to_thread(self.stream.read, FRAME_SIZE)

        if len(ret) != FRAME_SIZE:
            return b""
        return ret


class PCMVolumeTransformer(AudioSource):
    """ A wrapper that scales the volume of a PCM (non-Opus) audio source using the stdlib :mod:`array` module. """

    def __init__(self, original: AudioSource, volume: float = 1.0) -> None:
        if not isinstance(original, AudioSource):
            raise TypeError(f"Expected AudioSource, got {type(original).__name__}")
        if original.is_opus():
            raise ValueError("PCMVolumeTransformer only supports non-Opus sources")

        self.original = original
        self._volume = max(volume, 0.0)

    @property
    def volume(self) -> float:
        """ The volume multiplier, where ``1.0`` is unchanged. """
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = max(value, 0.0)

    async def read(self) -> bytes:
        """ Read one frame from the wrapped source with volume applied. """
        data = await self.original.read()
        if not data:
            return b""

        if math.isclose(self._volume, 1.0):
            return data

        samples = array("h")
        samples.frombytes(data)
        for i, sample in enumerate(samples):
            scaled = int(sample * self._volume)
            samples[i] = min(max(scaled, _INT16_MIN), _INT16_MAX)

        return samples.tobytes()

    def cleanup(self) -> None:
        """ Clean up the wrapped source. """
        self.original.cleanup()


class _FFmpegAudio(AudioSource):
    """ A base audio source backed by an ``ffmpeg`` subprocess launched lazily on first :meth:`read`. """

    def __init__(
        self,
        source: str | io.IOBase | AsyncIterable[bytes],
        *,
        args: list[str],
        before_args: list[str] | None = None,
        executable: str = "ffmpeg",
        pipe: bool = False,
    ) -> None:
        if shutil.which(executable) is None:
            raise FileNotFoundError(f"ffmpeg executable {executable!r} was not found on PATH")

        self._source = source
        self._executable = executable
        self._pipe = pipe
        self._args = args
        self._before_args = before_args or []

        self._process: asyncio.subprocess.Process | None = None
        self._stdin_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stdout: asyncio.StreamReader | None = None
        self._stderr_tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
        self._stdin_error: Exception | None = None
        self._closed = False
        self._finished = False

    async def _spawn(self) -> None:
        """ Launch the ffmpeg subprocess and start the stdin pump if piping. """
        stdin = asyncio.subprocess.PIPE if self._pipe else asyncio.subprocess.DEVNULL
        input_arg = "pipe:0" if self._pipe else self._source

        if not isinstance(input_arg, str):
            # Non-pipe sources must be a path or URL string.
            raise TypeError(f"Expected str source for non-piped ffmpeg, got {type(input_arg).__name__}")

        self._process = await asyncio.create_subprocess_exec(
            self._executable,
            *self._before_args,
            "-i",
            input_arg,
            *self._args,
            stdin=stdin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._stdout = self._process.stdout
        self._stderr_task = asyncio.create_task(self._read_stderr())

        if self._pipe:
            self._stdin_task = asyncio.create_task(self._pump_stdin())

    async def _read_stderr(self) -> None:
        """ Keep the last lines of ffmpeg's stderr, and keep the pipe drained so ffmpeg never blocks on it. """
        process = self._process
        if process is None or process.stderr is None:
            return

        while line := await process.stderr.readline():
            text = line.decode("utf-8", "replace").strip()
            if text:
                self._stderr_tail.append(text)

    async def _finish(self) -> None:
        """
        Check how ffmpeg ended once its output is exhausted.

        Raises
        ------
        FFmpegError
            - If ffmpeg exited with an error
            - If feeding it the input failed
        """
        if self._finished:
            return
        self._finished = True

        process = self._process
        if process is None:
            return

        try:
            returncode = await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            # Closed its output but kept running, cleanup() kills it
            return

        if self._stderr_task is not None:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await asyncio.wait_for(self._stderr_task, 1)

        if self._stdin_error is not None:
            raise FFmpegError(f"Failed to feed audio to ffmpeg: {self._stdin_error!r}") from self._stdin_error

        if returncode != 0:
            message = f"ffmpeg exited with code {returncode}"
            if self._stderr_tail:
                message += ": " + " | ".join(self._stderr_tail)
            raise FFmpegError(message)

    async def _pump_stdin(self) -> None:
        """ Copy the piped source into ffmpeg stdin, then close it. """
        process = self._process
        if process is None or process.stdin is None:
            return

        stdin = process.stdin
        try:
            if isinstance(self._source, AsyncIterable):
                async for chunk in self._source:
                    stdin.write(chunk)
                    await stdin.drain()
            elif isinstance(self._source, io.IOBase):
                while True:
                    # Off the loop, a real file or slow stream would stall pacing and heartbeats
                    chunk = await asyncio.to_thread(self._source.read, _OGG_READ_CHUNK)
                    if not chunk:
                        break
                    stdin.write(chunk)
                    await stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # ffmpeg may exit early (e.g. on stop); nothing more to feed.
            pass
        except Exception as exc:
            # The user's stream failed, ffmpeg only sees its input end early, so
            # keep the error for _finish() to report through ``after``
            self._stdin_error = exc
        finally:
            try:
                stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

    def cleanup(self) -> None:
        """ Terminate the ffmpeg subprocess and cancel the stdin pump. """
        self._closed = True

        for task in (self._stdin_task, self._stderr_task):
            if task is not None and not task.done():
                task.cancel()
        self._stdin_task = None
        self._stderr_task = None

        process = self._process
        if process is not None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

            # Reap the process before closing its transport: under uvloop, closing
            # the transport first stops libuv watching the child, which then stays
            # a zombie. ``cleanup`` is synchronous, so the wait runs as a task
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                task = loop.create_task(self._reap_process(process))
                _reap_tasks.add(task)
                task.add_done_callback(_reap_tasks.discard)
            else:
                # Hard interpreter shutdown, nothing left to wait with
                self._close_transport(process)

        self._process = None
        self._stdout = None

    @staticmethod
    def _close_transport(process: "asyncio.subprocess.Process") -> None:
        """
        Close the subprocess transport so its stdio pipes are released.

        On the Windows Proactor event loop an unclosed pipe transport otherwise
        triggers a ResourceWarning when the garbage collector finalizes it.
        """
        transport = getattr(process, "_transport", None)
        if transport is not None:
            with contextlib.suppress(Exception):
                transport.close()

    @classmethod
    async def _reap_process(cls, process: "asyncio.subprocess.Process") -> None:
        """ Wait for the killed ffmpeg to exit, then release its pipes. """
        try:
            await asyncio.wait_for(process.wait(), 5)
        except Exception:
            pass
        finally:
            cls._close_transport(process)


class FFmpegPCMAudio(_FFmpegAudio):
    """ An audio source that transcodes input to s16le 48kHz stereo PCM with ``ffmpeg`` (libopus needed to encode). """

    def __init__(
        self,
        source: str | io.IOBase | AsyncIterable[bytes],
        *,
        before_options: str | None = None,
        options: str | None = None,
        pipe: bool = False,
        executable: str = "ffmpeg",
    ) -> None:
        before_args = shlex.split(before_options) if before_options is not None else None

        args = ["-f", "s16le", "-ar", "48000", "-ac", "2", "-loglevel", "warning"]
        if options is not None:
            args.extend(shlex.split(options))
        args.append("pipe:1")

        super().__init__(source, args=args, before_args=before_args, executable=executable, pipe=pipe)

    async def read(self) -> bytes:
        """ Read one 3840-byte PCM frame from ffmpeg, or empty bytes at EOF. """
        if self._closed:
            return b""

        if self._stdout is None:
            await self._spawn()

        stdout = self._stdout
        if stdout is None:
            return b""

        try:
            return await stdout.readexactly(FRAME_SIZE)
        except asyncio.IncompleteReadError:
            # End of stream: discard any trailing partial frame and signal EOF.
            # The contract requires exactly FRAME_SIZE bytes or empty bytes; a
            # short PCM frame would be mis-encoded by libopus downstream.
            await self._finish()
            return b""


class FFmpegOpusAudio(_FFmpegAudio):
    """ An audio source that encodes input to Opus with ``ffmpeg``, extracting raw packets from its Ogg/Opus stream. """

    def __init__(
        self,
        source: str | io.IOBase | AsyncIterable[bytes],
        *,
        bitrate: int = 128,
        before_options: str | None = None,
        options: str | None = None,
        pipe: bool = False,
        executable: str = "ffmpeg",
    ) -> None:
        before_args = shlex.split(before_options) if before_options is not None else None

        args = [
            "-c:a", "libopus",
            "-f", "opus",
            "-ar", "48000",
            "-ac", "2",
            "-b:a", f"{bitrate}k",
            "-loglevel", "warning",
        ]
        if options is not None:
            args.extend(shlex.split(options))
        args.append("pipe:1")

        super().__init__(source, args=args, before_args=before_args, executable=executable, pipe=pipe)

        self._buffer = bytearray()
        self._partial = bytearray()
        self._packets: deque[bytes] = deque()
        self._eof = False

    async def _fill_buffer(self) -> bool:
        """ Read one chunk from ffmpeg stdout into the buffer, returning ``False`` at end of stdout. """
        stdout = self._stdout
        if stdout is None:
            # cleanup() ran while a read was in flight
            self._eof = True
            return False

        chunk = await stdout.read(_OGG_READ_CHUNK)
        if not chunk:
            self._eof = True
            return False

        self._buffer.extend(chunk)
        return True

    def _drain_buffer(self) -> None:
        """ Parse every complete Ogg page currently held in the buffer. """
        while True:
            index = self._buffer.find(_OGG_MAGIC)
            if index < 0:
                break

            try:
                # The slice starts just after the magic, matching what OggPage
                # expects. OggPage raises ValueError while the page is still
                # truncated, in which case we wait for more ffmpeg output.
                page = OggPage(io.BytesIO(self._buffer[index + 4:]))
            except ValueError:
                break

            page_end = index + 4 + _HEADER_STRUCT.size + len(page.segtable) + len(page.data)

            for chunk, complete in page.iter_packets():
                self._partial.extend(chunk)
                if complete:
                    packet = bytes(self._partial)
                    self._partial.clear()
                    if not packet.startswith((b"OpusHead", b"OpusTags")):
                        self._packets.append(packet)

            del self._buffer[:page_end]

    async def read(self) -> bytes:
        """ Read one Opus packet from ffmpeg's Ogg stream, or empty bytes at EOF. """
        if self._closed:
            return b""

        if self._stdout is None:
            await self._spawn()

        while not self._packets:
            self._drain_buffer()
            if self._packets:
                break
            if self._eof:
                if not self._closed:
                    await self._finish()
                return b""
            await self._fill_buffer()

        return self._packets.popleft()

    def is_opus(self) -> bool:
        """ Whether frames are Opus packets (always ``True`` for this source). """
        return True


class AudioPlayer:
    """ A drift-corrected :class:`asyncio.Task` player that streams an :class:`AudioSource` to a voice client. """

    DELAY: float = 0.02

    def __init__(
        self,
        source: AudioSource,
        voice_client: "VoiceClient",
        *,
        after: Callable[[Exception | None], object] | None = None,
    ) -> None:
        self.source = source
        self.voice_client = voice_client
        self.after = after

        self._loop = voice_client.loop
        self._task: asyncio.Task[None] | None = None
        self._resumed = asyncio.Event()
        self._resumed.set()
        self._end = asyncio.Event()
        self._error: Exception | None = None
        self._started = False

    def start(self) -> None:
        """ Schedule the playback task on the voice client's event loop. """
        if self._task is not None:
            raise RuntimeError("Player has already been started")
        self._task = self._loop.create_task(self._run())
        self._task.add_done_callback(self._on_task_done)

    def _on_task_done(self, _task: asyncio.Task[None]) -> None:
        """ Clean up a player that was stopped before its task ever ran. """
        if self._started:
            return

        # A task cancelled before its first step never enters _run(), so its
        # cleanup never ran: release the source and still tell ``after``
        self._end.set()
        try:
            self.source.cleanup()
        except Exception:
            _log.exception("Failed to clean up the audio source")
        self._call_after()

    def _call_after(self) -> None:
        """ Invoke ``after`` with the playback error, if any. """
        if self.after is None:
            if self._error is not None:
                _log.exception("Exception in audio player", exc_info=self._error)
            return

        try:
            result = self.after(self._error)
        except Exception:
            _log.exception("Error calling the after callback")
            return

        _schedule_if_awaitable(result, "after callback")

    def _send_silence(self) -> None:
        """ Send the five silence frames Discord asks for whenever audio stops, so clients don't interpolate. """
        for _ in range(5):
            self.voice_client.send_audio_packet(OPUS_SILENCE, encode=False)

    async def _run(self) -> None:
        """ Drive the playback loop with drift-corrected pacing. """
        self._started = True
        try:
            await self.voice_client.speak(True)

            start = self._loop.time()
            count = 0

            while not self._end.is_set():
                if not self._resumed.is_set():
                    self._send_silence()
                    with contextlib.suppress(Exception):
                        await self.voice_client.speak(False)

                    await self._resumed.wait()
                    if self._end.is_set():
                        break

                    with contextlib.suppress(Exception):
                        await self.voice_client.speak(True)

                    # Re-anchor pacing after a pause so we do not burst frames.
                    start = self._loop.time()
                    count = 0

                source = self.source
                data = await source.read()

                if source is not self.source:
                    # set_source() swapped the source while this read was in
                    # flight; the old source may have been torn down mid-read,
                    # making a truncated read look like EOF. Discard the stale
                    # result and re-anchor pacing on the new source instead.
                    start = self._loop.time()
                    count = 0
                    continue

                if not data:
                    break

                self.voice_client.send_audio_packet(data, encode=not source.is_opus())

                count += 1
                now = self._loop.time()
                delay = start + count * self.DELAY - now
                if delay < -_MAX_PACING_LAG:
                    start = now - count * self.DELAY
                    delay = 0.0
                await asyncio.sleep(max(0.0, delay))
        except Exception as exc:
            self._error = exc
        finally:
            try:
                await self._cleanup()
            except asyncio.CancelledError:
                _log.warning(
                    f"Audio player cleanup for guild {self.voice_client.guild_id} "
                    "was interrupted; trailing silence and speaking-off may be skipped"
                )
                raise

    async def _cleanup(self) -> None:
        """ Flush silence, stop speaking, clean up and invoke ``after``. """
        # Mark the player as finished so ``is_playing()``/``is_paused()`` report
        # correctly after natural EOF. Idempotent: ``stop()`` may have set it.
        self._end.set()

        # Only flush silence and clear the speaking flag while this player is
        # still the client's current player (or the client has none). When
        # ``play()`` replaced us with a new player, our teardown runs
        # concurrently with its startup; sending speaking-off here would race
        # the new player's speaking-on and could leave the indicator stuck off.
        current = self.voice_client._player
        try:
            if current is self or current is None:
                try:
                    self._send_silence()
                except Exception:
                    _log.exception("Failed to send trailing silence frames")

                try:
                    await self.voice_client.speak(False)
                except Exception:
                    _log.exception("Failed to disable speaking")
        finally:
            # Runs even when cancelled during speak(False), so ffmpeg never leaks
            self.source.cleanup()
            self._call_after()

    def stop(self) -> None:
        """ Stop playback as soon as possible and resume any paused loop. """
        self._end.set()
        self._resumed.set()
        if self._task is not None:
            self._task.cancel()

    def pause(self) -> None:
        """ Pause playback, halting reads until :meth:`resume` is called. """
        self._resumed.clear()

    def resume(self) -> None:
        """ Resume playback after a :meth:`pause`. """
        self._resumed.set()

    def is_playing(self) -> bool:
        """ Whether audio is currently playing (running and not paused). """
        return not self._end.is_set() and self._resumed.is_set()

    def is_paused(self) -> bool:
        """ Whether playback is paused (running but paused). """
        return not self._end.is_set() and not self._resumed.is_set()

    def set_source(self, source: AudioSource) -> None:
        """
        Hot-swap the audio source without interrupting the player task.

        Parameters
        ----------
        source
            The new audio source to read from.
        """
        # The playback loop notices the swap and discards any read still in
        # flight on the old source, a paused player stays paused
        old = self.source
        self.source = source
        old.cleanup()


AudioSourceInput = AudioSource | str | os.PathLike | bytes | bytearray | memoryview | io.IOBase | AsyncIterable[bytes]
""" The set of inputs accepted as audio sources by :meth:`VoiceClient.play`. """


def _resolve_source(audio: object) -> AudioSource:
    """
    Coerce arbitrary audio input into an :class:`AudioSource`.

    Parameters
    ----------
    audio
        One of: an :class:`AudioSource` (returned as-is); a ``str`` or
        :class:`os.PathLike` path/URL; raw ``bytes``/``bytearray``/``memoryview``;
        a readable :class:`io.IOBase` stream; or an :class:`~collections.abc.AsyncIterable`
        of ``bytes``. The latter four are decoded by ffmpeg into Opus.

    Returns
    -------
    AudioSource
        A source ready to be played.

    Raises
    ------
    TypeError
        If ``audio`` is not a supported type.
    FileNotFoundError
        If ffmpeg is required but not found on ``PATH``.
    """
    if isinstance(audio, AudioSource):
        return audio

    if isinstance(audio, (str, os.PathLike)):
        return FFmpegOpusAudio(os.fspath(audio))

    if isinstance(audio, (bytes, bytearray, memoryview)):
        return FFmpegOpusAudio(io.BytesIO(bytes(audio)), pipe=True)

    if isinstance(audio, io.IOBase):
        return FFmpegOpusAudio(audio, pipe=True)

    if isinstance(audio, AsyncIterable):
        return FFmpegOpusAudio(audio, pipe=True)

    raise TypeError(f"Unsupported audio source type: {type(audio).__name__}")
