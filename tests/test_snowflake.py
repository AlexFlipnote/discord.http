import unittest

from datetime import UTC, datetime

from discord_http import Snowflake, utils


class TestSnowflake(unittest.TestCase):
    def test_string_id_is_converted_to_int(self) -> None:
        snowflake = Snowflake("123456789012345678")
        self.assertEqual(int(snowflake), 123456789012345678)

    def test_invalid_id_type_raises(self) -> None:
        with self.assertRaises(TypeError):
            Snowflake("not-an-int")

    def test_comparison_with_int_and_snowflake(self) -> None:
        first = Snowflake(100)
        second = Snowflake(200)

        self.assertTrue(first < second)
        self.assertTrue(second > 150)
        self.assertTrue(first <= 100)
        self.assertTrue(second >= Snowflake(200))

    def test_created_at_matches_encoded_timestamp(self) -> None:
        expected = datetime(2024, 1, 1, tzinfo=UTC)
        sf = Snowflake(utils.time_snowflake(expected))

        self.assertEqual(sf.created_at, expected)


class TestSnowflakeInitErrorType(unittest.TestCase):
    """ A non-convertible id raises TypeError, not ValueError - int("not-an-int")
    itself raises ValueError internally, but Snowflake.__init__ catches that
    and re-raises as TypeError. """

    def test_non_convertible_string_raises_type_error_not_value_error(self) -> None:
        with self.assertRaises(TypeError):
            Snowflake("not-an-int")

        try:
            Snowflake("not-an-int")
        except TypeError:
            pass
        except ValueError:
            self.fail("Snowflake should raise TypeError, not ValueError")

    def test_none_raises_type_error(self) -> None:
        # int(None) raises TypeError directly, which is not caught by the
        # `except ValueError` clause - it propagates as-is (still a TypeError).
        with self.assertRaises(TypeError):
            Snowflake(None)  # type: ignore[arg-type]


class TestSnowflakeEqualityOrderingAsymmetry(unittest.TestCase):
    """ __eq__ is lenient (returns False for unrelated types, per Python's
    NotImplemented-less convention here), while __gt__/__lt__/__ge__/__le__
    are strict and raise TypeError for the same unrelated types. """

    def test_equality_with_unrelated_type_returns_false(self) -> None:
        sf = Snowflake(100)
        self.assertFalse(sf == "100")
        self.assertFalse(sf == 100.0)
        self.assertFalse(sf == object())

    def test_ordering_with_unrelated_type_raises_type_error(self) -> None:
        sf = Snowflake(100)
        with self.assertRaises(TypeError):
            sf > "100"
        with self.assertRaises(TypeError):
            sf < "100"
        with self.assertRaises(TypeError):
            sf >= object()
        with self.assertRaises(TypeError):
            sf <= object()

    def test_ordering_still_works_against_plain_int(self) -> None:
        sf = Snowflake(100)
        self.assertTrue(sf > 50)
        self.assertTrue(sf < 150)
        self.assertTrue(sf >= 100)
        self.assertTrue(sf <= 100)


if __name__ == "__main__":
    unittest.main()
