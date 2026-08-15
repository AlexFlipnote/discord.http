from datetime import datetime
from typing import TYPE_CHECKING

from . import utils
from .enums import EntitlementType, EntitlementOwnerType, SKUType, SubscriptionStatus
from .flags import SKUFlags
from .guild import Guild, PartialGuild
from .object import PartialBase, Snowflake
from .user import PartialUser

if TYPE_CHECKING:
    from .http import DiscordAPI

__all__ = (
    "SKU",
    "Entitlements",
    "PartialEntitlements",
    "PartialSKU",
    "PartialSubscription",
    "Subscription",
)


class PartialSKU(PartialBase):
    """ Represents a partial SKU object. """

    __slots__ = ("_state",)

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int  # ruff: ignore[builtin-argument-shadowing]
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialSKU id={self.id}>"

    def __str__(self) -> str:
        return "PartialSKU"

    async def create_test_entitlement(
        self,
        *,
        owner_id: Snowflake | int,
        owner_type: EntitlementOwnerType | int,
    ) -> "PartialEntitlements":
        """
        Create an entitlement for testing purposes.

        Parameters
        ----------
        owner_id:
            The ID of the owner, can be GuildID or UserID.
        owner_type:
            The type of the owner.

        Returns
        -------
            The created entitlement.
        """
        r = await self._state.query(
            "POST",
            f"/applications/{self._state.bot.application_id}/entitlements",
            json={
                "sku_id": str(self.id),
                "owner_id": str(int(owner_id)),
                "owner_type": int(owner_type)
            }
        )

        return PartialEntitlements(
            state=self._state,
            id=int(r.response["id"])
        )

    async def fetch_subscriptions(
        self,
        user_id: Snowflake | int,
        *,
        before: Snowflake | int | None = None,
        after: Snowflake | int | None = None,
        limit: int = 50,
    ) -> list["Subscription"]:
        """
        Fetch the subscriptions for this SKU.

        Parameters
        ----------
        user_id:
            The user ID to fetch subscriptions for. Required for bot-token requests
            (only optional when using an OAuth2 access token, which this library does not support).
        before:
            Consider only subscriptions before given ID
        after:
            Consider only subscriptions after given ID
        limit:
            The maximum amount of subscriptions to fetch (1-100)

        Returns
        -------
            The subscriptions for this SKU
        """
        params: dict[str, int | str] = {
            "limit": limit,
            "user_id": str(int(user_id)),
        }

        if before is not None:
            params["before"] = str(int(before))
        if after is not None:
            params["after"] = str(int(after))

        r = await self._state.query(
            "GET",
            f"/skus/{self.id}/subscriptions",
            params=params
        )

        return [
            Subscription(state=self._state, sku_id=self.id, data=g)
            for g in r.response
        ]

    async def fetch_subscription(
        self,
        subscription_id: Snowflake | int
    ) -> "Subscription":
        """
        Fetch a specific subscription for this SKU.

        Parameters
        ----------
        subscription_id:
            The ID of the subscription to fetch

        Returns
        -------
            The subscription
        """
        return await self.get_partial_subscription(subscription_id).fetch()

    def get_partial_subscription(
        self,
        subscription_id: Snowflake | int
    ) -> "PartialSubscription":
        """
        Creates a partial subscription object under this SKU, without fetching it.

        Parameters
        ----------
        subscription_id:
            The ID of the subscription

        Returns
        -------
            The partial subscription object
        """
        return PartialSubscription(
            state=self._state,
            id=int(subscription_id),
            sku_id=self.id
        )


class SKU(PartialSKU):
    """ Represents a SKU (Stock Keeping Unit) object. """

    __slots__ = (
        "_raw_flags",
        "_raw_type",
        "application",
        "name",
        "slug",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.name: str = data["name"]
        """ The name of the SKU. """

        self.slug: str = data["slug"]
        """ The slug of the SKU. """

        self._raw_type: int = data["type"]
        self._raw_flags: int = data["flags"]

        self.application: PartialUser = PartialUser(
            state=self._state,
            id=int(data["application_id"])
        )
        """ The application that owns the SKU. """

    def __repr__(self) -> str:
        return f"<SKU id={self.id} name={self.name} type={self.type}>"

    def __str__(self) -> str:
        return f"{self.name}"

    @property
    def type(self) -> SKUType:
        """ The type of the SKU. """
        return SKUType(self._raw_type)

    @property
    def flags(self) -> SKUFlags:
        """ The flags of the SKU. """
        return SKUFlags(self._raw_flags)


class PartialEntitlements(PartialBase):
    """ Represents a partial entitlement object. """

    __slots__ = ("_state",)

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int  # ruff: ignore[builtin-argument-shadowing]
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialEntitlements id={self.id}>"

    def __str__(self) -> str:
        return "PartialEntitlements"

    async def fetch(self) -> "Entitlements":
        """ Fetches the entitlement. """
        r = await self._state.query(
            "GET",
            f"/applications/{self._state.bot.application_id}/entitlements/{self.id}"
        )

        return Entitlements(
            state=self._state,
            data=r.response
        )

    async def consume(self) -> None:
        """ Mark the entitlement as consumed. """
        await self._state.query(
            "POST",
            f"/applications/{self._state.bot.application_id}/entitlements/{self.id}/consume",
            res_method="text"
        )

    async def delete_test_entitlement(self) -> None:
        """ Deletes a test entitlement. """
        await self._state.query(
            "DELETE",
            f"/applications/{self._state.bot.application_id}/entitlements/{self.id}",
            res_method="text"
        )


class Entitlements(PartialEntitlements):
    """ Represents an entitlement object. """
    __slots__ = (
        "_data_consumed",
        "application",
        "deleted",
        "ends_at",
        "guild_id",
        "sku",
        "starts_at",
        "subscription_id",
        "type",
        "user",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.deleted: bool = data["deleted"]
        """ Whether the entitlement is deleted or not. """

        self.type: EntitlementType = EntitlementType(data["type"])
        """ The type of the entitlement. """

        self.user: PartialUser | None = None
        """ The user that owns the entitlement, if the owner type is user. """

        self.guild_id: int | None = utils.get_int(data, "guild_id")
        """ The guild ID that owns the entitlement, if the owner type is guild. """

        self.subscription_id: int | None = utils.get_int(data, "subscription_id")
        """ The subscription ID that the entitlement belongs to, if any. """

        self.application: PartialUser = PartialUser(
            state=self._state,
            id=int(data["application_id"])
        )
        """ The application that owns the entitlement. """

        self.sku: PartialSKU = PartialSKU(
            state=self._state,
            id=int(data["sku_id"])
        )
        """ The SKU that the entitlement belongs to. """

        self.starts_at: datetime | None = None
        """ The time the entitlement starts at, if any. """

        self.ends_at: datetime | None = None
        """ The time the entitlement ends at, if any. """

        self._from_data(data)
        self._data_consumed: bool = data.get("consumed", False)

    def __repr__(self) -> str:
        return f"<Entitlements id={self.id} sku={self.sku} type={self.type}>"

    def __str__(self) -> str:
        return f"{self.sku}"

    def _from_data(self, data: dict) -> None:
        if data.get("user_id"):
            self.user = PartialUser(state=self._state, id=int(data["user_id"]))

        if data.get("starts_at"):
            self.starts_at = utils.parse_time(data["starts_at"])

        if data.get("ends_at"):
            self.ends_at = utils.parse_time(data["ends_at"])

    @property
    def guild(self) -> Guild | PartialGuild | None:
        """ The guild the entitlement is in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    def is_consumed(self) -> bool:
        """ Returns whether the entitlement is consumed or not. """
        return bool(self._data_consumed)


class PartialSubscription(PartialBase):
    """ Represents a partial subscription object. """

    __slots__ = ("_route_sku_id", "_state",)

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        sku_id: int,
        id: int,  # ruff: ignore[builtin-argument-shadowing]
    ):
        super().__init__(id=int(id))
        self._state = state

        self._route_sku_id: int = int(sku_id)
        """ The ID of the SKU to look up this subscription through. """

    def __repr__(self) -> str:
        return f"<PartialSubscription id={self.id}>"

    def __str__(self) -> str:
        return "PartialSubscription"

    @property
    def sku(self) -> PartialSKU:
        """ The SKU this subscription is being looked up through. """
        return PartialSKU(state=self._state, id=self._route_sku_id)

    async def fetch(self) -> "Subscription":
        """ Fetches the subscription. """
        r = await self._state.query(
            "GET",
            f"/skus/{self._route_sku_id}/subscriptions/{self.id}"
        )

        return Subscription(
            state=self._state,
            sku_id=self._route_sku_id,
            data=r.response
        )


class Subscription(PartialBase):
    """ Represents a subscription object. """

    __slots__ = (
        "_raw_status",
        "_route_sku_id",
        "_state",
        "canceled_at",
        "country",
        "current_period_end",
        "current_period_start",
        "entitlement_ids",
        "renewal_sku_ids",
        "sku_ids",
        "user_id",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        sku_id: int | None = None,
    ):
        super().__init__(id=int(data["id"]))
        self._state = state

        self._route_sku_id: int | None = sku_id
        """ The SKU this subscription was looked up through, only kept around to make `fetch()` work. """

        self.user_id: int = int(data["user_id"])
        """ The ID of the user subscribed to the SKU(s). """

        self.sku_ids: list[int] = [int(g) for g in data.get("sku_ids", [])]
        """ The SKUs the user is subscribed to. """

        self.entitlement_ids: list[int] = [int(g) for g in data.get("entitlement_ids", [])]
        """ The entitlements granted for this subscription. """

        self.renewal_sku_ids: list[int] | None = None
        """ The SKUs the user will be subscribed to at renewal, if any. """

        self.current_period_start: datetime = utils.parse_time(data["current_period_start"])
        """ The start of the current subscription period. """

        self.current_period_end: datetime = utils.parse_time(data["current_period_end"])
        """ The end of the current subscription period. """

        self._raw_status: int = data["status"]

        self.canceled_at: datetime | None = None
        """ The time the subscription was canceled, if any. """

        self.country: str | None = data.get("country")
        """ The ISO 3166-1 alpha-2 country code of the payment source, if any. """

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} status={self.status}>"

    def __str__(self) -> str:
        return "Subscription"

    def _from_data(self, data: dict) -> None:
        if data.get("renewal_sku_ids") is not None:
            self.renewal_sku_ids = [int(g) for g in data["renewal_sku_ids"]]

        if data.get("canceled_at"):
            self.canceled_at = utils.parse_time(data["canceled_at"])

    @property
    def skus(self) -> list[PartialSKU]:
        """ The partial SKU objects this subscription applies to. """
        return [
            PartialSKU(state=self._state, id=g)
            for g in self.sku_ids
        ]

    @property
    def renewal_skus(self) -> list[PartialSKU]:
        """ The partial SKU objects the user will be subscribed to at renewal, if any. """
        return [
            PartialSKU(state=self._state, id=g)
            for g in (self.renewal_sku_ids or [])
        ]

    @property
    def entitlements(self) -> list[PartialEntitlements]:
        """ The partial entitlement objects granted for this subscription. """
        return [
            PartialEntitlements(state=self._state, id=g)
            for g in self.entitlement_ids
        ]

    @property
    def status(self) -> SubscriptionStatus:
        """ The status of the subscription. """
        return SubscriptionStatus(self._raw_status)

    @property
    def user(self) -> PartialUser:
        """ The user subscribed to the SKU(s). """
        return PartialUser(state=self._state, id=self.user_id)

    async def fetch(self) -> "Subscription":
        """
        Fetches the latest version of this subscription.

        Raises
        ------
        `ValueError`
            If no SKU is known to route the request through (should not happen for a
            subscription that came from the API, which always includes `sku_ids`)
        """
        if self._route_sku_id is not None:
            sku_id = self._route_sku_id
        elif self.sku_ids:
            sku_id = self.sku_ids[0]
        else:
            raise ValueError("Cannot fetch a subscription with no known SKU to route the request through")

        return await PartialSubscription(
            state=self._state,
            id=self.id,
            sku_id=sku_id
        ).fetch()
