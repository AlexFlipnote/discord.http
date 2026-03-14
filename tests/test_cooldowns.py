import unittest

from types import SimpleNamespace

from discord_http import BucketType, Cooldown, CooldownCache


class TestCooldown(unittest.TestCase):
    def test_update_rate_limit_and_retry_after(self) -> None:
        cooldown = Cooldown(rate=2, per=10)

        self.assertIsNone(cooldown.update_rate_limit(current=100.0))
        self.assertIsNone(cooldown.update_rate_limit(current=101.0))

        retry_after = cooldown.update_rate_limit(current=102.0)
        self.assertEqual(retry_after, 8.0)

    def test_get_tokens_resets_after_window(self) -> None:
        cooldown = Cooldown(rate=1, per=5)
        cooldown.update_rate_limit(current=200.0)

        self.assertEqual(cooldown.get_tokens(current=201.0), 0)
        self.assertEqual(cooldown.get_tokens(current=206.0), 1)

    def test_reset_restores_initial_state(self) -> None:
        cooldown = Cooldown(rate=3, per=30)
        cooldown.update_rate_limit(current=50.0)
        cooldown.reset()

        self.assertEqual(cooldown.get_tokens(current=50.0), 3)


class TestBucketType(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = SimpleNamespace(
            user=SimpleNamespace(id=11),
            guild=SimpleNamespace(id=22),
            channel=SimpleNamespace(id=33, parent_id=44),
        )

    def test_bucket_type_key_resolution(self) -> None:
        self.assertEqual(BucketType.default.get_key(self.ctx), 0)  # pyright: ignore[reportArgumentType]
        self.assertEqual(BucketType.user.get_key(self.ctx), 11)  # pyright: ignore[reportArgumentType]
        self.assertEqual(BucketType.member.get_key(self.ctx), (22, 11))  # pyright: ignore[reportArgumentType]
        self.assertEqual(BucketType.guild.get_key(self.ctx), 22)  # pyright: ignore[reportArgumentType]
        self.assertEqual(BucketType.category.get_key(self.ctx), 44)  # pyright: ignore[reportArgumentType]
        self.assertEqual(BucketType.channel.get_key(self.ctx), 33)  # pyright: ignore[reportArgumentType]


class TestCooldownCache(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = SimpleNamespace(
            user=SimpleNamespace(id=99),
            guild=SimpleNamespace(id=123),
            channel=SimpleNamespace(id=456, parent_id=None),
        )

    def test_default_bucket_reuses_original_cooldown(self) -> None:
        base = Cooldown(rate=1, per=5)
        cache = CooldownCache(base, BucketType.default)

        self.assertIs(cache.get_bucket(self.ctx, current=1.0), base)  # pyright: ignore[reportArgumentType]

    def test_non_default_bucket_creates_and_reuses_bucket(self) -> None:
        cache = CooldownCache(Cooldown(rate=1, per=10), BucketType.user)

        first = cache.get_bucket(self.ctx, current=10.0)  # pyright: ignore[reportArgumentType]
        first.update_rate_limit(current=10.0)
        second = cache.get_bucket(self.ctx, current=11.0)  # pyright: ignore[reportArgumentType]

        self.assertIs(first, second)

    def test_cleanup_removes_expired_bucket(self) -> None:
        cache = CooldownCache(Cooldown(rate=1, per=2), BucketType.user)

        first = cache.get_bucket(self.ctx, current=0.0)  # pyright: ignore[reportArgumentType]
        cache.update_rate_limit(self.ctx, current=0.0)  # pyright: ignore[reportArgumentType]

        second = cache.get_bucket(self.ctx, current=4.0)  # pyright: ignore[reportArgumentType]
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
