import aiohttp
import asyncio
import json
import logging
import random
import sys

from aiohttp.client_exceptions import ContentTypeError
from collections import deque
from typing import (
    Optional, Any, Union, Self, overload,
    Literal, TypeVar, Generic, TYPE_CHECKING
)

from . import __version__
from .errors import (
    NotFound, DiscordServerError,
    Forbidden, HTTPException, Ratelimited,
    AutomodBlock
)

if TYPE_CHECKING:
    from .user import User

MethodTypes = Literal["GET", "POST", "DELETE", "PUT", "HEAD", "PATCH", "OPTIONS"]
ResMethodTypes = Literal["text", "read", "json"]
ResponseT = TypeVar("ResponseT")

_log = logging.getLogger(__name__)

__all__ = (
    "DiscordAPI",
    "HTTPResponse",
)


class HTTPSession(aiohttp.ClientSession):
    async def __aexit__(self):
        if not self.closed:
            await self.close()


class HTTPResponse(Generic[ResponseT]):
    def __init__(
        self,
        *,
        status: int,
        response: ResponseT,
        reason: Optional[str],
        res_method: ResMethodTypes,
        headers: aiohttp.multipart.CIMultiDictProxy[str],
    ):
        self.status = status
        self.response = response
        self.res_method = res_method
        self.reason = reason
        self.headers = headers

    def __repr__(self) -> str:
        return (
            f"<HTTPResponse status={self.status} "
            f"res_method='{self.res_method}'>"
        )


class HTTPClient:
    """
    Used to make HTTP requests, but with a session
    Can be used to make requests outside of the usual Discord API
    """
    def __init__(self):
        self.__session: Optional[HTTPSession] = None

    async def _create_session(self) -> None:
        """ Creates a new session for the library """
        if self.__session:
            await self.__session.close()
        self.__session = HTTPSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )

    async def _close_session(self) -> None:
        """ Closes the session for the library """
        if self.__session:
            await self.__session.close()
        self.__session = None

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
        res_method: Optional[ResMethodTypes] = "text",
        **kwargs
    ) -> HTTPResponse:
        """
        Make a request using the aiohttp library.
        However, it handles response methods for you

        Parameters
        ----------
        method: `Optional[str]`
            The HTTP method to use, defaults to GET
        url: `str`
            The URL to make the request to
        res_method: `Optional[str]`
            The method to use to get the response, defaults to text

        Returns
        -------
        `HTTPResponse`
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

        async with self.__session.request(method.upper(), str(url), **kwargs) as res:
            try:
                r = await getattr(res, res_method.lower())()
            except ContentTypeError:
                if res_method == "json":
                    try:
                        r = json.loads(await res.text())
                    except json.JSONDecodeError:
                        # Give up trying, something is really wrong...
                        r = await res.text()
                        res_method = "text"
                else:
                    r = await res.text()
                    res_method = "text"

            output = HTTPResponse(
                status=res.status,
                response=r,
                res_method=res_method,
                reason=res.reason,
                headers=res.headers
            )

        return output


class Ratelimit:
    def __init__(self, key: str):
        self._key: str = key

        self.limit: int = 1
        self.outgoing: int = 0
        self.remaining = self.limit
        self.reset_after: float = 0.0
        self.expires: Optional[float] = None

        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        self._lock = asyncio.Lock()
        self._last_request: float = self._loop.time()
        self._pending_requests: deque[asyncio.Future[Any]] = deque()

    def reset(self) -> None:
        """ Reset the ratelimit """
        self.remaining = self.limit - self.outgoing
        self.expires = None
        self.reset_after = 0.0

    def update(self, response: HTTPResponse) -> None:
        """ Update the ratelimit with the response headers """
        self.remaining = int(response.headers.get("x-ratelimit-remaining", 0))
        self.reset_after = float(response.headers.get("x-ratelimit-reset-after", 0))
        self.expires = self._loop.time() + self.reset_after

    def _wake_next(self) -> None:
        while self._pending_requests:
            future = self._pending_requests.popleft()
            if not future.done():
                future.set_result(None)
                break

    def _wake(self, count: int = 1) -> None:
        awaken = 0
        while self._pending_requests:
            future = self._pending_requests.popleft()
            if not future.done():
                future.set_result(None)
                awaken += 1

            if awaken >= count:
                break

    async def _refresh(self):
        async with self._lock:
            _log.debug(
                f"Ratelimit bucket hit ({self._key}), "
                f"waiting {self.reset_after}s..."
            )
            await asyncio.sleep(self.reset_after)
            _log.debug(f"Ratelimit bucket released ({self._key})")

        self.reset()
        self._wake(self.remaining)

    def is_expired(self) -> bool:
        return (
            self.expires is not None and
            self._loop.time() > self.expires
        )

    def is_inactive(self) -> bool:
        return (
            (self._loop.time() - self._last_request) >= 300 and
            len(self._pending_requests) == 0
        )

    async def _queue_up(self) -> None:
        self._last_request = self._loop.time()
        if self.is_expired():
            self.reset()

        while self.remaining <= 0:
            future = self._loop.create_future()
            self._pending_requests.append(future)
            try:
                await future
            except Exception:
                future.cancel()
                if self.remaining > 0 and not future.cancelled():
                    self._wake_next()
                raise

        self.remaining -= 1
        self.outgoing += 1

    async def __aenter__(self) -> Self:
        await self._queue_up()
        return self

    async def __aexit__(self, type, value, traceback) -> None:
        self.outgoing -= 1
        tokens = self.remaining - self.outgoing

        if not self._lock.locked():
            if tokens <= 0:
                await self._refresh()
            elif self._pending_requests:
                self._wake(tokens)


class DiscordAPI:
    def __init__(
        self,
        *,
        token: str,
        application_id: Optional[int],
        api_version: Optional[int] = None
    ):
        self.token: str = token
        self.application_id: Optional[int] = application_id

        self.api_version: int = api_version or 10
        if not isinstance(self.api_version, int):
            raise TypeError("api_version must be an integer")

        self.base_url: str = "https://discord.com/api"
        self.api_url: str = f"{self.base_url}/v{self.api_version}"
        self.http: HTTPClient = HTTPClient()

        self._buckets: dict[str, Ratelimit] = {}

    def _clear_old_ratelimits(self) -> None:
        if len(self._buckets) <= 256:
            return

        for key in [k for k, v in self._buckets.items() if v.is_inactive()]:
            try:
                del self._buckets[key]
            except KeyError:
                pass

    def get_ratelimit(self, key: str) -> Ratelimit:
        try:
            value = self._buckets[key]
        except KeyError:
            self._buckets[key] = value = Ratelimit(key)
            self._clear_old_ratelimits()

        return value

    def create_jitter(self) -> float:
        """ `float`: Simply returns a random float between 0 and 1 """
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
        Make a request to the Discord API

        Parameters
        ----------
        method: `str`
            Which HTTP method to use
        path: `str`
            The path to make the request to
        res_method: `str`
            The method to use to get the response

        Returns
        -------
        `HTTPResponse`
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
        if "headers" not in kwargs:
            kwargs["headers"] = {}

        if "Authorization" not in kwargs["headers"]:
            kwargs["headers"]["Authorization"] = f"Bot {self.token}"

        if res_method == "json" and "Content-Type" not in kwargs["headers"]:
            kwargs["headers"]["Content-Type"] = "application/json"

        kwargs["headers"]["User-Agent"] = "discord.http/{0} Python/{1} aiohttp/{2}".format(
            __version__,
            ".".join(str(i) for i in sys.version_info[:3]),
            aiohttp.__version__
        )

        reason = kwargs.pop("reason", None)
        if reason:
            kwargs["headers"]["X-Audit-Log-Reason"] = reason

        _api_url = self.api_url
        if kwargs.pop("webhook", False):
            _api_url = self.base_url

        ratelimit = self.get_ratelimit(f"{method} {path}")

        _http_400_error_table: dict[int, type[HTTPException]] = {
            200000: AutomodBlock,
            200001: AutomodBlock,
        }

        async def _sleep(tries: int) -> None:
            await asyncio.sleep(1 + (tries * 2) + self.create_jitter())

        async with ratelimit:
            for tries in range(5):
                try:
                    r: HTTPResponse = await self.http.request(
                        method,
                        f"{_api_url}{path}",
                        res_method=res_method,
                        **kwargs
                    )

                    _log.debug(f"HTTP {method.upper()} ({r.status}): {path}")

                    match r.status:
                        case x if x >= 200 and x <= 299:
                            ratelimit.update(r)
                            return r

                        case 429:
                            if not isinstance(r.response, dict):
                                # For cases where you're ratelimited by CloudFlare
                                raise Ratelimited(r)

                            retry_after: float = r.response["retry_after"]
                            _log.warning(f"Ratelimit hit ({path}), waiting {retry_after}s...")
                            await asyncio.sleep(retry_after)
                            continue

                        case x if x in (500, 502, 503, 504):
                            if tries > 4:  # Give up after 5 tries
                                raise DiscordServerError(r)

                            # Try again, maybe it will work next time, surely...
                            await _sleep(tries)
                            continue

                        case 400:
                            raise _http_400_error_table.get(
                                r.response.get("code", 0),
                                HTTPException
                            )(r)

                        case 403:
                            raise Forbidden(r)

                        case 404:
                            raise NotFound(r)

                        case _:
                            raise HTTPException(r)

                except OSError as e:
                    if tries < 4 and e.errno in (54, 10054):
                        await _sleep(tries)
                        continue
                    raise
            else:
                raise RuntimeError("Unreachable code, reached max tries (5)")

    async def me(self) -> "User":
        """ `User`: Fetches the bot's user information """
        r = await self.query("GET", "/users/@me")

        from .user import User
        return User(
            state=self,
            data=r.response
        )

    async def _app_command_query(
        self,
        method: MethodTypes,
        guild_id: Optional[int] = None,
        **kwargs
    ) -> HTTPResponse:
        """
        Used to query the application commands
        Mostly used internally by the library

        Parameters
        ----------
        method: `MethodTypes`
            The HTTP method to use
        guild_id: `Optional[int]`
            The guild ID to query the commands for

        Returns
        -------
        `HTTPResponse`
            The response from the request
        """
        if not self.application_id:
            raise ValueError("application_id is required to sync commands")

        url = f"/applications/{self.application_id}/commands"
        if guild_id:
            url = f"/applications/{self.application_id}/guilds/{guild_id}/commands"

        try:
            r = await self.query(method, url, res_method="json", **kwargs)
        except HTTPException as e:
            r = e.request

        return r

    async def update_commands(
        self,
        data: Union[list[dict], dict],
        guild_id: Optional[int] = None
    ) -> dict:
        """
        Updates the commands for the bot

        Parameters
        ----------
        data: `list[dict]`
            The JSON data to send to Discord API
        guild_id: `Optional[int]`
            The guild ID to update the commands for (if None, commands will be global)

        Returns
        -------
        `dict`
            The response from the request
        """
        r = await self._app_command_query(
            "PUT",
            guild_id=guild_id,
            json=data
        )

        target = f"for Guild:{guild_id}" if guild_id else "globally"

        if r.status >= 200 and r.status <= 299:
            _log.info(f"🔁 Successfully synced commands {target}")
        else:
            _log.warning(f"🔁 Failed to sync commands {target}: {r.response}")

        return r.response

    async def fetch_commands(
        self,
        guild_id: Optional[int] = None
    ) -> dict:
        """
        Fetches the commands for the bot

        Parameters
        ----------
        guild_id: `Optional[int]`
            The guild ID to fetch the commands for (if None, commands will be global)

        Returns
        -------
        `dict`
            The response from the request
        """
        r = await self._app_command_query(
            "GET",
            guild_id=guild_id
        )

        return r.response
