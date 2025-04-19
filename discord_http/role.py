from typing import TYPE_CHECKING, Union, Optional

from . import utils
from .asset import Asset
from .colour import Colour
from .file import File
from .flags import Permissions, PermissionType
from .object import PartialBase, Snowflake

if TYPE_CHECKING:
    from .guild import PartialGuild, Guild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "PartialRole",
    "Role",
)


class PartialRole(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        guild_id: int
    ):
        super().__init__(id=int(id))
        self._state = state
        self._target_type: PermissionType = PermissionType.role

        self.guild_id: int = guild_id

    def __repr__(self) -> str:
        return f"<PartialRole id={self.id} guild_id={self.guild_id}>"

    @property
    def guild(self) -> "Guild | PartialGuild":
        """ Returns the guild this role is in. """
        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def mention(self) -> str:
        """ Returns a string that mentions the role. """
        return f"<@&{self.id}>"

    async def add_role(
        self,
        user_id: Snowflake | int,
        *,
        reason: str | None = None
    ) -> None:
        """
        Add the role to someone.

        Parameters
        ----------
        user_id:
            The user ID to add the role to
        reason:
            The reason for adding the role
        """
        await self._state.query(
            "PUT",
            f"/guilds/{self.guild_id}/members/{int(user_id)}/roles/{self.id}",
            res_method="text",
            reason=reason
        )

    async def remove_role(
        self,
        user_id: Snowflake | int,
        *,
        reason: str | None = None
    ) -> None:
        """
        Remove the role from someone.

        Parameters
        ----------
        user_id:
            The user ID to remove the role from
        reason:
            The reason for removing the role
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild_id}/members/{int(user_id)}/roles/{self.id}",
            res_method="text",
            reason=reason
        )

    async def delete(
        self,
        *,
        reason: str | None = None
    ) -> None:
        """
        Delete the role.

        Parameters
        ----------
        reason:
            The reason for deleting the role
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild_id}/roles/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def edit(
        self,
        *,
        name: str | None = MISSING,
        colour: Colour | int | None = MISSING,
        hoist: bool | None = MISSING,
        mentionable: bool | None = MISSING,
        positions: int | None = MISSING,
        permissions: Optional["Permissions"] = MISSING,
        unicode_emoji: str | None = MISSING,
        icon: File | bytes | None = MISSING,
        reason: str | None = None,
    ) -> "Role":
        """
        Edit the role.

        Parameters
        ----------
        name:
            The new name of the role
        colour:
            The new colour of the role
        hoist:
            Whether the role should be displayed separately in the sidebar
        mentionable:
            Whether the role should be mentionable
        unicode_emoji:
            The new unicode emoji of the role
        positions:
            The new position of the role
        permissions:
            The new permissions for the role
        icon:
            The new icon of the role
        reason:
            The reason for editing the role

        Returns
        -------
            The edited role and its data

        Raises
        ------
        `ValueError`
            - If both `unicode_emoji` and `icon` are set
            - If there were no changes applied to the role
            - If position was changed, but Discord API returned invalid data
        """
        payload = {}
        role: "Role | None" = None

        if name is not MISSING:
            payload["name"] = name
        if colour is not MISSING:
            if isinstance(colour, Colour):
                payload["color"] = colour.value
            else:
                payload["color"] = colour
        if permissions is not MISSING:
            payload["permissions"] = permissions.value
        if hoist is not MISSING:
            payload["hoist"] = hoist
        if mentionable is not MISSING:
            payload["mentionable"] = mentionable

        if unicode_emoji is not MISSING:
            payload["unicode_emoji"] = unicode_emoji

        if icon is not MISSING:
            payload["icon"] = (
                utils.bytes_to_base64(icon)
                if icon else None
            )

        if (
            unicode_emoji is not MISSING and
            icon is not MISSING
        ):
            raise ValueError("Cannot set both unicode_emoji and icon")

        if positions is not MISSING:
            r = await self._state.query(
                "PATCH",
                f"/guilds/{self.guild_id}/roles",
                json={
                    "id": str(self.id),
                    "position": positions
                },
                reason=reason
            )

            find_role: dict | None = next((
                r for r in r.response
                if r["id"] == str(self.id)
            ), None)

            if not find_role:
                raise ValueError(
                    "Could not find role in response "
                    "(Most likely Discord API bug)"
                )

            role = Role(
                state=self._state,
                guild=self.guild,
                data=find_role
            )

        if payload:
            r = await self._state.query(
                "PATCH",
                f"/guilds/{self.guild_id}/roles/{self.id}",
                json=payload,
                reason=reason
            )

            role = Role(
                state=self._state,
                guild=self.guild,
                data=r.response
            )

        if not role:
            raise ValueError(
                "There were no changes applied to the role. "
                "No edits were taken"
            )

        return role


class Role(PartialRole):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: Union["PartialGuild", "Guild"],
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]), guild_id=guild.id)

        self.name: str = data["name"]
        self.hoist: bool = data["hoist"]
        self.managed: bool = data.get("managed", False)
        self.mentionable: bool = data.get("mentionable", False)
        self.permissions: Permissions = Permissions(int(data["permissions"]))
        self.colour: Colour = Colour(int(data["color"]))
        self.position: int = int(data["position"])
        self.tags: dict = data.get("tags", {})

        self.bot_id: int | None = utils.get_int(data, "bot_id")
        self.integration_id: int | None = utils.get_int(data, "integration_id")
        self.subscription_listing_id: int | None = utils.get_int(data, "subscription_listing_id")
        self.unicode_emoji: str | None = data.get("unicode_emoji")

        self._premium_subscriber: bool = "premium_subscriber" in self.tags
        self._available_for_purchase: bool = "available_for_purchase" in self.tags
        self._guild_connections: bool = "guild_connections" in self.tags
        self._icon: str | None = data.get("icon")

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Role id={self.id} name='{self.name}'>"

    @property
    def icon(self) -> Asset | None:
        """ Returns the icon of the role if it's custom. """
        if self._icon is None:
            return None

        return Asset._from_icon(
            state=self._state,
            object_id=self.id,
            icon_hash=self._icon,
            path="role"
        )

    @property
    def display_icon(self) -> Asset | str | None:
        """ Returns the display icon of the role. """
        return self.icon or self.unicode_emoji

    def is_bot_managed(self) -> bool:
        """ Returns whether the role is bot managed. """
        return self.bot_id is not None

    def is_integration(self) -> bool:
        """ Returns whether the role is an integration. """
        return self.integration_id is not None

    def is_premium_subscriber(self) -> bool:
        """ Returns whether the role is a premium subscriber. """
        return self._premium_subscriber

    def is_available_for_purchase(self) -> bool:
        """ Returns whether the role is available for purchase. """
        return self._available_for_purchase

    def is_guild_connection(self) -> bool:
        """ Returns whether the role is a guild connection. """
        return self._guild_connections
