import abc
import io
import logging
import os
import wave

from collections.abc import Callable
from dataclasses import dataclass

__all__ = (
    "AudioSink",
    "CallbackSink",
    "VoiceData",
    "WaveSink",
)

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class VoiceData:
    """ Represents a single chunk of received voice audio for one speaker. """

    user: int | None
    """ The user ID this audio belongs to, or ``None`` if unknown. """

    pcm: bytes | None
    """ The decoded 48kHz 16-bit stereo PCM payload, if available. """

    opus: bytes | None
    """ The raw Opus payload, if available. """

    timestamp: int
    """ The RTP timestamp of the packet this data came from. """

    ssrc: int
    """ The RTP SSRC of the sender this data came from. """


class AudioSink(abc.ABC):
    """ Abstract base class for consumers of received voice audio. """

    def wants_opus(self) -> bool:
        """
        Whether this sink wants raw Opus payloads instead of decoded PCM.

        When ``False`` (the default) the receiver decodes packets to PCM
        before handing them to :meth:`write`.

        Returns
        -------
            ``True`` if the sink consumes Opus, ``False`` for PCM
        """
        return False

    @abc.abstractmethod
    def write(self, user: int | None, data: VoiceData) -> None:
        """
        Consume a single chunk of received voice audio.

        Parameters
        ----------
        user:
            The user ID the audio belongs to, or ``None`` if unknown
        data:
            The voice data container holding the PCM and/or Opus payload
        """
        raise NotImplementedError

    def cleanup(self) -> None:
        """ Finalize the sink, flushing and releasing any held resources. """
        return


class CallbackSink(AudioSink):
    """ Audio sink that forwards every received chunk to a callback. """

    def __init__(
        self,
        callback: Callable[[int | None, VoiceData], object],
        *,
        opus: bool = False
    ) -> None:
        """
        Create a sink that forwards received audio to a callback.

        Parameters
        ----------
        callback:
            The callable invoked as ``callback(user, data)`` for each chunk
        opus:
            Whether to request raw Opus payloads instead of decoded PCM
        """
        self.callback = callback
        self.opus = opus

    def wants_opus(self) -> bool:
        """
        Whether this sink wants raw Opus payloads instead of decoded PCM.

        Returns
        -------
            The value of the ``opus`` flag passed at construction
        """
        return self.opus

    def write(self, user: int | None, data: VoiceData) -> None:
        """
        Forward the received audio chunk to the callback.

        Parameters
        ----------
        user:
            The user ID the audio belongs to, or ``None`` if unknown
        data:
            The voice data container holding the PCM and/or Opus payload
        """
        self.callback(user, data)


class WaveSink(AudioSink):
    """
    Audio sink that writes received PCM to a single 48kHz 16-bit stereo WAV file.

    All speakers are mixed into a single stream; the ``user`` argument to
    :meth:`write` is ignored, so per-speaker separation is not preserved.
    """

    def __init__(self, destination: str | os.PathLike | io.IOBase) -> None:
        """
        Create a sink that writes received PCM to a WAV file.

        Parameters
        ----------
        destination:
            A file path or writable binary stream to receive the WAV data
        """
        self.destination = destination
        self._file: wave.Wave_write | None = None

    def wants_opus(self) -> bool:
        """
        Whether this sink wants raw Opus payloads instead of decoded PCM.

        Returns
        -------
            Always ``False`` as the WAV file stores PCM
        """
        return False

    def _ensure_open(self) -> wave.Wave_write:
        """ Open the wave file lazily, configuring it for 48kHz 16-bit stereo. """
        file = self._file
        if file is None:
            file = wave.open(self.destination, "wb")  # type: ignore[arg-type]  # noqa: SIM115
            file.setnchannels(2)
            file.setsampwidth(2)
            file.setframerate(48000)
            self._file = file
        return file

    def write(self, user: int | None, data: VoiceData) -> None:  # noqa: ARG002
        """
        Append the chunk's PCM payload to the WAV file.

        Parameters
        ----------
        user:
            The user ID the audio belongs to, or ``None`` if unknown (unused;
            all speakers are mixed into the same WAV stream)
        data:
            The voice data container holding the PCM payload
        """
        if data.pcm is None:
            return
        self._ensure_open().writeframes(data.pcm)

    def cleanup(self) -> None:
        """ Finalize the WAV file, writing headers and closing the stream. """
        if self._file is not None:
            self._file.close()
            self._file = None
