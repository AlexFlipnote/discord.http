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


if __name__ == "__main__":
    unittest.main()
