from datetime import datetime
from typing import TYPE_CHECKING

from . import utils
from .enums import EntitlementType, EntitlementOwnerType, SKUType
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
)


class PartialSKU(PartialBase):
    __slots__ = ("_state",)

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int  # noqa: A002
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialSKU id={self.id}>"

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


class SKU(PartialSKU):
    """
    Represents a SKU (Stock Keeping Unit) object.

    Attributes
    ----------
    name: str
        The name of the SKU.
    slug: str
        The slug of the SKU.
    type: SKUType
        The type of the SKU.
    flags: SKUFlags
        The flags of the SKU.
    application: PartialUser
        The application that owns the SKU.
    """

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
        self.slug: str = data["slug"]

        self._raw_type: int = data["type"]
        self._raw_flags: int = data["flags"]

        self.application: PartialUser = PartialUser(
            state=self._state,
            id=int(data["application_id"])
        )

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
    __slots__ = ("_state",)

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int  # noqa: A002
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialEntitlements id={self.id}>"

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
        self.type: EntitlementType = EntitlementType(data["type"])

        self.user: PartialUser | None = None
        self.guild_id: int | None = utils.get_int(data, "guild_id")
        self.subscription_id: int | None = utils.get_int(data, "subscription_id")

        self.application: PartialUser = PartialUser(
            state=self._state,
            id=int(data["application_id"])
        )
        self.sku: PartialSKU = PartialSKU(
            state=self._state,
            id=int(data["sku_id"])
        )

        self.starts_at: datetime | None = None
        self.ends_at: datetime | None = None

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
        """ Returns the guild the entitlement is in. """
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
