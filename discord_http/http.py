import aiohttp
import asyncio
import errno
import logging
import orjson
import random
import re
import socket
import ssl
import sys

from aiohttp.client_exceptions import ContentTypeError
from collections.abc import AsyncIterator
from multidict import CIMultiDictProxy
from typing import Any, Self, overload, Literal, TypeVar, Generic, TYPE_CHECKING
from urllib.parse import quote as url_quote

from . import __version__
from .flags import ApplicationFlags
from .utils import MultipartData
from .errors import (
    NotFound, DiscordServerError,
    Forbidden, HTTPException, Ratelimited,
    AutomodBlock, Unauthorized
)

from .gateway.flags import Intents

if TYPE_CHECKING:
    from .client import Client
    from .user import Application

MethodTypes = Literal["GET", "POST", "DELETE", "PUT", "HEAD", "PATCH", "OPTIONS"]
ResMethodTypes = Literal["text", "read", "json"]
ResponseT = TypeVar("ResponseT")

_log = logging.getLogger(__name__)

__all__ = (
    "DiscordAPI",
    "HTTPResponse",
)

_HTTP_400_ERROR_TABLE: dict[int, type[HTTPException]] = {
    200000: AutomodBlock,
    200001: AutomodBlock,
}

_MAJOR_PARAM_ROOTS = ("guilds", "channels", "webhooks", "stage-instances")

major_param_re = re.compile(r"^/(" + "|".join(_MAJOR_PARAM_ROOTS) + r")/(\d+)(?=/|$)")
id_segment_re = re.compile(r"(?<=/)\d+(?=/|$)")


def _try_json(data: str) -> dict | str:
    if isinstance(data, str):
        try:
            return orjson.loads(data)
        except orjson.JSONDecodeError:
            pass
    return data


class HTTPSession(aiohttp.ClientSession):
    """ A subclass of aiohttp.ClientSession that ensures the session is properly closed. """

    __slots__ = ()

    async def __aexit__(self, *args) -> None:  # ruff: ignore[missing-type-args]
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

    __slots__ = ("_timeout", "session",)

    def __init__(self):
        self.session: HTTPSession | None = None
        """ The aiohttp session used for making requests. """

        self._timeout: int = 60
        """ The timeout for HTTP requests, in seconds. """

    async def _create_session(self) -> None:
        """ Creates a new session for the library. """
        if self.session:
            await self.session.close()

        self.session = HTTPSession(
            connector=aiohttp.TCPConnector(
                limit=0,
                ssl=ssl.create_default_context(),
                keepalive_timeout=self._timeout,
                family=socket.AF_INET,
            ),
            timeout=aiohttp.ClientTimeout(total=self._timeout),
            cookie_jar=aiohttp.DummyCookieJar(),
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
        method
            The HTTP method to use, defaults to GET
        url
            The URL to make the request to
        res_method
            The method to use to get the response, defaults to text
        **kwargs
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
        chunk_size: int = 65536,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """
        Make a request and yield the response in chunks to prevent memory spikes.

        Perfect for downloading large files or assets.

        Parameters
        ----------
        method
            The HTTP method to use (e.g., "GET")
        url
            The URL to make the request to
        chunk_size
            The amount of bytes to yield at a time. Defaults to 64KB.
        **kwargs
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
        "bucket_hash",
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

        self.bucket_hash: str | None = None
        """ Discord's own bucket identifier from the `X-RateLimit-Bucket` header, if seen yet. """

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
            f"remaining={self.remaining} reset_after={self.reset_after:.2f} "
            f"bucket_hash={self.bucket_hash!r}>"
        )

    def is_inactive(self) -> bool:
        """ Check if the ratelimit is inactive. """
        if self.in_flight > 0:
            return False
        if self.expires is not None and self._loop.time() < self.expires:
            # Still inside a known cooldown window (e.g. a long 429 retry_after) -
            # evicting now would make the next request start from a fresh,
            # falsely-optimistic bucket and immediately re-trigger the limit.
            return False
        return (self._loop.time() - self._last_request) >= 60

    def update(self, response: HTTPResponse) -> None:
        """
        Update the ratelimit information from the response headers.

        Parameters
        ----------
        response
            The HTTPResponse object to update the ratelimit information from
        """
        self._last_request = self._loop.time()
        headers = response.headers

        new_bucket_hash = headers.get("X-RateLimit-Bucket")
        if (
            new_bucket_hash and
            self.bucket_hash and
            new_bucket_hash != self.bucket_hash
        ):
            _log.debug(
                f"Ratelimit bucket hash changed for key '{self.key}': "
                f"{self.bucket_hash!r} -> {new_bucket_hash!r}"
            )
        if new_bucket_hash:
            self.bucket_hash = new_bucket_hash

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
                if self.expires:
                    wait_time = self.expires - now
                else:
                    # No X-RateLimit-Reset was ever recorded for this bucket (e.g. the
                    # last response was an error like 403 that carries no ratelimit
                    # headers), so there's nothing to actually wait out.
                    self.remaining = self.limit
                    wait_time = 1.0

                _log.debug(f"Ratelimit prevented ({self.key}), waiting {max(wait_time, 0):.2f}s...")

            # Sleep outside the lock so others can at least check the state
            await asyncio.sleep(max(wait_time, 0.1) + 0.1)

    async def __aexit__(self, *args) -> None:  # ruff: ignore[missing-type-args]
        """ When a request is done, decrease the in-flight count. """
        async with self._lock:
            self.in_flight -= 1


class GlobalRatelimit:
    """
    Enforces Discord's global rate limit (50 requests/second per bot token).

    This is independent of and in addition to the per-route buckets above.
    Interaction/webhook execution endpoints are exempt from this per Discord's
    docs, so callers should skip acquiring this for those paths entirely.
    """

    __slots__ = (
        "_lock",
        "_loop",
        "locked_until",
        "max",
        "per",
        "remaining",
        "window",
    )

    def __init__(self, *, max_requests: int = 50, per: float = 1.0):
        self.max: int = max_requests
        """ The maximum number of requests allowed per window. """

        self.per: float = per
        """ The length of the window in seconds. """

        self.remaining: int = max_requests
        """ The number of requests remaining in the current window. """

        self.window: float = 0.0
        """ The epoch time when the current window started. """

        self.locked_until: float | None = None
        """ Set when Discord reports an actual global 429, blocking every request until it passes. """

        self._lock: asyncio.Lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """ Since this class is defined at start, we only fetch it when doing HTTP requests. """
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def acquire(self) -> None:
        """ Blocks until a global request slot is available. """
        loop = self._ensure_loop()

        while True:
            async with self._lock:
                now = loop.time()

                if self.locked_until is not None and now < self.locked_until:
                    wait_time = self.locked_until - now
                else:
                    self.locked_until = None

                    if now - self.window >= self.per:
                        self.remaining = self.max
                        self.window = now

                    if self.remaining > 0:
                        self.remaining -= 1
                        return

                    wait_time = self.per - (now - self.window)

            _log.debug(f"Global ratelimit exhausted, waiting {max(wait_time, 0):.2f}s...")
            await asyncio.sleep(max(wait_time, 0.05))

    def lock_for(self, retry_after: float) -> None:
        """ Called when Discord reports a real global 429, pauses every request until it clears. """
        self.locked_until = self._ensure_loop().time() + retry_after


class DiscordAPI:
    """ The main class for interacting with the Discord API. """

    def __init__(self, *, client: "Client"):
        self.bot: "Client" = client
        """ The client instance that owns this HTTP client. """

        # Aliases
        self.cache = self.bot.cache
        """ Alias to the client's cache, used for caching guilds, users, etc. """

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

        self._default_headers: dict[str, str] = {
            "User-Agent": "discord.http/{} Python/{} aiohttp/{}".format(
                __version__,
                ".".join(str(i) for i in sys.version_info[:3]),
                aiohttp.__version__
            ),
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }

        # Ratelimit handling
        self._buckets: dict[str, Ratelimit] = {}
        self._global_ratelimit: GlobalRatelimit = GlobalRatelimit()
        self._bucket_hashes: dict[str, str] = {}

        # Background tasks
        task = self.bot.loop.create_task(
            self._cleanup_loop(),
            name="discord.http/cleanup_http_loop"
        )
        self.bot._background_tasks.add(task)
        task.add_done_callback(self.bot._cleanup_task)

    async def _cleanup_loop(self) -> None:
        """ A loop that runs periodically to clean up old ratelimits. """
        while True:
            await asyncio.sleep(60)
            self._clear_old_ratelimits()

    def _clear_old_ratelimits(self) -> None:
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

    @staticmethod
    def _apply_bucket_quirks(method: str, normalized: str) -> str:
        """ Route-specific exceptions to the generic id-collapsing rule below. """
        if method == "DELETE" and normalized.endswith("/messages/:id"):
            return normalized + "-delete"
        return normalized

    def _get_bucket_key(self, method: str, path: str) -> str:
        """
        Get the local, path-guessed bucket key for the given method and path.

        Parameters
        ----------
        method
            The HTTP method to use
        path
            The path to make the request to

        Returns
        -------
            The bucket key for the given method and path
        """
        # Remove query parameters
        base_path = path.partition("?")[0]

        # Keep the major param (guild/channel/webhook id) raw, collapse everything else
        if major_match := major_param_re.match(base_path):
            prefix = major_match.group(0)
            remainder = base_path[major_match.end():]
        else:
            prefix = ""
            remainder = base_path

        normalized = self._apply_bucket_quirks(
            method, prefix + id_segment_re.sub(":id", remainder)
        )

        return f"{method} {normalized}"

    def _route_template(self, method: str, path: str) -> str:
        """
        Get the route "shape" for the given method and path, with every id collapsed.

        Parameters
        ----------
        method
            The HTTP method to use
        path
            The path to make the request to

        Returns
        -------
            The route template for the given method and path
        """
        base_path = path.partition("?")[0]
        normalized = self._apply_bucket_quirks(
            method, id_segment_re.sub(":id", base_path)
        )
        return f"{method} {normalized}"

    @staticmethod
    def _major_param_value(path: str) -> str:
        """ The raw major-param id for the given path, or "" if it has none. """
        base_path = path.partition("?")[0]
        return match.group(2) if (match := major_param_re.match(base_path)) else ""

    def _resolve_bucket_key(self, method: str, path: str) -> tuple[str, str]:
        """
        Resolve which route template and actual bucket key a request should use.

        Parameters
        ----------
        method
            The HTTP method to use
        path
            The path to make the request to

        Returns
        -------
            A tuple of `(route_template, bucket_key)`. `route_template` is what
            `_bucket_hashes` should be updated with once a response comes back.
        """
        route_template = self._route_template(method, path)

        if bucket_hash := self._bucket_hashes.get(route_template):
            major_param = self._major_param_value(path)
            key = f"{method} #{bucket_hash}" + (f":{major_param}" if major_param else "")
        else:
            key = self._get_bucket_key(method, path)

        return route_template, key

    def get_ratelimit(self, key: str) -> Ratelimit:
        """
        Get a ratelimit object from the bucket.

        Parameters
        ----------
        key
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
        **kwargs
    ) -> HTTPResponse[str]:
        ...

    async def query(
        self,
        method: MethodTypes,
        path: str,
        *,
        res_method: ResMethodTypes = "json",
        **kwargs
    ) -> HTTPResponse:
        """
        Make a request to the Discord API.

        Parameters
        ----------
        method
            Which HTTP method to use
        path
            The path to make the request to
        res_method
            The method to use to get the response
        **kwargs
            The keyword arguments to pass to the aiohttp.ClientSession.request method

        Returns
        -------
            The response from the request

        Raises
        ------
        ValueError
            Invalid HTTP method
        DiscordServerError
            Something went wrong on Discord's end
        Forbidden
            You are not allowed to do this
        NotFound
            The resource was not found
        Unauthorized
            The bot token is invalid or has been revoked
        HTTPException
            Something went wrong
        """
        extra_headers = kwargs.pop("headers", None)
        headers = (
            {**self._default_headers, **extra_headers}
            if extra_headers else
            dict(self._default_headers)
        )

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

        base_path = path.split("?")[0]
        exempt_from_global = base_path.startswith(("/interactions/", "/webhooks/"))

        # Resolved once per call, reused across retries - resolving fresh per retry
        # could orphan a 429 cooldown if the hash gets learned mid-loop.
        route_template, bucket_key = self._resolve_bucket_key(method, path)
        ratelimit = self.get_ratelimit(bucket_key)

        async def _sleep(tries: int) -> None:
            await asyncio.sleep(1 + (tries * 2) + self.create_jitter())

        error_tries = 0
        ratelimit_tries = 0

        while True:
            body = kwargs.get("data")
            if (error_tries or ratelimit_tries) and isinstance(body, MultipartData):
                # File streams were already consumed by the previous attempt
                body.reset()

            if not exempt_from_global:
                await self._global_ratelimit.acquire()

            async with ratelimit:
                try:
                    r: HTTPResponse = await self.http.request(
                        method, f"{api_url}{path}",
                        res_method=res_method,
                        **kwargs
                    )
                    ratelimit.update(r)

                    if new_bucket_hash := r.headers.get("X-RateLimit-Bucket"):
                        self._bucket_hashes[route_template] = new_bucket_hash

                    _log.debug(
                        "HTTP %s (%s): %s (%s/%s, %.2fs until reset)",
                        method.upper(), r.status, path,
                        ratelimit.remaining, ratelimit.limit, ratelimit.reset_after
                    )

                    match r.status:
                        case x if x >= 200 and x <= 299:
                            return r

                        case 429:
                            response = _try_json(r.response)

                            if not isinstance(response, dict):
                                # For cases where you're ratelimited by CloudFlare
                                raise Ratelimited(r)

                            ratelimit_tries += 1
                            if ratelimit_tries > 10:
                                # something is actually wrong, not just normal throttling
                                _log.error(f"Ratelimit hit ({ratelimit.key}) 10 times in a row, giving up")
                                raise Ratelimited(r)

                            retry_after: float = response.get("retry_after", 1.0)

                            if response.get("global", False):
                                _log.warning(f"Global ratelimit hit, pausing all requests for {retry_after:.2f}s...")
                                self._global_ratelimit.lock_for(retry_after)

                                if exempt_from_global:
                                    await asyncio.sleep(retry_after)
                            else:
                                _log.warning(f"Ratelimit hit ({ratelimit.key}), waiting {retry_after}s...")

                                async with ratelimit._lock:
                                    ratelimit.remaining = 0
                                    ratelimit.expires = ratelimit._loop.time() + retry_after

                            continue

                        case x if x in (500, 502, 503, 504):
                            if error_tries >= 4:  # Give up after 5 tries
                                raise DiscordServerError(r)

                            _log.debug(
                                f"HTTP {method.upper()} {path} got {x}, "
                                f"retrying (attempt {error_tries + 1}/5)..."
                            )

                            # Try again, maybe it will work next time, surely...
                            await _sleep(error_tries)
                            error_tries += 1
                            continue

                        case 400:
                            response = _try_json(r.response)
                            if isinstance(response, str):
                                raise _HTTP_400_ERROR_TABLE.get(400, HTTPException)(r)
                            raise _HTTP_400_ERROR_TABLE.get(
                                response.get("code", 0),
                                HTTPException
                            )(r)

                        case 401:
                            _log.error("HTTP 401: The bot token is invalid or was revoked")
                            raise Unauthorized(r)

                        case 403:
                            raise Forbidden(r)

                        case 404:
                            raise NotFound(r)

                        case _:
                            raise HTTPException(r)

                except OSError as e:
                    if error_tries < 4 and e.errno in (errno.ECONNRESET, errno.ECONNABORTED, 54):
                        _log.debug(
                            f"HTTP {method.upper()} {path} hit {e!r}, "
                            f"retrying (attempt {error_tries + 1}/5)..."
                        )
                        await _sleep(error_tries)
                        error_tries += 1
                        continue
                    raise

    async def me(self) -> "Application":
        """
        Fetches the bot's user information.

        Returns
        -------
            The bot's user object

        Raises
        ------
        RuntimeError
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
        method
            The HTTP method to use
        guild_id
            The guild ID to query the commands for
        **kwargs
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
        except Unauthorized:
            raise
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
        data
            The JSON data to send to Discord API
        guild_id
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
        guild_id
            The guild ID to fetch the commands for (if None, commands will be global)

        Returns
        -------
            The response from the request

        Raises
        ------
        HTTPException
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
