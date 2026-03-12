import aiohttp
import asyncio
import errno
import logging
import orjson
import random
import re
import sys

from aiohttp.client_exceptions import ContentTypeError
from collections.abc import AsyncIterator
from multidict import CIMultiDictProxy
from typing import Any, Self, overload, Literal, TypeVar, Generic, TYPE_CHECKING
from urllib.parse import quote as url_quote

from . import __version__
from .flags import ApplicationFlags
from .errors import (
    NotFound, DiscordServerError,
    Forbidden, HTTPException, Ratelimited,
    AutomodBlock
)

from .gateway.flags import Intents

if TYPE_CHECKING:
    from .client import Client
    from .user import Application

MethodTypes = Literal["GET", "POST", "DELETE", "PUT", "HEAD", "PATCH", "OPTIONS"]
ResMethodTypes = Literal["text", "read", "json"]
ResponseT = TypeVar("ResponseT")

_log = logging.getLogger(__name__)

ratelimit_bucket_re = re.compile(
    r"/(messages|members|roles|emojis|stickers|permissions|reactions|interactions)/([^/]+)"
)

__all__ = (
    "DiscordAPI",
    "HTTPResponse",
)


class HTTPSession(aiohttp.ClientSession):
    """ A subclass of aiohttp.ClientSession that ensures the session is properly closed. """

    __slots__ = ()

    async def __aexit__(self, *args) -> None:  # noqa: ANN002
        if not self.closed:
            await self.close()


class HTTPResponse(Generic[ResponseT]):
    """ Represents a response from the HTTP request. """

    __slots__ = (
        "headers",
        "reason",
        "res_method",
        "response",
        "status",
    )

    def __init__(
        self,
        *,
        status: int,
        response: ResponseT,
        reason: str | None,
        res_method: ResMethodTypes,
        headers: CIMultiDictProxy[str],
    ):
        self.status = status
        """ The HTTP status code of the response. """

        self.response = response
        """ The response data, which can be of type str, bytes, or dict depending on the request. """

        self.res_method = res_method
        """ The method used to retrieve the response data. """

        self.reason = reason
        """ The reason phrase returned by the server, if any. """

        self.headers = headers
        """ The headers of the response, as a CIMultiDictProxy. """

    def __repr__(self) -> str:
        return (
            f"<HTTPResponse status={self.status} "
            f"res_method='{self.res_method}'>"
        )


class HTTPClient:
    """
    Used to make HTTP requests, but with a session.

    Can be used to make requests outside of the usual Discord API
    """

    __slots__ = ("session",)

    def __init__(self):
        self.session: HTTPSession | None = None
        """ The aiohttp session used for making requests. """

    async def _create_session(self) -> None:
        """ Creates a new session for the library. """
        if self.session:
            await self.session.close()

        self.session = HTTPSession(
            connector=aiohttp.TCPConnector(limit=0),
            timeout=aiohttp.ClientTimeout(total=60),
            cookie_jar=aiohttp.DummyCookieJar(),
            # orjson.dumps returns bytes, but aiohttp expects str
            json_serialize=lambda obj: orjson.dumps(obj).decode("utf-8")
        )

    async def _close_session(self) -> None:
        """ Closes the session for the library. """
        if self.session:
            await self.session.close()
        self.session = None

    @overload
    async def request(
        self,
        method: MethodTypes,
        url: str,
        *,
        res_method: Literal["text"],
        **kwargs
    ) -> HTTPResponse[str]:
        ...

    @overload
    async def request(
        self,
        method: MethodTypes,
        url: str,
        *,
        res_method: Literal["json"],
        **kwargs
    ) -> HTTPResponse[dict[Any, Any]]:
        ...

    @overload
    async def request(
        self,
        method: MethodTypes,
        url: str,
        *,
        res_method: Literal["read"],
        **kwargs
    ) -> HTTPResponse[bytes]:
        ...

    async def request(
        self,
        method: MethodTypes,
        url: str,
        *,
        res_method: ResMethodTypes | None = "text",
        **kwargs
    ) -> HTTPResponse:
        """
        Make a request using the aiohttp library.

        However, it handles response methods for you

        Parameters
        ----------
        method:
            The HTTP method to use, defaults to GET
        url:
            The URL to make the request to
        res_method:
            The method to use to get the response, defaults to text
        **kwargs:
            The keyword arguments to pass to the aiohttp.ClientSession.request method

        Returns
        -------
            The response from the request
        """
        if not res_method:
            res_method = "text"

        if method.upper() not in MethodTypes.__args__:
            raise ValueError(f"Invalid HTTP method: {method}")

        if res_method.lower() not in ResMethodTypes.__args__:
            raise ValueError(
                f"Invalid res_method: {res_method}, "
                "must be either text, read or json"
            )

        async with self.session.request(method.upper(), str(url), **kwargs) as res:
            match res_method:
                case "read":
                    r = await res.read()

                case "text":
                    r = await res.text()

                case "json":
                    try:
                        r = await res.json(loads=orjson.loads)
                    except ContentTypeError:
                        try:
                            r = orjson.loads(await res.text())
                        except orjson.JSONDecodeError:
                            # Give up trying, something is really wrong...
                            r = await res.text()
                            res_method = "text"

            return HTTPResponse(
                status=res.status,
                response=r,
                res_method=res_method,
                reason=res.reason,
                headers=res.headers
            )

    async def stream_request(
        self,
        method: str,
        url: str,
        *,
        chunk_size: int = 8192,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """
        Make a request and yield the response in chunks to prevent memory spikes.

        Perfect for downloading large files or assets.

        Parameters
        ----------
        method:
            The HTTP method to use (e.g., "GET")
        url:
            The URL to make the request to
        chunk_size:
            The amount of bytes to yield at a time. Defaults to 8KB.
        **kwargs:
            The keyword arguments to pass to the aiohttp.ClientSession.request method

        Yields
        ------
            Chunks of the response as bytes
        """
        if method.upper() not in MethodTypes.__args__:
            raise ValueError(f"Invalid HTTP method: {method}")

        async with self.session.request(method.upper(), str(url), **kwargs) as res:
            if res.status not in range(200, 300):
                error_text = await res.text()
                raise ValueError(f"Stream request failed with status {res.status}: {error_text}")

            async for chunk in res.content.iter_chunked(chunk_size):
                yield chunk


class Ratelimit:
    """ Represents a ratelimit bucket. """

    __slots__ = (
        "_last_request",
        "_lock",
        "_loop",
        "bucket_reset_epoch",
        "expires",
        "in_flight",
        "key",
        "limit",
        "remaining",
        "reset_after",
    )

    def __init__(self, key: str):
        self.key: str = key
        """ The key of the ratelimit bucket, usually in the format "METHOD /path/:id". """

        self.limit: int = 1
        """ The maximum number of requests that can be made in the current bucket window. """

        self.remaining: int = 1
        """ The number of requests remaining in the current bucket window. """

        self.reset_after: float = 0.0
        """ The number of seconds until the bucket resets. """

        self.expires: float | None = None
        """ The epoch time when the bucket expires, or None if it doesn't expire. """

        self.bucket_reset_epoch: float = 0.0
        """ The epoch time when the current bucket window started. """

        self.in_flight: int = 0
        """ The number of requests currently in-flight for this bucket. """

        self._lock: asyncio.Lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._last_request: float = self._loop.time()

    def __repr__(self) -> str:
        return (
            f"<Ratelimit key='{self.key}' limit={self.limit} "
            f"remaining={self.remaining} reset_after={self.reset_after:.2f}>"
        )

    def is_inactive(self) -> bool:
        """ Check if the ratelimit is inactive (5 minutes). """
        return (self._loop.time() - self._last_request) >= 300

    def update(self, response: HTTPResponse) -> None:
        """
        Update the ratelimit information from the response headers.

        Parameters
        ----------
        response:
            The HTTPResponse object to update the ratelimit information from
        """
        self._last_request = self._loop.time()
        headers = response.headers

        reset_epoch_str = headers.get("X-RateLimit-Reset")
        if not reset_epoch_str:
            return

        reset_epoch = float(reset_epoch_str)
        limit = int(headers.get("X-RateLimit-Limit", 1))
        remaining = int(headers.get("X-RateLimit-Remaining", 0))
        reset_after = float(headers.get("X-RateLimit-Reset-After", 0.0))

        unaccounted_in_flight = max(0, self.in_flight - 1)
        calculated_remaining = max(0, remaining - unaccounted_in_flight)

        # New bucket window
        if reset_epoch > self.bucket_reset_epoch + 0.5:
            self.bucket_reset_epoch = reset_epoch
            self.limit = limit
            self.reset_after = reset_after
            self.expires = self._loop.time() + self.reset_after
            self.remaining = calculated_remaining

        # Same bucket window
        elif abs(reset_epoch - self.bucket_reset_epoch) <= 0.5:
            self.remaining = min(self.remaining, calculated_remaining)

    async def __aenter__(self) -> Self:
        # Stay in this loop until a successful token is acquired
        while True:
            async with self._lock:
                now = self._loop.time()

                # Check for bucket reset
                if self.expires and now > self.expires:
                    self.remaining = self.limit
                    self.expires = None

                # If we have remaining tokens, use one and proceed with the request
                if self.remaining > 0:
                    self.remaining -= 1
                    self.in_flight += 1
                    return self

                # No tokens? Calculate wait time
                wait_time = (self.expires - now) if self.expires else 1.0
                _log.debug(f"Ratelimit prevented ({self.key}), waiting {max(wait_time, 0):.2f}s...")

            # Sleep outside the lock so others can at least check the state
            await asyncio.sleep(max(wait_time, 0.1) + 0.1)

    async def __aexit__(self, *args) -> None:  # noqa: ANN002
        """ When a request is done, decrease the in-flight count. """
        async with self._lock:
            self.in_flight -= 1


class DiscordAPI:
    """ The main class for interacting with the Discord API. """

    def __init__(self, *, client: "Client"):
        self.bot: "Client" = client
        """ The client instance that owns this HTTP client. cache: A reference to the client's cache for easy access within HTTP methods. """

        self.cache = self.bot.cache

        # Aliases
        self.token: str = self.bot.token
        """ The bot token used for authentication with the Discord API. """

        self.api_version: int = self.bot.api_version or 10
        """ The version of the Discord API to use for requests. """

        if not isinstance(self.api_version, int):
            raise TypeError("api_version must be an integer")

        self.base_url = self.bot.api_base_url
        """ The base URL for the Discord API. """

        self.api_url: str = f"{self.base_url}/v{self.api_version}"
        """ The full API URL including the version (e.g., "https://discord.com/api/v10"). """

        self.http: HTTPClient = HTTPClient()
        """ The HTTP client used to make requests to the Discord API. """

        self._buckets: dict[str, Ratelimit] = {}

        self._default_headers: dict[str, str] = {
            "User-Agent": "discord.http/{} Python/{} aiohttp/{}".format(
                __version__,
                ".".join(str(i) for i in sys.version_info[:3]),
                aiohttp.__version__
            ),
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }

        # Background tasks
        self.bot.loop.create_task(
            self._cleanup_loop(),
            name="discord.http/cleanup_http_loop"
        )

    async def _cleanup_loop(self) -> None:
        """ A loop that runs every 5 minutes to clean up old ratelimits. """
        while True:
            await asyncio.sleep(300)
            self._clear_old_ratelimits()

    def _clear_old_ratelimits(self) -> None:
        if len(self._buckets) <= 256:
            _log.debug(f"Ratelimit buckets: {len(self._buckets)}, no cleanup needed.")
            return

        to_remove = [
            key for key, bucket in self._buckets.items()
            if bucket.is_inactive()
        ]

        for key in to_remove:
            try:
                del self._buckets[key]
            except KeyError:
                pass

        if to_remove:
            _log.debug(f"Cleaned up {len(to_remove)} old ratelimits, {len(self._buckets)} remaining.")

    def _get_bucket_key(self, method: str, path: str) -> str:
        """
        Get the bucket key for the given method and path.

        Parameters
        ----------
        method:
            The HTTP method to use
        path:
            The path to make the request to

        Returns
        -------
            The bucket key for the given method and path
        """
        # Remove query parameters
        base_path = path.split("?")[0]

        # Replace IDs in the path with :id to create a more general bucket key
        # Each guild has its own bucket, but all channels share the same bucket, etc.
        normalized = ratelimit_bucket_re.sub(r"/\1/:id", base_path)

        # Special case for message deletion, as it has a separate bucket
        if method == "DELETE" and "messages" in normalized:
            normalized += "-delete"

        return f"{method} {normalized}"

    def get_ratelimit(self, key: str) -> Ratelimit:
        """
        Get a ratelimit object from the bucket.

        Parameters
        ----------
        key:
            The key to get the ratelimit for

        Returns
        -------
            The ratelimit object for the given key
        """
        try:
            value = self._buckets[key]
        except KeyError:
            self._buckets[key] = value = Ratelimit(key)

        return value

    def create_jitter(self) -> float:
        """ Simply returns a random float between 0 and 1. """
        return random.random()

    @overload
    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: Literal["json"] = "json",
        retry_codes: list[int] | None = None,
        **kwargs
    ) -> HTTPResponse[dict[Any, Any]]:
        ...

    @overload
    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: Literal["read"] = "read",
        retry_codes: list[int] | None = None,
        **kwargs
    ) -> HTTPResponse[bytes]:
        ...

    @overload
    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: Literal["text"] = "text",
        retry_codes: list[int] | None = None,
        **kwargs
    ) -> HTTPResponse[str]:
        ...

    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: ResMethodTypes = "json",
        retry_codes: list[int] | None = None,
        **kwargs
    ) -> HTTPResponse:
        """
        Make a request to the Discord API.

        Parameters
        ----------
        method:
            Which HTTP method to use
        path:
            The path to make the request to
        res_method:
            The method to use to get the response
        retry_codes:
            The HTTP codes to retry regardless of the response
        **kwargs:
            The keyword arguments to pass to the aiohttp.ClientSession.request method

        Returns
        -------
            The response from the request

        Raises
        ------
        `ValueError`
            Invalid HTTP method
        `DiscordServerError`
            Something went wrong on Discord's end
        `Forbidden`
            You are not allowed to do this
        `NotFound`
            The resource was not found
        `HTTPException`
            Something went wrong
        `RuntimeError`
            Unreachable code, reached max tries (5)
        """
        headers = {
            **self._default_headers,  # Grab default headers
            **kwargs.pop("headers", {})  # Merge with extra headers if any
        }

        if res_method != "json":
            headers.pop("Content-Type", None)

        reason = kwargs.pop("reason", None)
        if reason:
            headers["X-Audit-Log-Reason"] = url_quote(reason)

        # Set the headers after modifications
        kwargs["headers"] = headers

        api_url = self.api_url
        if kwargs.pop("webhook", False):
            api_url = self.base_url

        retry_codes = retry_codes or []

        ratelimit = self.get_ratelimit(
            self._get_bucket_key(method, path)
        )

        http_400_error_table: dict[int, type[HTTPException]] = {
            200000: AutomodBlock,
            200001: AutomodBlock,
        }

        async def _sleep(tries: int) -> None:
            await asyncio.sleep(1 + (tries * 2) + self.create_jitter())

        def _try_json(data: str) -> dict | str:
            response = data
            if isinstance(data, str):
                try:
                    response = orjson.loads(data)
                except orjson.JSONDecodeError:
                    pass
            return response

        for tries in range(5):
            async with ratelimit:
                try:
                    r: HTTPResponse = await self.http.request(
                        method, f"{api_url}{path}",
                        res_method=res_method,
                        **kwargs
                    )
                    ratelimit.update(r)
                    _log.debug(
                        f"HTTP {method.upper()} ({r.status}): {path} "
                        f"({ratelimit.remaining}/{ratelimit.limit}, {ratelimit.reset_after:.2f}s until reset)"
                    )

                    match r.status:
                        case x if x >= 200 and x <= 299:
                            return r

                        case x if x in retry_codes:
                            # Custom retry code

                            if tries > 4:  # Give up after 5 tries
                                raise DiscordServerError(r)

                            # Try again, maybe it will work next time, surely...
                            await _sleep(tries)
                            continue

                        case 429:
                            response = _try_json(r.response)

                            if not isinstance(response, dict):
                                # For cases where you're ratelimited by CloudFlare
                                raise Ratelimited(r)

                            retry_after: float = response.get("retry_after", 1.0)
                            _log.warning(f"Ratelimit hit ({ratelimit.key}), waiting {retry_after}s...")

                            async with ratelimit._lock:
                                ratelimit.remaining = 0
                                ratelimit.expires = ratelimit._loop.time() + retry_after

                            continue

                        case x if x in (500, 502, 503, 504):
                            if tries > 4:  # Give up after 5 tries
                                raise DiscordServerError(r)

                            # Try again, maybe it will work next time, surely...
                            await _sleep(tries)
                            continue

                        case 400:
                            response = _try_json(r.response)
                            if isinstance(response, str):
                                raise http_400_error_table.get(400, HTTPException)(r)
                            raise http_400_error_table.get(
                                response.get("code", 0),
                                HTTPException
                            )(r)

                        case 403:
                            raise Forbidden(r)

                        case 404:
                            raise NotFound(r)

                        case _:
                            raise HTTPException(r)

                except OSError as e:
                    if tries < 4 and e.errno in (errno.ECONNRESET, errno.ECONNABORTED, 54):
                        await _sleep(tries)
                        continue
                    raise

        raise RuntimeError("Unreachable code, reached max tries (5)")

    async def me(self) -> "Application":
        """
        Fetches the bot's user information.

        Returns
        -------
            The bot's user object

        Raises
        ------
        `RuntimeError`
            - If the bot token is not valid
            - If the bot is not allowed to use the some intents
        """
        try:
            r = await self.query("GET", "/applications/@me")
        except HTTPException as e:
            raise RuntimeError(
                "Bot token is not valid, please check your token and try again. "
                f"({e.text})"
            )

        flags = ApplicationFlags(r.response["flags"])
        denied_intents: Intents = Intents(0)

        if (
            self.bot.intents and
            self.bot.enable_gateway
        ):
            if Intents.guild_presences in self.bot.intents and (
                flags.gateway_presence not in flags and
                flags.gateway_presence_limited not in flags
            ):
                denied_intents |= Intents.guild_presences

            if Intents.message_content in self.bot.intents and (
                flags.gateway_message_content not in flags and
                flags.gateway_message_content_limited not in flags
            ):
                denied_intents |= Intents.message_content

            if Intents.guild_members in self.bot.intents and (
                flags.gateway_guild_members not in flags and
                flags.gateway_guild_members_limited not in flags
            ):
                denied_intents |= Intents.guild_members

        if denied_intents != Intents(0):
            raise RuntimeError(
                "You attempted to boot the bot with intents that are not allowed "
                f"by the application. Denied intents: {denied_intents!r}"
            )

        from .user import Application
        return Application(
            state=self,
            data=r.response
        )

    async def _app_command_query(
        self,
        method: MethodTypes,
        guild_id: int | None = None,
        **kwargs
    ) -> HTTPResponse:
        """
        Used to query the application commands.

        Mostly used internally by the library

        Parameters
        ----------
        method:
            The HTTP method to use
        guild_id:
            The guild ID to query the commands for
        **kwargs:
            The keyword arguments to pass to the aiohttp.ClientSession.request method

        Returns
        -------
            The response from the request
        """
        app_id = self.bot.application_id

        if not app_id:
            raise ValueError("application_id is required to sync commands")

        url = f"/applications/{app_id}/commands"
        if guild_id:
            url = f"/applications/{app_id}/guilds/{guild_id}/commands"

        try:
            r = await self.query(method, url, res_method="json", **kwargs)
        except HTTPException as e:
            r = e.request

        return r

    async def update_commands(
        self,
        data: list[dict] | dict,
        guild_id: int | None = None
    ) -> dict:
        """
        Updates the commands for the bot.

        Parameters
        ----------
        data:
            The JSON data to send to Discord API
        guild_id:
            The guild ID to update the commands for (if None, commands will be global)

        Returns
        -------
            The response from the request
        """
        r = await self._app_command_query(
            "PUT",
            guild_id=guild_id,
            json=data
        )

        target = f"for Guild:{guild_id}" if guild_id else "globally"

        if r.status >= 200 and r.status <= 299:
            _log.info(f"Successfully synced commands {target}")
        else:
            _log.warning(f"Failed to sync commands {target}: {r.response}")

        return r.response

    async def fetch_commands(
        self,
        guild_id: int | None = None
    ) -> dict:
        """
        Fetches the commands for the bot.

        Parameters
        ----------
        guild_id:
            The guild ID to fetch the commands for (if None, commands will be global)

        Returns
        -------
            The response from the request

        Raises
        ------
        `HTTPException`
            If the request returned anything other than 200.
            Typically this means the guild is not found.
        """
        r = await self._app_command_query(
            "GET",
            guild_id=guild_id
        )

        if r.status != 200:
            raise HTTPException(r)

        return r.response
