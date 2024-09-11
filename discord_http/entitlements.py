from datetime import datetime
from typing import TYPE_CHECKING, Optional, Union

from . import utils
from .enums import EntitlementType, EntitlementOwnerType, SKUType
from .flag import SKUFlags
from .guild import PartialGuild
from .object import PartialBase, Snowflake
from .user import PartialUser

if TYPE_CHECKING:
    from .http import DiscordAPI

__all__ = (
    "Entitlements",
    "PartialEntitlements",
    "PartialSKU",
    "SKU",
)


class PartialSKU(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialSKU id={self.id}>"

    async def create_test_entitlement(
        self,
        *,
        owner_id: Union[Snowflake, int],
        owner_type: Union[EntitlementOwnerType, int],
    ) -> "PartialEntitlements":
        """
        Create an entitlement for testing purposes.

        Parameters
        ----------
        owner_id: `Union[Snowflake, int]`
            The ID of the owner, can be GuildID or UserID.
        owner_type: `Union[EntitlementOwnerType, int]`
            The type of the owner.

        Returns
        -------
        `PartialEntitlements`
            The created entitlement.
        """
        r = await self._state.query(
            "POST",
            f"/applications/{self._state.application_id}/entitlements",
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
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.name: str = data["name"]
        self.slug: str = data["slug"]
        self.type: SKUType = SKUType(data["type"])
        self.flags: SKUFlags = SKUFlags(data["flags"])

        self.application: PartialUser = PartialUser(
            state=self._state,
            id=int(data["application_id"])
        )

    def __repr__(self) -> str:
        return f"<SKU id={self.id} name={self.name} type={self.type}>"

    def __str__(self) -> str:
        return f"{self.name}"


class PartialEntitlements(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialEntitlements id={self.id}>"

    async def fetch(self) -> "Entitlements":
        """ `Entitlements`: Fetches the entitlement. """
        r = await self._state.query(
            "GET",
            f"/applications/{self._state.application_id}/entitlements/{self.id}"
        )

        return Entitlements(
            state=self._state,
            data=r.response
        )

    async def consume(self) -> None:
        """ Mark the entitlement as consumed. """
        await self._state.query(
            "POST",
            f"/applications/{self._state.application_id}/entitlements/{self.id}/consume",
            res_method="text"
        )

    async def delete_test_entitlement(self) -> None:
        """ Deletes a test entitlement. """
        await self._state.query(
            "DELETE",
            f"/applications/{self._state.application_id}/entitlements/{self.id}",
            res_method="text"
        )


class Entitlements(PartialEntitlements):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.deleted: bool = data["deleted"]
        self.type: EntitlementType = EntitlementType(data["type"])

        self.user: Optional[PartialUser] = None
        self.guild: Optional[PartialGuild] = None
        self.application: PartialUser = PartialUser(
            state=self._state,
            id=int(data["application_id"])
        )
        self.sku: PartialSKU = PartialSKU(
            state=self._state,
            id=int(data["sku_id"])
        )

        self.starts_at: Optional[datetime] = None
        self.ends_at: Optional[datetime] = None

        self._from_data(data)
        self._data_consumed: bool = data.get("consumed", False)

    def __repr__(self) -> str:
        return f"<Entitlements id={self.id} sku={self.sku} type={self.type}>"

    def __str__(self) -> str:
        return f"{self.sku}"

    def _from_data(self, data: dict):
        if data.get("user_id", None):
            self.user = PartialUser(state=self._state, id=int(data["user_id"]))

        if data.get("guild_id", None):
            self.guild = PartialGuild(state=self._state, id=int(data["guild_id"]))

        if data.get("starts_at", None):
            self.starts_at = utils.parse_time(data["starts_at"])

        if data.get("ends_at", None):
            self.ends_at = utils.parse_time(data["ends_at"])

    def is_consumed(self) -> bool:
        """ `bool`: Returns whether the entitlement is consumed or not. """
        return bool(self._data_consumed)
