import abc
import asyncio
import io
import logging
import os
import shutil

from array import array
from collections.abc import AsyncIterable, Callable
from typing import TYPE_CHECKING

from .oggparse import OggPage
from .opus import OPUS_SILENCE

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

# The 4-byte capture pattern that begins every Ogg page.
_OGG_MAGIC = b"OggS"

# The fixed-size Ogg page header that follows the capture pattern (see oggparse).
_OGG_HEADER_SIZE = 23

# The signed 16-bit value range, used when clamping scaled PCM samples.
_INT16_MIN = -32768
_INT16_MAX = 32767


class AudioSource(abc.ABC):
    """
    An abstract base class for an audio source.

    A source yields raw audio one 20ms frame at a time via :meth:`read`. When
    :meth:`is_opus` returns ``True`` each frame is a complete Opus packet ready
    to be sent on the wire; otherwise each frame is 3840 bytes of signed 16-bit
    little-endian PCM (48kHz, stereo) which the player encodes before sending.
    """

    @abc.abstractmethod
    async def read(self) -> bytes:
        """
        Read the next 20ms frame of audio.

        Returns
        -------
        bytes
            A single Opus packet when :meth:`is_opus` is ``True``, otherwise
            exactly 3840 bytes of s16le PCM. Empty bytes signal end of stream.
        """
        raise NotImplementedError

    def is_opus(self) -> bool:
        """
        Whether :meth:`read` yields pre-encoded Opus packets.

        Returns
        -------
        bool
            ``True`` if frames are Opus packets, ``False`` if they are PCM.
        """
        return False

    def cleanup(self) -> None:
        """ Release any resources held by the source. """
        return


class PCMAudio(AudioSource):
    """
    An audio source that reads raw PCM frames from a binary stream.

    The stream must contain signed 16-bit little-endian PCM at 48kHz in stereo.

    Parameters
    ----------
    stream:
        A readable binary stream of s16le PCM data.
    """

    def __init__(self, stream: io.IOBase) -> None:
        self.stream = stream

    async def read(self) -> bytes:
        """ Read one 3840-byte PCM frame, or empty bytes at end of stream. """
        ret = self.stream.read(FRAME_SIZE)
        if len(ret) != FRAME_SIZE:
            return b""
        return ret


class PCMVolumeTransformer(AudioSource):
    """
    A wrapper that scales the volume of a PCM (non-Opus) audio source.

    Samples are scaled with the stdlib :mod:`array` module because ``audioop``
    is removed in Python 3.13. Each signed 16-bit sample is multiplied by the
    volume factor and clamped back into the int16 range.

    Parameters
    ----------
    original:
        The PCM source to wrap. Its :meth:`AudioSource.is_opus` must be ``False``.
    volume:
        The initial volume multiplier, where ``1.0`` is unchanged.

    Raises
    ------
    TypeError
        If ``original`` is not an :class:`AudioSource`.
    ValueError
        If ``original`` yields Opus packets rather than PCM.
    """

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
    """
    A base audio source backed by an ``ffmpeg`` subprocess.

    The subprocess is launched lazily on the first :meth:`read` via
    :func:`asyncio.create_subprocess_exec`, so no blocking thread is ever used.
    When ``pipe`` is set the ``source`` is streamed into ffmpeg's stdin: a small
    pump task copies bytes from a readable stream (or an async iterable) into
    stdin and closes it at end of input.

    Parameters
    ----------
    source:
        A path/URL (when ``pipe`` is ``False``) or a readable stream / async
        iterable of bytes (when ``pipe`` is ``True``).
    args:
        The ffmpeg output argument list following the ``-i`` input specifier.
    before_args:
        The ffmpeg input argument list placed before the ``-i`` input specifier.
    executable:
        The ffmpeg executable name or path.
    pipe:
        Whether ``source`` is piped to ffmpeg stdin rather than read as input.

    Raises
    ------
    FileNotFoundError
        If the ffmpeg executable cannot be located on ``PATH``.
    """

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
        self._stdout: asyncio.StreamReader | None = None

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
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._stdout = self._process.stdout

        if self._pipe:
            self._stdin_task = asyncio.create_task(self._pump_stdin())

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
                    chunk = self._source.read(_OGG_READ_CHUNK)
                    if not chunk:
                        break
                    stdin.write(chunk)
                    await stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # ffmpeg may exit early (e.g. on stop); nothing more to feed.
            pass
        finally:
            try:
                stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

    def cleanup(self) -> None:
        """ Terminate the ffmpeg subprocess and cancel the stdin pump. """
        if self._stdin_task is not None and not self._stdin_task.done():
            self._stdin_task.cancel()
            self._stdin_task = None

        process = self._process
        if process is not None and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass

        self._process = None
        self._stdout = None


class FFmpegPCMAudio(_FFmpegAudio):
    """
    An audio source that transcodes input to PCM with ``ffmpeg``.

    ffmpeg decodes the input to signed 16-bit little-endian PCM at 48kHz in
    stereo, and :meth:`read` returns one 3840-byte frame per call via
    :meth:`asyncio.StreamReader.readexactly`. The final, possibly short frame is
    returned once before end of stream is signalled with empty bytes.

    Because the output is PCM, libopus is required to encode it before sending.

    Parameters
    ----------
    source:
        A path/URL, or (when ``pipe`` is ``True``) a readable stream / async
        iterable of bytes fed to ffmpeg stdin.
    before_options:
        Extra ffmpeg arguments placed before ``-i`` (e.g. seek options).
    options:
        Extra ffmpeg output arguments placed after the format flags.
    pipe:
        Whether ``source`` is piped to ffmpeg stdin.
    executable:
        The ffmpeg executable name or path.
    """

    def __init__(
        self,
        source: str | io.IOBase | AsyncIterable[bytes],
        *,
        before_options: str | None = None,
        options: str | None = None,
        pipe: bool = False,
        executable: str = "ffmpeg",
    ) -> None:
        before_args = before_options.split() if before_options is not None else None

        args = ["-f", "s16le", "-ar", "48000", "-ac", "2", "-loglevel", "warning"]
        if options is not None:
            args.extend(options.split())
        args.append("pipe:1")

        super().__init__(source, args=args, before_args=before_args, executable=executable, pipe=pipe)

    async def read(self) -> bytes:
        """ Read one 3840-byte PCM frame from ffmpeg, or empty bytes at EOF. """
        if self._stdout is None:
            await self._spawn()

        assert self._stdout is not None
        try:
            return await self._stdout.readexactly(FRAME_SIZE)
        except asyncio.IncompleteReadError as exc:
            # End of stream: return the trailing partial frame, then b"".
            return bytes(exc.partial)


class FFmpegOpusAudio(_FFmpegAudio):
    """
    An audio source that encodes input to Opus with ``ffmpeg``.

    ffmpeg produces an Ogg/Opus stream on stdout and this class extracts raw
    Opus packets from it, so no libopus binding is needed on the Python side.

    Approach for async Ogg parsing
    -------------------------------
    :class:`~discord_http.voice.oggparse.OggPage` parses synchronously from a
    file-like ``read`` and raises ``ValueError`` if a page is truncated. To keep
    the event loop unblocked we never hand it ffmpeg's pipe directly. Instead
    bytes are accumulated in a :class:`bytearray` and parsed one *complete page
    at a time*:

    1. Chunks are read from ffmpeg stdout with ``await stdout.read(n)`` and
       appended to the buffer.
    2. The buffer is scanned for the ``b"OggS"`` capture pattern. Using only the
       fixed header and segment table, the full byte length of the page is
       computed up front; parsing is deferred until that many bytes are present,
       so :class:`OggPage` never sees a truncated page. Each fully-parsed page is
       removed from the front of the buffer.
    3. Packets are reassembled across pages (a trailing ``255`` lacing value
       continues a packet into the next page), with the ``OpusHead``/``OpusTags``
       header packets skipped.

    More bytes are read and the pass retried until at least one packet is ready.
    Empty bytes are returned once stdout is exhausted and the buffer drained.

    Parameters
    ----------
    source:
        A path/URL, or (when ``pipe`` is ``True``) a readable stream / async
        iterable of bytes fed to ffmpeg stdin.
    bitrate:
        The target Opus bitrate in kilobits per second.
    before_options:
        Extra ffmpeg arguments placed before ``-i`` (e.g. seek options).
    options:
        Extra ffmpeg output arguments placed after the format flags.
    pipe:
        Whether ``source`` is piped to ffmpeg stdin.
    executable:
        The ffmpeg executable name or path.
    """

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
        before_args = before_options.split() if before_options is not None else None

        args = [
            "-c:a", "libopus",
            "-f", "opus",
            "-ar", "48000",
            "-ac", "2",
            "-b:a", f"{bitrate}k",
            "-loglevel", "warning",
        ]
        if options is not None:
            args.extend(options.split())
        args.append("pipe:1")

        super().__init__(source, args=args, before_args=before_args, executable=executable, pipe=pipe)

        self._buffer = bytearray()
        self._partial = bytearray()
        self._packets: list[bytes] = []
        self._eof = False

    async def _fill_buffer(self) -> bool:
        """
        Read one chunk from ffmpeg stdout into the buffer.

        Returns
        -------
        bool
            ``True`` if data was read, ``False`` at end of stdout.
        """
        assert self._stdout is not None
        chunk = await self._stdout.read(_OGG_READ_CHUNK)
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

            # An Ogg page is: magic (4) + fixed header (23) + segment table
            # (page_segments) + body (sum of lacing values). Bail until the full
            # page has arrived so OggPage never reads a truncated header/body.
            header_end = index + 4 + _OGG_HEADER_SIZE
            if len(self._buffer) < header_end:
                break

            page_segments = self._buffer[header_end - 1]
            table_end = header_end + page_segments
            if len(self._buffer) < table_end:
                break

            body_size = sum(self._buffer[header_end:table_end])
            page_end = table_end + body_size
            if len(self._buffer) < page_end:
                break

            # The slice starts just after the magic, matching what OggPage expects.
            page = OggPage(io.BytesIO(self._buffer[index + 4:page_end]))
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
        if self._stdout is None:
            await self._spawn()

        while not self._packets:
            self._drain_buffer()
            if self._packets:
                break
            if self._eof:
                return b""
            await self._fill_buffer()

        return self._packets.pop(0)

    def is_opus(self) -> bool:
        """ Whether frames are Opus packets (always ``True`` for this source). """
        return True


class AudioPlayer:
    """
    A paced player that streams an :class:`AudioSource` to a voice client.

    The player runs as an :class:`asyncio.Task`. Frames are read and sent every
    :attr:`DELAY` seconds with drift correction: each frame's deadline is
    computed from a fixed start time so transient delays do not accumulate.

    Pause, resume and stop are controlled by :class:`asyncio.Event` flags, and
    the source can be hot-swapped mid-playback via :meth:`set_source`. When the
    stream ends, five :data:`~discord_http.voice.opus.OPUS_SILENCE` frames are
    sent, speaking is disabled, and the optional ``after`` callback is invoked.

    Parameters
    ----------
    source:
        The audio source to play.
    voice_client:
        The voice client used to speak and send packets.
    after:
        An optional callable invoked with an exception (or ``None`` on success)
        once playback ends. It is called synchronously and may not be a
        coroutine; exceptions raised by it are logged and swallowed.
    """

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

    def start(self) -> None:
        """ Schedule the playback task on the voice client's event loop. """
        if self._task is not None:
            raise RuntimeError("Player has already been started")
        self._task = self._loop.create_task(self._run())

    async def _run(self) -> None:
        """ Drive the playback loop with drift-corrected pacing. """
        try:
            await self.voice_client.speak(True)

            start = self._loop.time()
            count = 0

            while not self._end.is_set():
                if not self._resumed.is_set():
                    await self._resumed.wait()
                    # Re-anchor pacing after a pause so we do not burst frames.
                    start = self._loop.time()
                    count = 0

                data = await self.source.read()
                if not data:
                    break

                self.voice_client.send_audio_packet(data, encode=not self.source.is_opus())

                count += 1
                deadline = start + count * self.DELAY
                await asyncio.sleep(max(0.0, deadline - self._loop.time()))
        except Exception as exc:
            self._error = exc
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        """ Flush silence, stop speaking, clean up and invoke ``after``. """
        try:
            for _ in range(5):
                self.voice_client.send_audio_packet(OPUS_SILENCE, encode=False)
        except Exception:
            _log.exception("Failed to send trailing silence frames")

        try:
            await self.voice_client.speak(False)
        except Exception:
            _log.exception("Failed to disable speaking")

        self.source.cleanup()

        if self.after is not None:
            try:
                self.after(self._error)
            except Exception:
                _log.exception("Error calling the after callback")
        elif self._error is not None:
            _log.exception("Exception in audio player", exc_info=self._error)

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
        """
        Whether audio is currently playing.

        Returns
        -------
        bool
            ``True`` if the loop is running and not paused.
        """
        return not self._end.is_set() and self._resumed.is_set()

    def is_paused(self) -> bool:
        """
        Whether playback is paused.

        Returns
        -------
        bool
            ``True`` if the loop is running but paused.
        """
        return not self._end.is_set() and not self._resumed.is_set()

    def set_source(self, source: AudioSource) -> None:
        """
        Hot-swap the audio source without interrupting the player task.

        Parameters
        ----------
        source:
            The new audio source to read from.
        """
        self.pause()
        self.source.cleanup()
        self.source = source
        self.resume()


AudioSourceInput = AudioSource | str | os.PathLike | bytes | bytearray | memoryview | io.IOBase | AsyncIterable[bytes]
""" The set of inputs accepted as audio sources by :meth:`VoiceClient.play`. """


def _resolve_source(audio: object) -> AudioSource:
    """
    Coerce arbitrary audio input into an :class:`AudioSource`.

    Parameters
    ----------
    audio:
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
