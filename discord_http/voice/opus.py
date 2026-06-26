import ctypes
import ctypes.util
import logging

from ..errors import OpusError, OpusNotLoaded

__all__ = (
    "OPUS_APPLICATION_AUDIO",
    "OPUS_APPLICATION_LOWDELAY",
    "OPUS_APPLICATION_VOIP",
    "OPUS_SILENCE",
    "SAMPLES_PER_FRAME",
    "SAMPLE_RATE",
    "Decoder",
    "Encoder",
    "OpusError",
    "OpusNotLoaded",
    "is_loaded",
    "load_opus",
)

_log = logging.getLogger(__name__)


# Audio constants, fixed for Discord voice (48kHz stereo, 20ms frames).
SAMPLE_RATE = 48000
""" The sample rate Discord expects, in Hz. """

CHANNELS = 2
""" The number of audio channels Discord expects (stereo). """

FRAME_LENGTH = 20
""" The length of a single audio frame, in milliseconds. """

SAMPLES_PER_FRAME = SAMPLE_RATE // 1000 * FRAME_LENGTH
""" The number of samples per channel in a single 20ms frame (960). """

SAMPLE_SIZE = 2
""" The size of a single sample, in bytes (signed 16-bit). """

FRAME_SIZE = SAMPLES_PER_FRAME * CHANNELS * SAMPLE_SIZE
""" The size of a decoded 20ms PCM frame, in bytes (s16le, stereo). """

OPUS_SILENCE = b"\xf8\xff\xfe"
""" The magic Opus frame that encodes silence. """


# Opus application types.
OPUS_APPLICATION_VOIP = 2048
OPUS_APPLICATION_AUDIO = 2049
OPUS_APPLICATION_LOWDELAY = 2051

# Opus CTL request constants.
OPUS_SET_BITRATE_REQUEST = 4002
OPUS_SET_BANDWIDTH_REQUEST = 4008
OPUS_SET_INBAND_FEC_REQUEST = 4012
OPUS_SET_PACKET_LOSS_PERC_REQUEST = 4014
OPUS_SET_SIGNAL_REQUEST = 4024

# Opus value constants for CTL requests.
OPUS_AUTO = -1000
OPUS_SIGNAL_VOICE = 3001
OPUS_SIGNAL_MUSIC = 3002
OPUS_BANDWIDTH_FULLBAND = 1105

# Opus error codes (used when raising OpusError).
OPUS_OK = 0

# Named aliases that the public set_* helpers accept.
_BANDWIDTHS: dict[str, int] = {
    "auto": OPUS_AUTO,
    "fullband": OPUS_BANDWIDTH_FULLBAND,
}

_SIGNALS: dict[str, int] = {
    "auto": OPUS_AUTO,
    "voice": OPUS_SIGNAL_VOICE,
    "music": OPUS_SIGNAL_MUSIC,
}


# Opaque handle types. libopus only ever hands these back as pointers.
EncoderStruct = ctypes.c_void_p
DecoderStruct = ctypes.c_void_p


class _OpusLoader:
    """ Holds the lazily-loaded libopus handle and its load state on an instance to avoid module-level ``global``. """

    __slots__ = ("attempted", "lib")

    def __init__(self) -> None:
        self.lib: ctypes.CDLL | None = None
        """ The loaded libopus shared library, or ``None`` if unavailable. """

        self.attempted: bool = False
        """ Whether a load has been attempted (so it is not retried endlessly). """


_loader = _OpusLoader()


def _configure_lib(lib: ctypes.CDLL) -> None:
    """ Configure the ``argtypes`` and ``restype`` of every function we bind. """
    lib.opus_strerror.argtypes = [ctypes.c_int]
    lib.opus_strerror.restype = ctypes.c_char_p

    lib.opus_encoder_get_size.argtypes = [ctypes.c_int]
    lib.opus_encoder_get_size.restype = ctypes.c_int

    lib.opus_encoder_create.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.opus_encoder_create.restype = EncoderStruct

    # ``opus_encoder_ctl`` is variadic; arguments are supplied per-call.
    lib.opus_encoder_ctl.restype = ctypes.c_int

    lib.opus_encode.argtypes = [
        EncoderStruct,
        ctypes.POINTER(ctypes.c_int16),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_int32,
    ]
    lib.opus_encode.restype = ctypes.c_int32

    lib.opus_encoder_destroy.argtypes = [EncoderStruct]
    lib.opus_encoder_destroy.restype = None

    lib.opus_decoder_get_size.argtypes = [ctypes.c_int]
    lib.opus_decoder_get_size.restype = ctypes.c_int

    lib.opus_decoder_create.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.opus_decoder_create.restype = DecoderStruct

    # ``opus_decoder_ctl`` is variadic; arguments are supplied per-call.
    lib.opus_decoder_ctl.restype = ctypes.c_int

    lib.opus_decode.argtypes = [
        DecoderStruct,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int16),
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.opus_decode.restype = ctypes.c_int

    lib.opus_decoder_destroy.argtypes = [DecoderStruct]
    lib.opus_decoder_destroy.restype = None

    lib.opus_packet_get_nb_frames.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
    lib.opus_packet_get_nb_frames.restype = ctypes.c_int

    lib.opus_packet_get_samples_per_frame.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
    lib.opus_packet_get_samples_per_frame.restype = ctypes.c_int


def load_opus(name: str | None = None) -> None:
    """ Load libopus and configure all of its bindings. """
    _loader.attempted = True

    location = name
    if location is None:
        location = ctypes.util.find_library("opus")

    if location is None:
        # No library on the system; this is not fatal. The passthrough/E2EE
        # paths can still operate without libopus present.
        _loader.lib = None
        _log.debug("libopus could not be located; Opus encode/decode is unavailable")
        return

    try:
        lib = ctypes.CDLL(location)
        _configure_lib(lib)
    except (OSError, AttributeError) as exc:
        _loader.lib = None
        if name is not None:
            # The caller explicitly asked for this library, so surface failure.
            raise OpusError(f"Could not load libopus from {location!r}") from exc
        _log.warning(f"Found libopus at {location!r} but failed to load it: {exc}")
        return

    _loader.lib = lib
    _log.debug(f"Successfully loaded libopus from {location!r}")


def is_loaded() -> bool:
    """ Whether libopus is currently loaded, attempting a lazy load once if not yet tried. """
    if not _loader.attempted:
        load_opus()

    return _loader.lib is not None


def _get_lib() -> ctypes.CDLL:
    """ Return the loaded libopus library, loading it lazily if needed. """
    if not _loader.attempted:
        load_opus()

    if _loader.lib is None:
        raise OpusNotLoaded("libopus is not loaded; install the Opus shared library to use voice encode/decode")

    return _loader.lib


def _strerror(code: int) -> str:
    """ Resolve a libopus error code into a human-readable string. """
    lib = _loader.lib
    if lib is None:
        return f"error code {code}"

    message: bytes | None = lib.opus_strerror(code)
    if message is None:
        return f"error code {code}"

    return message.decode("utf-8", "replace")


def _as_ubyte_ptr(data: bytes) -> "ctypes._Pointer[ctypes.c_ubyte]":
    """ Copy ``data`` into a ctypes buffer and return a ``c_ubyte`` pointer to it. """
    buffer = ctypes.create_string_buffer(bytes(data), len(data))
    return ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))


def _as_int16_ptr(data: bytes) -> "ctypes._Pointer[ctypes.c_int16]":
    """ Copy ``data`` into a ctypes buffer and return a ``c_int16`` pointer to it. """
    buffer = ctypes.create_string_buffer(bytes(data), len(data))
    return ctypes.cast(buffer, ctypes.POINTER(ctypes.c_int16))


def _check(code: int) -> int:
    """ Raise :class:`OpusError` if ``code`` indicates a libopus failure, else return ``code``. """
    if code < OPUS_OK:
        raise OpusError(_strerror(code))

    return code


class Encoder:
    """ A libopus encoder configured for Discord voice (48kHz, stereo). """

    def __init__(self, application: int = OPUS_APPLICATION_AUDIO):
        # Set first so __del__ is safe even if _get_lib() raises below.
        self._state: int = 0
        self._lib: ctypes.CDLL = _get_lib()
        self.application = application
        """ The Opus application type the encoder was created with. """

        error = ctypes.c_int()
        state: int = self._lib.opus_encoder_create(
            ctypes.c_int(SAMPLE_RATE),
            ctypes.c_int(CHANNELS),
            ctypes.c_int(application),
            ctypes.byref(error),
        )

        _check(error.value)
        self._state = state

    def __del__(self) -> None:
        self.cleanup()

    def _ctl(self, request: int, value: int) -> int:
        """ Issue a CTL request to the encoder. """
        return _check(self._lib.opus_encoder_ctl(self._state, ctypes.c_int(request), ctypes.c_int(value)))

    def set_bitrate(self, kbps: int) -> None:
        """ Set the target bitrate, in kilobits per second. """
        clamped = min(512, max(16, kbps))
        self._ctl(OPUS_SET_BITRATE_REQUEST, clamped * 1024)

    def set_fec(self, enabled: bool) -> None:
        """ Enable or disable in-band forward error correction. """
        self._ctl(OPUS_SET_INBAND_FEC_REQUEST, 1 if enabled else 0)

    def set_expected_packet_loss_percent(self, pct: float) -> None:
        """ Set the expected packet-loss percentage (as a fraction between 0 and 1) used to tune FEC. """
        value = min(100, max(0, int(pct * 100)))
        self._ctl(OPUS_SET_PACKET_LOSS_PERC_REQUEST, value)

    def set_bandwidth(self, name: str) -> None:
        """ Set the encoder bandwidth, one of ``auto`` or ``fullband``. """
        self._ctl(OPUS_SET_BANDWIDTH_REQUEST, _BANDWIDTHS[name])

    def set_signal_type(self, name: str) -> None:
        """ Set the signal type hint, one of ``auto``, ``voice`` or ``music``. """
        self._ctl(OPUS_SET_SIGNAL_REQUEST, _SIGNALS[name])

    def encode(self, pcm: bytes, frame_size: int = SAMPLES_PER_FRAME) -> bytes:
        """ Encode a single frame of s16le stereo PCM audio into an Opus packet. """
        max_data_bytes = len(pcm)
        pcm_ptr = _as_int16_ptr(pcm)
        output = (ctypes.c_ubyte * max_data_bytes)()

        result: int = self._lib.opus_encode(
            self._state,
            pcm_ptr,
            ctypes.c_int(frame_size),
            ctypes.cast(output, ctypes.POINTER(ctypes.c_ubyte)),
            ctypes.c_int32(max_data_bytes),
        )

        _check(result)

        return bytes(output[:result])

    def cleanup(self) -> None:
        """ Free the underlying libopus encoder. """
        if self._state:
            self._lib.opus_encoder_destroy(self._state)
            self._state = 0


class Decoder:
    """ A libopus decoder configured for Discord voice (48kHz, stereo). """

    def __init__(self):
        # Set first so __del__ is safe even if _get_lib() raises below.
        self._state: int = 0
        self._lib: ctypes.CDLL = _get_lib()

        error = ctypes.c_int()
        state: int = self._lib.opus_decoder_create(
            ctypes.c_int(SAMPLE_RATE),
            ctypes.c_int(CHANNELS),
            ctypes.byref(error),
        )

        _check(error.value)
        self._state = state

    def __del__(self) -> None:
        self.cleanup()

    @staticmethod
    def packet_get_nb_frames(data: bytes) -> int:
        """ Return the number of frames in an Opus packet. """
        lib = _get_lib()
        data_ptr = _as_ubyte_ptr(data)
        return _check(lib.opus_packet_get_nb_frames(data_ptr, ctypes.c_int(len(data))))

    @staticmethod
    def packet_get_samples_per_frame(data: bytes) -> int:
        """ Return the number of samples per channel in each frame of an Opus packet. """
        lib = _get_lib()
        data_ptr = _as_ubyte_ptr(data)
        return _check(lib.opus_packet_get_samples_per_frame(data_ptr, ctypes.c_int(SAMPLE_RATE)))

    def decode(self, data: bytes | None, *, fec: bool = False) -> bytes:
        """ Decode an Opus packet into s16le stereo PCM, or ``None`` for packet-loss concealment. """
        if data is None:
            frame_size = SAMPLES_PER_FRAME
            data_ptr: "ctypes._Pointer[ctypes.c_ubyte] | None" = None
            data_len = 0
        else:
            frames = self.packet_get_nb_frames(data)
            samples_per_frame = self.packet_get_samples_per_frame(data)
            frame_size = frames * samples_per_frame
            data_ptr = _as_ubyte_ptr(data)
            data_len = len(data)

        pcm = (ctypes.c_int16 * (frame_size * CHANNELS))()

        result: int = self._lib.opus_decode(
            self._state,
            data_ptr,
            ctypes.c_int32(data_len),
            ctypes.cast(pcm, ctypes.POINTER(ctypes.c_int16)),
            ctypes.c_int(frame_size),
            ctypes.c_int(1 if fec else 0),
        )

        _check(result)

        return bytes(bytearray(pcm)[: result * CHANNELS * SAMPLE_SIZE])

    def cleanup(self) -> None:
        """ Free the underlying libopus decoder. """
        if self._state:
            self._lib.opus_decoder_destroy(self._state)
            self._state = 0
