import logging
import re
import sys
import traceback
import unicodedata

from base64 import b64encode
from datetime import datetime, timedelta, UTC
from typing import Optional, Any, Union, Iterator, TYPE_CHECKING

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


def traceback_maker(
    err: Exception,
    advance: bool = True
) -> str:
    """
    Takes a traceback from an error and returns it as a string

    Useful if you wish to get traceback in any other forms than the console

    Parameters
    ----------
    err: `Exception`
        The error to get the traceback from
    advance: `bool`
        Whether to include the traceback or not

    Returns
    -------
    `str`
        The traceback of the error
    """
    _traceback = "".join(traceback.format_tb(err.__traceback__))
    error = f"{_traceback}{type(err).__name__}: {err}"
    return error if advance else f"{type(err).__name__}: {err}"


def snowflake_time(id: Union["Snowflake", int]) -> datetime:
    """
    Get the datetime from a discord snowflake

    Parameters
    ----------
    id: `int`
        The snowflake to get the datetime from

    Returns
    -------
    `datetime`
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
    Get a discord snowflake from a datetime

    Parameters
    ----------
    dt: `datetime`
        The datetime to get the snowflake from
    high: `bool`
        Whether to get the high snowflake or not

    Returns
    -------
    `int`
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
    Parse a timestamp from a string or int

    Parameters
    ----------
    ts: `str` | `int`
        The timestamp to parse

    Returns
    -------
    `datetime`
        The datetime of the timestamp

    Raises
    ------
    `TypeError`
        If the provided timestamp is not a string or int
    """
    if isinstance(ts, int):
        if len(str(ts)) >= 13:
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=UTC)
    elif isinstance(ts, str):
        return datetime.fromisoformat(ts)

    raise TypeError("ts must be a str or int")


def normalize_entity_id(
    entry: Union[datetime, int, str, "Snowflake"]
) -> int:
    """
    Translates a search ID or datetime to a Snowflake
    Mostly used for audit-logs, messages, and similar API calls

    Parameters
    ----------
    entry: `Union[datetime, int, str, Snowflake]`
        The entry to translate

    Returns
    -------
    `Snowflake`
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
    Get the unicode name of a string

    Parameters
    ----------
    text: `str`
        The text to get the unicode name from

    Returns
    -------
    `str`
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
    client_id: Union["Snowflake", int],
    /,
    scope: Optional[str] = None,
    user_install: bool = False,
    **kwargs: str
):
    """
    Get the oauth url of a user

    Parameters
    ----------
    client_id: `Union[Snowflake, int]`
        Application ID to invite to the server
    scope: `Optional[str]`
        Changing the scope of the oauth url, default: `bot+applications.commands`
    user_install: `bool`
        Whether the bot is allowed to be installed on the user's account
    kwargs: `str`
        The query parameters to add to the url

    Returns
    -------
    `str`
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
    Divide a list into chunks

    Parameters
    ----------
    array: `list[Any]`
        The list to divide
    n: `int`
        The amount of chunks to divide the list into

    Returns
    -------
    `list[list[Any]]`
        The divided list
    """
    return [
        array[i:i + n]
        for i in range(0, len(array), n)
    ]


def utcnow() -> datetime:
    """
    Alias for `datetime.now(UTC)`

    Returns
    -------
    `datetime`
        The current time in UTC
    """
    return datetime.now(UTC)


def add_to_datetime(
    ts: Union[datetime, timedelta, int]
) -> datetime:
    """
    Converts different Python timestamps to a `datetime` object

    Parameters
    ----------
    ts: `Union[datetime, timedelta, dtime, int]`
        The timestamp to convert
        - `datetime`: Returns the datetime, but in UTC format
        - `timedelta`: Adds the timedelta to the current time
        - `int`: Adds seconds to the current time

    Returns
    -------
    `datetime`
        The timestamp in UTC format

    Raises
    ------
    `ValueError`
        `datetime` object must be timezone aware
    `TypeError`
        Invalid type for timestamp provided
    """
    _now = utcnow()

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
            return _now + x

        case x if isinstance(x, int):
            return _now + timedelta(seconds=x)

        case _:
            raise TypeError(
                "Invalid type for timestamp, expected "
                f"datetime, timedelta or int, got {type(ts)} instead"
            )


def mime_type_image(image: bytes) -> str:
    """
    Get the mime type of an image

    Parameters
    ----------
    image: `bytes`
        The image to get the mime type from

    Returns
    -------
    `str`
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
    Get the mime type of an audio

    Parameters
    ----------
    audio: `bytes`
        The audio to get the mime type from

    Returns
    -------
    `str`
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
            x.startswith(b"ID3") or
            x.startswith(b"\xff\xd8\xff") or
            (x[0] == 0xff and (x[1] & 0xe0) == 0xe0)
        ):
            return "audio/mpeg"

        case _:
            raise ValueError("Audio bytes provided is not supported sadly")


def bytes_to_base64(image: Union[File, bytes]) -> str:
    """
    Convert bytes to base64

    Parameters
    ----------
    image: `Union[File, bytes]`
        The image to convert to base64

    Returns
    -------
    `str`
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
    default: Optional[Any] = None
) -> Optional[int]:
    """
    Get an integer from a dictionary, similar to `dict.get`

    Parameters
    ----------
    data: `dict`
        The dictionary to get the integer from
    key: `str`
        The key to get the integer from
    default: `Optional[Any]`
        The default value to return if the key is not found

    Returns
    -------
    `Optional[int]`
        The integer from the dictionary

    Raises
    ------
    `ValueError`
        The key returned a non-digit value
    """
    output: Optional[str] = data.get(key, None)
    if output is None:
        return default
    if isinstance(output, int):
        return output
    if not output.isdigit():
        raise ValueError(f"Key {key} returned a non-digit value")
    return int(output)


class _MissingType:
    """
    A class to represent a missing value in a dictionary
    This is used in favour of accepting None as a value

    It is also filled with a bunch of methods to make it
    more compatible with other types and make pyright happy
    """
    def __init__(self) -> None:
        self.id: int = -1

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
        return bytes()

    def __eq__(self, other) -> bool:
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

    def __init__(self, datefmt: Optional[str] = None):
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
        """ Format the log """
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
    Setup the logger

    Parameters
    ----------
    level: `Optional[int]`
        The level of the logger
    """
    lib, _, _ = __name__.partition(".")
    logger = logging.getLogger(lib)

    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)
