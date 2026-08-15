import unittest

from discord_http import Subscription, PartialSubscription
from discord_http.enums import SubscriptionStatus


class FakeState:
    pass


def _subscription_data(**overrides):
    data = {
        "id": "1", "user_id": "2", "sku_ids": ["10", "11"], "entitlement_ids": ["20"],
        "current_period_start": "2024-01-01T00:00:00.000000+00:00",
        "current_period_end": "2024-02-01T00:00:00.000000+00:00",
        "status": 0,
    }
    data.update(overrides)
    return data


class TestSubscriptionDoesNotExposeSingularSku(unittest.TestCase):
    """ Subscription deliberately does NOT inherit from PartialSubscription and
    has no `sku_id`/`sku` attribute — a subscription can cover multiple SKUs
    at once, so only the plural `sku_ids`/`skus` are exposed. """

    def test_no_sku_id_attribute(self) -> None:
        sub = Subscription(state=FakeState(), data=_subscription_data())
        self.assertFalse(hasattr(sub, "sku_id"))
        self.assertFalse(hasattr(sub, "sku"))

    def test_skus_and_renewal_skus_properties(self) -> None:
        sub = Subscription(state=FakeState(), data=_subscription_data(
            renewal_sku_ids=["12"]
        ))
        self.assertEqual([s.id for s in sub.skus], [10, 11])
        self.assertEqual([s.id for s in sub.renewal_skus], [12])

    def test_entitlements_property(self) -> None:
        sub = Subscription(state=FakeState(), data=_subscription_data())
        self.assertEqual([e.id for e in sub.entitlements], [20])

    def test_status_and_canceled_at(self) -> None:
        sub = Subscription(state=FakeState(), data=_subscription_data(
            status=2, canceled_at="2024-01-15T00:00:00.000000+00:00"
        ))
        self.assertEqual(sub.status, SubscriptionStatus.ending)
        self.assertIsNotNone(sub.canceled_at)


class TestSubscriptionFetchRouting(unittest.IsolatedAsyncioTestCase):
    """ Regression test: fetch() used to do `self.sku_ids[0]` unconditionally,
    raising a bare, confusing IndexError whenever sku_ids was empty. """

    async def test_fetch_without_any_sku_context_raises_value_error(self) -> None:
        sub = Subscription(state=FakeState(), data=_subscription_data(sku_ids=[]))
        with self.assertRaises(ValueError):
            await sub.fetch()


class TestPartialSubscription(unittest.TestCase):
    def test_sku_property(self) -> None:
        partial = PartialSubscription(state=FakeState(), id=1, sku_id=10)
        self.assertEqual(partial.sku.id, 10)


if __name__ == "__main__":
    unittest.main()
