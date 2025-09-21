import logging
import re
import sys
import struct
import zlib
import binascii
import traceback
import unicodedata

from base64 import b64encode
from collections.abc import Iterator
from datetime import datetime, timedelta, UTC
from types import UnionType
from typing import Any, TYPE_CHECKING, get_origin, get_args, Union

from .file import File

if TYPE_CHECKING:
    from .object import Snowflake

DISCORD_EPOCH = 1420070400000

# RegEx patterns
re_channel: re.Pattern = re.compile(r"<#([0-9]{15,20})>")
re_role: re.Pattern = re.compile(r"<@&([0-9]{15,20})>")
re_mention: re.Pattern = re.compile(r"<@!?([0-9]{15,20})>")
re_emoji: re.Pattern = re.compile(r"<(a)?:([a-zA-Z0-9_]+):([0-9]{15,20})>")
re_hex = re.compile(r"^(?:#)?(?:[0-9a-fA-F]{3}){1,2}$")
re_jump_url: re.Pattern = re.compile(
    r"https:\/\/(?:.*\.)?discord\.com\/channels\/([0-9]{15,20}|@me)\/([0-9]{15,20})(?:\/([0-9]{15,20}))?"
)


def create_missing_texture(*, size: int = 256, tiles: int = 8) -> bytes:
    """
    Generate a PNG image of the classic magenta and black checkerboard pattern.

    Parameters
    ----------
    size:
        The width and height of the image, in pixels, defaults to 256
    tiles:
        The number of tiles across and down the image, defaults to 8

    Returns
    -------
        The PNG image as bytes
    """
    # Dear code reviewer;
    # Yes, I am fully aware that Pillow can do this much easier.
    # However, I do not want to add a dependency just for this.
    magenta = (0xFF, 0x00, 0xFF, 0xFF)
    black = (0x00, 0x00, 0x00, 0xFF)

    def chunk(t: bytes, d: bytes) -> bytes:
        """ Create a PNG chunk. """
        return (
            struct.pack(">I", len(d)) + t + d +
            struct.pack(">I", binascii.crc32(t + d) & 0xFFFFFFFF)
        )

    w = h = size
    tile = max(1, w // tiles)

    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            color = magenta if ((x // tile + y // tile) & 1) == 0 else black
            raw += bytes(color)

    compressed = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)

    return (
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", ihdr) +
        chunk(b"IDAT", compressed) +
        chunk(b"IEND", b"")
    )


def traceback_maker(
    err: Exception,
    advance: bool = True
) -> str:
    """
    Takes a traceback from an error and returns it as a string.

    Useful if you wish to get traceback in any other forms than the console

    Parameters
    ----------
    err:
        The error to get the traceback from
    advance:
        Whether to include the traceback or not

    Returns
    -------
        The traceback of the error
    """
    traceback_ = "".join(traceback.format_tb(err.__traceback__))
    error = f"{traceback_}{type(err).__name__}: {err}"
    return error if advance else f"{type(err).__name__}: {err}"


def unwrap_optional(annotation: type) -> type:
    """
    Unwraps Optional[T] to T.

    Parameters
    ----------
    annotation:
        The annotation to unwrap, usually a type hint.

    Returns
    -------
        The unwrapped annotation
    """
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        args = get_args(annotation)
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return non_none_args[0]
    return annotation


def snowflake_time(
    id: "Snowflake | int"  # noqa: A002
) -> datetime:
    """
    Get the datetime from a discord snowflak.

    Parameters
    ----------
    id:
        The snowflake to get the datetime from

    Returns
    -------
        The datetime of the snowflake
    """
    return datetime.fromtimestamp(
        ((int(id) >> 22) + DISCORD_EPOCH) / 1000,
        tz=UTC
    )


def time_snowflake(
    dt: datetime,
    *,
    high: bool = False
) -> int:
    """
    Get a discord snowflake from a datetime.

    Parameters
    ----------
    dt:
        The datetime to get the snowflake from
    high:
        Whether to get the high snowflake or not

    Returns
    -------
        The snowflake of the datetime

    Raises
    ------
    `TypeError`
        Wrong timestamp type provided
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"dt must be a datetime object, got {type(dt)} instead")

    return (
        int(dt.timestamp() * 1000 - DISCORD_EPOCH) << 22 +
        (2 ** 22 - 1 if high else 0)
    )


def parse_time(ts: str | int) -> datetime:
    """
    Parse a timestamp from a string or int.

    Parameters
    ----------
    ts:
        The timestamp to parse

    Returns
    -------
        The datetime of the timestamp

    Raises
    ------
    `TypeError`
        If the provided timestamp is not a string or int
    """
    if isinstance(ts, int):
        ts_length = len(str(ts))
        if ts_length >= 16:  # Microseconds
            ts = ts // 1_000_000
        elif ts_length >= 13:  # Milliseconds
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=UTC)

    if isinstance(ts, str):
        return datetime.fromisoformat(ts)

    raise TypeError("ts must be a str or int")


def normalize_entity_id(
    entry: "datetime | int | str | Snowflake"
) -> int:
    """
    Translates a search ID or datetime to a Snowflake.

    Mostly used for audit-logs, messages, and similar API calls

    Parameters
    ----------
    entry:
        The entry to translate

    Returns
    -------
        The translated

    Raises
    ------
    `TypeError`
        If the entry is not a datetime, int, str, or Snowflake
    """
    match entry:
        case x if isinstance(x, int):
            return x

        case x if getattr(x, "id", None):
            # This is potentially a Snowflake
            # Due to circular imports, can't 100% check it, just trust it
            return int(x)  # type: ignore

        case x if isinstance(x, str):
            if not x.isdigit():
                raise TypeError("Got a string that was not a Snowflake ID")
            return int(x)

        case x if isinstance(x, datetime):
            return time_snowflake(x)

        case _:
            raise TypeError(f"Expected datetime, int, str, or Snowflake, got {type(entry)}")


def unicode_name(text: str) -> str:
    """
    Get the unicode name of a string.

    Parameters
    ----------
    text:
        The text to get the unicode name from

    Returns
    -------
        The unicode name of the text
    """
    try:
        output = unicodedata.name(text)
    except TypeError:
        pass
    else:
        output = output.replace(" ", "_")

    return text


def oauth_url(
    client_id: "Snowflake | int",
    /,
    scope: str | None = None,
    user_install: bool = False,
    **kwargs: str
) -> str:
    """
    Get the oauth url of a user.

    Parameters
    ----------
    client_id:
        Application ID to invite to the server
    scope:
        Changing the scope of the oauth url, default: `bot+applications.commands`
    user_install:
        Whether the bot is allowed to be installed on the user's account
    kwargs:
        The query parameters to add to the url

    Returns
    -------
        The oauth url of the user
    """
    output = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={int(client_id)}"
    )

    output += (
        "&scope=bot+applications.commands"
        if scope is None else f"&scope={scope}"
    )

    if user_install:
        output += "&interaction_type=1"

    for key, value in kwargs.items():
        output += f"&{key}={value}"

    return output


def divide_chunks(
    array: list[Any],
    n: int
) -> list[list[Any]]:
    """
    Divide a list into chunks.

    Parameters
    ----------
    array:
        The list to divide
    n:
        The amount of chunks to divide the list into

    Returns
    -------
        The divided list
    """
    return [
        array[i:i + n]
        for i in range(0, len(array), n)
    ]


def utcnow() -> datetime:
    """
    Alias for `datetime.now(UTC)`.

    Returns
    -------
        The current time in UTC
    """
    return datetime.now(UTC)


def add_to_datetime(
    ts: datetime | timedelta | int
) -> datetime:
    """
    Converts different Python timestamps to a `datetime` object.

    Parameters
    ----------
    ts:
        The timestamp to convert
        - `datetime`: Returns the datetime, but in UTC format
        - `timedelta`: Adds the timedelta to the current time
        - `int`: Adds seconds to the current time

    Returns
    -------
        The timestamp in UTC format

    Raises
    ------
    `ValueError`
        `datetime` object must be timezone aware
    `TypeError`
        Invalid type for timestamp provided
    """
    now = utcnow()

    match ts:
        case x if isinstance(x, datetime):
            if x.tzinfo is None:
                raise ValueError(
                    "datetime object must be timezone aware"
                )

            if x.tzinfo is UTC:
                return x

            return x.astimezone(UTC)

        case x if isinstance(x, timedelta):
            return now + x

        case x if isinstance(x, int):
            return now + timedelta(seconds=x)

        case _:
            raise TypeError(
                "Invalid type for timestamp, expected "
                f"datetime, timedelta or int, got {type(ts)} instead"
            )


def mime_type_image(image: bytes) -> str:
    """
    Get the mime type of an image.

    Parameters
    ----------
    image:
        The image to get the mime type from

    Returns
    -------
        The mime type of the image

    Raises
    ------
    `ValueError`
        The image bytes provided is not supported sadly
    """
    match image:
        case x if x.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"

        case x if x.startswith(b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"):
            return "image/png"

        case x if x.startswith((
            b"\x47\x49\x46\x38\x37\x61",
            b"\x47\x49\x46\x38\x39\x61"
        )):
            return "image/gif"

        case x if x.startswith(b"RIFF") and x[8:12] == b"WEBP":
            return "image/webp"

        case _:
            raise ValueError("Image bytes provided is not supported sadly")


def mime_type_audio(audio: bytes) -> str:
    """
    Get the mime type of an audio.

    Parameters
    ----------
    audio:
        The audio to get the mime type from

    Returns
    -------
        The mime type of the audio

    Raises
    ------
    `ValueError`
        The audio bytes provided is not supported sadly
    """
    match audio:
        case x if x.startswith(b"OggS"):
            return "audio/ogg"

        case x if (
            x.startswith((b"ID3", b"\xff\xd8\xff")) or
            (x[0] == 255 and x[1] & 224 == 224)
        ):
            return "audio/mpeg"

        case _:
            raise ValueError("Audio bytes provided is not supported sadly")


def bytes_to_base64(image: File | bytes) -> str:
    """
    Convert bytes to base64.

    Parameters
    ----------
    image:
        The image to convert to base64

    Returns
    -------
        The base64 of the image

    Raises
    ------
    `ValueError`
        The image provided is not supported sadly
    """
    if isinstance(image, File):
        image = image.data.read()
    elif isinstance(image, bytes):
        pass
    else:
        raise ValueError(
            "Attempted to parse bytes, was expecting "
            f"File or bytes, got {type(image)} instead."
        )

    return (
        f"data:{mime_type_image(image)};"
        f"base64,{b64encode(image).decode('ascii')}"
    )


def get_int(
    data: dict,
    key: str,
    *,
    default: Any | None = None  # noqa: ANN401
) -> int | None:
    """
    Get an integer from a dictionary, similar to `dict.get`.

    Parameters
    ----------
    data:
        The dictionary to get the integer from
    key:
        The key to get the integer from
    default:
        The default value to return if the key is not found

    Returns
    -------
        The integer from the dictionary

    Raises
    ------
    `ValueError`
        The key returned a non-digit value
    """
    output: str | None = data.get(key)
    if output is None:
        return default
    if isinstance(output, int):
        return output
    if not output.isdigit():
        raise ValueError(f"Key {key} returned a non-digit value")
    return int(output)


class DiscordTimestamp:
    """
    A class to represent a Discord timestamp.

    This takes a datetime, int or timedelta and
    converts it to a Discord timestamp.
    """
    def __init__(self, ts: int | datetime | timedelta):
        self._ts = ts
        if isinstance(ts, datetime):
            self._ts = int(ts.timestamp())
        elif isinstance(ts, timedelta):
            self._ts = int((utcnow() + ts).timestamp())

        if not isinstance(self._ts, int):
            raise TypeError("ts must be an int, datetime or timedelta")

    def __str__(self) -> str:
        return self.default

    def __int__(self) -> int:
        if not isinstance(self._ts, int):
            raise TypeError("ts somehow manged to be a non-int")

        return self._ts

    def __repr__(self) -> str:
        return f"<DiscordTimestamp ts={self._ts}>"

    def _fmt(self, fmt: str | None = None) -> str:
        """
        Returns the timestamp in a specified format.

        Mostly used internally, but can be used externally I guess..?

        Parameters
        ----------
        fmt:
            The format to return the timestamp in

        Returns
        -------
            The timestamp in the specified format for Discord
        """
        if fmt is None:
            return f"<t:{self._ts}>"
        return f"<t:{self._ts}:{fmt}>"

    @property
    def default(self) -> str:
        """ Returned format: 31. January 2000 16:01. """
        return self._fmt()

    @property
    def short_time(self) -> str:
        """ Returned format: 16:01. """
        return self._fmt("t")

    @property
    def long_time(self) -> str:
        """ Returned format: 16:01:02. """
        return self._fmt("T")

    @property
    def short_date(self) -> str:
        """ Returned format: 31/01/2000. """
        return self._fmt("d")

    @property
    def long_date(self) -> str:
        """ Returned format: 31. January 2000. """
        return self._fmt("D")

    @property
    def short_date_time(self) -> str:
        """ Returned format: 31. January 2000 16:01. """
        return self._fmt("f")

    @property
    def long_date_time(self) -> str:
        """ Returned format: Monday 31. January 2000 16:01. """
        return self._fmt("F")

    @property
    def relative_time(self) -> str:
        """ 21 years ago. """
        return self._fmt("R")


class _MissingType:
    """
    A class to represent a missing value in a dictionary.

    This is used in favour of accepting None as a value

    It is also filled with a bunch of methods to make it
    more compatible with other types and make pyright happy
    """
    def __init__(self) -> None:
        self.id: int = -1

    def __hash__(self) -> int:
        return 0

    def __str__(self) -> str:
        return ""

    def __int__(self) -> int:
        return -1

    def __next__(self) -> None:
        return None

    def __iter__(self) -> Iterator:
        return self

    def __dict__(self) -> dict:
        return {}

    def items(self) -> dict:
        return {}

    def __bytes__(self) -> bytes:
        return b""

    def __eq__(self, other) -> bool:  # noqa: ANN001
        return False

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<MISSING>"


MISSING: Any = _MissingType()


class CustomFormatter(logging.Formatter):
    reset = "\x1b[0m"

    # Normal colours
    white = "\x1b[38;21m"
    grey = "\x1b[38;5;240m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"

    # Light colours
    light_white = "\x1b[38;5;250m"
    light_grey = "\x1b[38;5;244m"
    light_blue = "\x1b[38;5;75m"
    light_yellow = "\x1b[38;5;229m"
    light_red = "\x1b[38;5;203m"
    light_bold_red = "\x1b[38;5;197m"

    def __init__(self, datefmt: str | None = None):
        super().__init__()
        self._datefmt = datefmt

    def _prefix_fmt(
        self,
        name: str,
        primary: str,
        secondary: str
    ) -> str:
        # Cut name if longer than 5 characters
        # If shorter, right-justify it to 5 characters
        name = name[:5].rjust(5)

        return (
            f"{secondary}[ {primary}{name}{self.reset} "
            f"{secondary}]{self.reset}"
        )

    def format(self, record: logging.LogRecord) -> str:
        """ Format the log. """
        match record.levelno:
            case logging.DEBUG:
                prefix = self._prefix_fmt(
                    "DEBUG", self.grey, self.light_grey
                )

            case logging.INFO:
                prefix = self._prefix_fmt(
                    "INFO", self.blue, self.light_blue
                )

            case logging.WARNING:
                prefix = self._prefix_fmt(
                    "WARN", self.yellow, self.light_yellow
                )

            case logging.ERROR:
                prefix = self._prefix_fmt(
                    "ERROR", self.red, self.light_red
                )

            case logging.CRITICAL:
                prefix = self._prefix_fmt(
                    "CRIT", self.bold_red, self.light_bold_red
                )

            case _:
                prefix = self._prefix_fmt(
                    "OTHER", self.white, self.light_white
                )

        formatter = logging.Formatter(
            f"{prefix} {self.grey}%(asctime)s{self.reset} "
            f"%(message)s{self.reset}",
            datefmt=self._datefmt
        )

        return formatter.format(record)


def setup_logger(
    *,
    level: int = logging.INFO
) -> None:
    """
    Setup the logger.

    Parameters
    ----------
    level:
        The level of the logger
    """
    lib, _, _ = __name__.partition(".")
    logger = logging.getLogger(lib)

    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)
