import aiohttp
import asyncio
import inspect
import logging

from datetime import time as dtime
from datetime import timedelta, datetime, timezone
from typing import Callable, Sequence

from . import utils

_log = logging.getLogger(__name__)


class Sleeper:
    def __init__(self, dt: datetime, *, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.future: asyncio.Future = loop.create_future()
        self.handle: asyncio.TimerHandle = loop.call_later(
            max((dt - utils.utcnow()).total_seconds(), 0),
            self.future.set_result,
            True
        )

    def recalculate(self, dt: datetime) -> None:
        self.handle.cancel()
        self.handle: asyncio.TimerHandle = self.loop.call_later(
            max((dt - utils.utcnow()).total_seconds(), 0),
            self.future.set_result,
            True
        )

    def wait(self) -> asyncio.Future:
        return self.future

    def done(self) -> bool:
        return self.future.done()

    def cancel(self) -> None:
        self.future.cancel()
        self.handle.cancel()


class Loop:
    def __init__(
        self,
        *,
        func: Callable,
        seconds: float | None,
        minutes: float | None,
        hours: float | None,
        time: dtime | list[dtime] | None = None,
        count: int | None = None,
        reconnect: bool = True
    ):
        self.func: Callable = func
        self.reconnect: bool = reconnect

        self.count: int | None = count
        if self.count is not None and self.count <= 0:
            raise ValueError("count must be greater than 0 or None")

        self._task: asyncio.Task | None = None
        self._injected = None

        self._error: Callable = self._default_error
        self._before_loop: Callable = self._default_before_loop
        self._after_loop: Callable = self._default_after_loop

        self._whitelist_exceptions: tuple[type[Exception], ...] = (
            OSError,
            asyncio.TimeoutError,
            aiohttp.ClientError,
        )

        self.handle_interval(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            time=time
        )

        self._will_cancel: bool = False
        self._should_stop: bool = False
        self._has_faild: bool = False
        self._last_loop_failed: bool = False
        self._last_loop: datetime | None = None
        self._next_loop: datetime | None = None
        self._loop_count: int = 0

    async def __call__(self, *args, **kwargs) -> Callable:
        if self._injected is not None:
            args = (self._injected, *args)

        return await self.func(*args, **kwargs)

    def __get__(self, obj, objtype):
        if obj is None:
            return self

        copy: Loop = Loop(
            func=self.func,
            seconds=self._seconds,
            minutes=self._minutes,
            hours=self._hours,
            time=self._time,
            count=self.count,
            reconnect=self.reconnect
        )

        copy._injected = obj
        copy._before_loop = self._before_loop
        copy._after_loop = self._after_loop
        copy._error = self._error
        setattr(obj, self.func.__name__, copy)
        return copy

    async def _try_sleep_until(self, dt: datetime) -> None:
        """ Attempt to sleeps until a specified datetime depending on the loop configuration """
        self._handle = Sleeper(dt, loop=asyncio.get_event_loop())
        return await self._handle.wait()

    async def _default_error(self, e: Exception) -> None:
        """ The default error handler for the loop """
        _log.error(
            f"Unhandled exception in background loop {self.func.__name__}",
            exc_info=e
        )

    async def _default_before_loop(self) -> None:
        """ The default before_loop handler for the loop """
        pass

    async def _default_after_loop(self) -> None:
        """ The default after_loop handler for the loop """
        pass

    async def _looper(self, *args, **kwargs) -> None:
        """ Internal looper that handles the behaviour of the loop """
        await self._before_loop()
        self._last_loop_failed = False

        if self._is_explicit_time():
            self._next_loop = self._next_sleep_time()
        else:
            self._next_loop = utils.utcnow()
            await asyncio.sleep(0)

        try:
            if self._should_stop:
                return None
            while True:
                if self._is_explicit_time():
                    await self._try_sleep_until(self._next_loop)

                if not self._last_loop_failed:
                    self._last_loop = self._next_loop
                    self._next_loop = self._next_sleep_time()

                    while (
                        self._is_explicit_time() and
                        self._next_loop <= self._last_loop
                    ):
                        _log.warning(
                            f"task:{self.func.__name__} woke up a bit too early. "
                            f"Sleeping until {self._next_loop} to avoid drifting."
                        )
                        await self._try_sleep_until(self._next_loop)
                        self._next_loop = self._next_sleep_time()

                try:
                    await self.func(*args, **kwargs)
                    self._last_loop_failed = False
                except self._whitelist_exceptions:
                    self._last_loop_failed = True
                    if not self.reconnect:
                        raise
                    await asyncio.sleep(5)
                else:
                    if self._should_stop:
                        return

                    if self._is_relative_time():
                        await self._try_sleep_until(self._next_loop)

                    self._loop_count += 1
                    if (
                        self.count and
                        self.loop_count >= self.count
                    ):
                        break

        except asyncio.CancelledError:
            self._will_cancel = True
            raise
        except Exception as e:
            self._has_faild = True
            await self._error(e)
        finally:
            await self._after_loop()
            if self._handle:
                self._handle.cancel()
            self._will_cancel = False
            self._loop_count = 0
            self._should_stop = False

    def start(self, *args, **kwargs) -> asyncio.Task:
        """ Starts the loop """
        if self._task and not self._task.done():
            raise RuntimeError("The loop is already running")

        if self._injected is not None:
            args = (self._injected, *args)

        self._last_loop_failed = False
        self._task = asyncio.create_task(self._looper(*args, **kwargs))
        return self._task

    def stop(self) -> None:
        """ Stops the loop """
        if self._task and not self._task.done():
            self._should_stop = True

    def _can_be_cancelled(self) -> bool:
        return bool(
            not self._will_cancel and
            self._task and
            not self._task.done()
        )

    def cancel(self) -> None:
        """ Cancels the loop if possible """
        if self._can_be_cancelled():
            self._task.cancel()

    def on_error(self) -> Callable:
        """ Decorator that registers a custom error handler for the loop """
        def decorator(func: Loop) -> Loop:
            if not inspect.iscoroutinefunction(func):
                raise TypeError("The error handler must be a coroutine function")

            self._error = func
            return func

        return decorator

    def before_loop(self) -> Callable:
        """ Decorator that registers a custom before_loop handler for the loop """
        def decorator(func: Loop) -> Loop:
            if not inspect.iscoroutinefunction(func):
                raise TypeError("The before_loop must be a coroutine function")

            self._before_loop = func
            return func

        return decorator

    def after_loop(self) -> Callable:
        """ Decorator that registers a custom after_loop handler for the loop """
        def decorator(func: Loop) -> Loop:
            if not inspect.iscoroutinefunction(func):
                raise TypeError("The after_loop must be a coroutine function")

            self._after_loop = func
            return func

        return decorator

    def is_running(self) -> bool:
        """ Returns whether the loop is running or not """
        return not bool(self._task.done()) if self._task else False

    @property
    def loop_count(self) -> int:
        """ Returns the number of times the loop has been run """
        return self._loop_count

    @property
    def failed(self) -> bool:
        """ Returns whether the loop has failed or not """
        return self._has_faild

    def _is_relative_time(self) -> bool:
        return self._time is None

    def _is_explicit_time(self) -> bool:
        return self._time is not None

    def is_being_cancelled(self) -> bool:
        """ Returns whether the loop is being cancelled or not """
        return self._will_cancel

    def fetch_task(self) -> asyncio.Task | None:
        """ Returns the task that is running the loop """
        return self._task

    def add_exception(self, *exceptions: Exception) -> None:
        """ Adds exceptions to the whitelist of exceptions that are ignored """
        for e in exceptions:
            if not inspect.isclass(e):
                _log.error(
                    "Loop.add_exception expected a class, "
                    f"received {type(e)} instead, skipping"
                )
                continue

            if not issubclass(e, BaseException):
                _log.error(
                    "Loop.add_exception expected a subclass of BaseException, "
                    f"received {e} instead, skipping"
                )
                continue

            self._whitelist_exceptions += (e,)  # type: ignore

    def remove_exception(self, *exceptions: Exception) -> None:
        """ Removes exceptions from the whitelist of exceptions that are ignored """
        self._whitelist_exceptions = tuple(
            x for x in self._whitelist_exceptions
            if x not in exceptions
        )

    def reset_exceptions(self) -> None:
        """ Resets the whitelist of exceptions that are ignored back to the default """
        self._whitelist_exceptions = (
            OSError,
            asyncio.TimeoutError,
            aiohttp.ClientError,
        )

    def _sort_static_times(
        self,
        times: dtime | Sequence[dtime] | None
    ) -> list[dtime]:
        if isinstance(times, dtime):
            return [
                times
                if times.tzinfo is not None
                else times.replace(tzinfo=timezone.utc)
            ]

        if not isinstance(times, Sequence):
            raise TypeError(f"Expected a list, got {type(times)} instead")
        if not times:
            raise ValueError("Expected at least one item, got an empty list instead")

        output: list[dtime] = []
        for i, ts in enumerate(times):
            if not isinstance(ts, dtime):
                raise TypeError(f"Expected datetime.time, got {type(ts)} (Index: {i})")

            output.append(
                ts
                if ts.tzinfo is not None
                else ts.replace(tzinfo=timezone.utc)
            )

        return sorted(set(output))

    def handle_interval(
        self,
        *,
        seconds: float | None = 0,
        minutes: float | None = 0,
        hours: float | None = 0,
        time: dtime | list[dtime] | None = None
    ) -> None:
        """
        Sets the interval of the loop.

        Parameters
        ----------
        seconds: `float`
            Amount of seconds between each iteration of the loop
        minutes: `float`
            Amount of minutes between each iteration of the loop
        hours: `float`
            Amount of hours between each iteration of the loop
        time: `dtime`
            The time of day to run the loop at

        Raises
        ------
        `ValueError`
            - The sleep timer cannot be 0
            - `count` must be greater than 0 or `None`
        `TypeError`
            `time` must be a `datetime.time` object
        """
        if time is None:
            seconds = seconds or 0.0
            minutes = minutes or 0.0
            hours = hours or 0.0

            sleep = seconds + (minutes * 60.0) + (hours * 3600.0)
            if sleep <= 0:
                raise ValueError("The sleep timer cannot be 0")

            self._seconds = float(seconds)
            self._minutes = float(minutes)
            self._hours = float(hours)
            self._sleep = sleep
            self._time: list[dtime] | None = None
        else:
            if any((seconds, minutes, hours)):
                raise ValueError("Cannot use both time and seconds/minutes/hours")

            self._time: list[dtime] | None = self._sort_static_times(time)
            self._sleep = self._seconds = self._minutes = self._hours = None

        if self.is_running() and self._last_loop is not None:
            self._next_loop = self._next_sleep_time()
            if self._handle and not self._handle.done():
                self._handle.recalculate(self._next_loop)

    def _find_time_index(self, now: datetime) -> int | None:
        """
        Finds the index of the next time in the list of times

        Parameters
        ----------
        now: `datetime`
            The current time

        Returns
        -------
        `Optional[int]`
            The index of the next time in the list of times
        """
        if not self._time:
            return None

        for i, ts in enumerate(self._time):
            start = now.astimezone(ts.tzinfo)
            if ts >= start.timetz():
                return i
        else:
            return None

    def _next_sleep_time(self, now: datetime | None = None) -> datetime:
        """ Calculates the next time the loop should run """
        if self._sleep is not None:
            return self._last_loop + timedelta(seconds=self._sleep)

        if now is None:
            now = utils.utcnow()

        index = self._find_time_index(now)

        if index is None:
            time = self._time[0]
            tomorrow = now.astimezone(time.tzinfo) + timedelta(days=1)
            date = tomorrow.date()
        else:
            time = self._time[index]
            date = now.astimezone(time.tzinfo).date()

        dt = datetime.combine(date, time, tzinfo=time.tzinfo)
        return dt.astimezone(timezone.utc)


def loop(
    *,
    seconds: float | None = None,
    minutes: float | None = None,
    hours: float | None = None,
    time: dtime | list[dtime] | None = None,
    count: int | None = None,
    reconnect: bool = True
) -> Callable[[Callable], Loop]:
    """
    Decorator that registers a function as a loop.

    Parameters
    ----------
    seconds: `float`
        The number of seconds between each iteration of the loop.
    minutes: `float`
        The number of minutes between each iteration of the loop.
    hours: `float`
        The number of hours between each iteration of the loop.
    time: `datetime.time`
        The time of day to run the loop at. (UTC only)
    count: `int`
        The number of times to run the loop. If ``None``, the loop will run forever.
    reconnect: `bool`
        Whether the loop should reconnect if it fails or not.
    """
    def decorator(func) -> Loop:
        return Loop(
            func=func,
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            time=time,
            count=count,
            reconnect=reconnect
        )

    return decorator
