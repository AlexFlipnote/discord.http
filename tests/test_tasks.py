import unittest

from datetime import time as dtime
from datetime import timedelta, datetime, UTC

from discord_http.tasks import Loop


async def _dummy() -> None:
    pass


def _make_loop(**overrides) -> Loop:
    kwargs = {
        "func": _dummy, "seconds": 60, "minutes": None, "hours": None,
        "time": None, "count": None, "reconnect": True,
    }
    kwargs.update(overrides)
    return Loop(**kwargs)


class TestLoopCountValidation(unittest.TestCase):
    def test_zero_count_raises(self) -> None:
        with self.assertRaises(ValueError):
            _make_loop(count=0)

    def test_negative_count_raises(self) -> None:
        with self.assertRaises(ValueError):
            _make_loop(count=-1)

    def test_none_count_is_allowed(self) -> None:
        loop = _make_loop(count=None)
        self.assertIsNone(loop.count)

    def test_positive_count_is_allowed(self) -> None:
        loop = _make_loop(count=3)
        self.assertEqual(loop.count, 3)


class TestHandleIntervalValidation(unittest.TestCase):
    def test_all_zero_interval_raises(self) -> None:
        with self.assertRaises(ValueError):
            _make_loop(seconds=0, minutes=0, hours=0)

    def test_combining_time_and_seconds_raises(self) -> None:
        loop = _make_loop(seconds=60)
        with self.assertRaises(ValueError):
            loop.handle_interval(seconds=5, time=dtime(12, 0))

    def test_relative_interval_sums_all_units(self) -> None:
        loop = _make_loop(seconds=1, minutes=2, hours=1)
        self.assertEqual(loop._sleep, 1 + 2 * 60 + 1 * 3600)

    def test_explicit_time_clears_relative_fields(self) -> None:
        loop = _make_loop(seconds=None, minutes=None, hours=None, time=dtime(12, 0))
        self.assertIsNone(loop._sleep)
        self.assertTrue(loop._is_explicit_time())
        self.assertFalse(loop._is_relative_time())

    def test_relative_time_is_the_default_mode(self) -> None:
        loop = _make_loop()
        self.assertTrue(loop._is_relative_time())
        self.assertFalse(loop._is_explicit_time())


class TestSortStaticTimes(unittest.TestCase):
    def test_single_naive_time_gets_utc_attached(self) -> None:
        loop = _make_loop()
        result = loop._sort_static_times(dtime(12, 0))
        self.assertEqual(result, [dtime(12, 0, tzinfo=UTC)])

    def test_list_is_sorted_and_deduplicated(self) -> None:
        loop = _make_loop()
        result = loop._sort_static_times([
            dtime(20, 0), dtime(10, 0), dtime(10, 0),
        ])
        self.assertEqual(result, [dtime(10, 0, tzinfo=UTC), dtime(20, 0, tzinfo=UTC)])

    def test_non_sequence_raises_type_error(self) -> None:
        loop = _make_loop()
        with self.assertRaises(TypeError):
            loop._sort_static_times(123)  # type: ignore[arg-type]

    def test_empty_list_raises_value_error(self) -> None:
        loop = _make_loop()
        with self.assertRaises(ValueError):
            loop._sort_static_times([])

    def test_non_time_item_in_list_raises_type_error(self) -> None:
        loop = _make_loop()
        with self.assertRaises(TypeError):
            loop._sort_static_times([dtime(10, 0), "noon"])  # type: ignore[list-item]


class TestFindTimeIndex(unittest.TestCase):
    def test_returns_index_of_next_upcoming_time(self) -> None:
        loop = _make_loop(seconds=None, time=[dtime(10, 0), dtime(20, 0)])
        now = datetime(2024, 1, 1, 15, 0, tzinfo=UTC)
        self.assertEqual(loop._find_time_index(now), 1)

    def test_returns_first_index_when_now_is_before_all_times(self) -> None:
        loop = _make_loop(seconds=None, time=[dtime(10, 0), dtime(20, 0)])
        now = datetime(2024, 1, 1, 5, 0, tzinfo=UTC)
        self.assertEqual(loop._find_time_index(now), 0)

    def test_returns_none_when_now_is_after_all_times(self) -> None:
        loop = _make_loop(seconds=None, time=[dtime(10, 0), dtime(20, 0)])
        now = datetime(2024, 1, 1, 22, 0, tzinfo=UTC)
        self.assertIsNone(loop._find_time_index(now))


class TestNextSleepTime(unittest.TestCase):
    def test_relative_mode_adds_sleep_seconds_to_last_loop(self) -> None:
        loop = _make_loop(seconds=60)
        loop._last_loop = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        self.assertEqual(
            loop._next_sleep_time(),
            datetime(2024, 1, 1, 12, 1, tzinfo=UTC),
        )

    def test_explicit_time_uses_todays_remaining_slot(self) -> None:
        loop = _make_loop(seconds=None, time=[dtime(10, 0), dtime(20, 0)])
        now = datetime(2024, 1, 1, 15, 0, tzinfo=UTC)
        result = loop._next_sleep_time(now)
        self.assertEqual(result, datetime(2024, 1, 1, 20, 0, tzinfo=UTC))

    def test_explicit_time_rolls_over_to_tomorrows_first_slot(self) -> None:
        loop = _make_loop(seconds=None, time=[dtime(10, 0), dtime(20, 0)])
        now = datetime(2024, 1, 1, 22, 0, tzinfo=UTC)
        result = loop._next_sleep_time(now)
        self.assertEqual(result, datetime(2024, 1, 2, 10, 0, tzinfo=UTC))


class TestExceptionWhitelist(unittest.TestCase):
    def test_default_whitelist(self) -> None:
        import aiohttp
        import asyncio
        loop = _make_loop()
        self.assertEqual(
            loop._whitelist_exceptions,
            (OSError, asyncio.TimeoutError, aiohttp.ClientError),
        )

    def test_add_exception_appends_valid_exception_class(self) -> None:
        loop = _make_loop()
        loop.add_exception(ValueError)
        self.assertIn(ValueError, loop._whitelist_exceptions)

    def test_add_exception_skips_non_class(self) -> None:
        loop = _make_loop()
        before = loop._whitelist_exceptions
        with self.assertLogs("discord_http", level="ERROR"):
            loop.add_exception(5)  # type: ignore[arg-type]
        self.assertEqual(loop._whitelist_exceptions, before)

    def test_add_exception_skips_non_exception_class(self) -> None:
        loop = _make_loop()
        before = loop._whitelist_exceptions

        class NotAnException:
            pass

        with self.assertLogs("discord_http", level="ERROR"):
            loop.add_exception(NotAnException)  # type: ignore[arg-type]
        self.assertEqual(loop._whitelist_exceptions, before)

    def test_remove_exception(self) -> None:
        loop = _make_loop()
        loop.remove_exception(OSError)
        self.assertNotIn(OSError, loop._whitelist_exceptions)

    def test_reset_exceptions_restores_defaults(self) -> None:
        import aiohttp
        import asyncio
        loop = _make_loop()
        loop.add_exception(ValueError)
        loop.remove_exception(OSError)
        loop.reset_exceptions()
        self.assertEqual(
            loop._whitelist_exceptions,
            (OSError, asyncio.TimeoutError, aiohttp.ClientError),
        )


class TestLoopDecoratorValidation(unittest.TestCase):
    def test_on_error_rejects_non_coroutine(self) -> None:
        loop = _make_loop()
        with self.assertRaises(TypeError):
            loop.on_error()(lambda e: None)

    def test_before_loop_rejects_non_coroutine(self) -> None:
        loop = _make_loop()
        with self.assertRaises(TypeError):
            loop.before_loop()(lambda: None)

    def test_after_loop_rejects_non_coroutine(self) -> None:
        loop = _make_loop()
        with self.assertRaises(TypeError):
            loop.after_loop()(lambda: None)

    def test_on_error_accepts_coroutine_and_registers_it(self) -> None:
        loop = _make_loop()

        async def handler(e: Exception) -> None:
            pass

        loop.on_error()(handler)
        self.assertIs(loop._error, handler)


class TestLoopMisc(unittest.TestCase):
    def test_is_running_false_without_a_task(self) -> None:
        loop = _make_loop()
        self.assertFalse(loop.is_running())

    def test_loop_count_starts_at_zero(self) -> None:
        loop = _make_loop()
        self.assertEqual(loop.loop_count, 0)

    def test_failed_starts_false(self) -> None:
        loop = _make_loop()
        self.assertFalse(loop.failed)

    def test_is_being_cancelled_starts_false(self) -> None:
        loop = _make_loop()
        self.assertFalse(loop.is_being_cancelled())


if __name__ == "__main__":
    unittest.main()
