import sys

from typing import TYPE_CHECKING

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
    """ Represents a partial role object. """

    __slots__ = (
        "_state",
        "_target_type",
        "guild_id",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # ruff: ignore[builtin-argument-shadowing]
        guild_id: int
    ):
        super().__init__(id=int(id))
        self._state = state
        self._target_type: PermissionType = PermissionType.role

        self.guild_id: int = guild_id
        """ The ID of the guild this role is in. """

    def __repr__(self) -> str:
        return f"<PartialRole id={self.id} guild_id={self.guild_id}>"

    def __str__(self) -> str:
        return "PartialRole"

    @property
    def guild(self) -> "Guild | PartialGuild":
        """ The guild this role is in. """
        if cache := self._state.cache.get_guild(self.guild_id):
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def mention(self) -> str:
        """ A string that mentions the role. """
        return f"<@&{self.id}>"

    def is_default_role(self) -> bool:
        """ Returns whether the role is the default @everyone role. """
        return self.id == self.guild_id

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
        user_id
            The user ID to add the role to
        reason
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
        user_id
            The user ID to remove the role from
        reason
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
        reason
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
        color: tuple[Colour | int, ...] | Colour | int | None = MISSING,
        colour: tuple[Colour | int, ...] | Colour | int | None = MISSING,
        hoist: bool | None = MISSING,
        mentionable: bool | None = MISSING,
        positions: int | None = MISSING,
        permissions: "Permissions | None" = MISSING,
        unicode_emoji: str | None = MISSING,
        icon: File | bytes | None = MISSING,
        reason: str | None = None,
    ) -> "Role":
        """
        Edit the role.

        Parameters
        ----------
        name
            The new name of the role
        color
            Alias for colour
        colour
            The new colour of the role.
            If tuple is provided, it switches to the new gradient role colours.
            The third value must be one of the following:
            - 16761760
            - 11127295
            - 16759788
        hoist
            Whether the role should be displayed separately in the sidebar
        mentionable
            Whether the role should be mentionable
        unicode_emoji
            The new unicode emoji of the role
        positions
            The new position of the role
        permissions
            The new permissions for the role
        icon
            The new icon of the role
        reason
            The reason for editing the role

        Returns
        -------
            The edited role and its data

        Raises
        ------
        ValueError
            - If both `unicode_emoji` and `icon` are set
            - If there were no changes applied to the role
            - If position was changed, but Discord API returned invalid data
        """
        payload = {}
        role: "Role | None" = None

        if name is not MISSING:
            payload["name"] = name

        colour = color or colour
        if colour is not MISSING:
            if isinstance(colour, tuple):
                payload["colors"] = {}
                names = ["primary_color", "secondary_color", "tertiary_color"]
                for i, c in enumerate(colour[:3]):
                    payload["colors"][names[i]] = int(c)

                # Just to make sure Discord API does not break
                # And making default get value the valid one to not change if not provided
                if payload["colors"].get("tertiary_color", 16761760) not in (11127295, 16759788, 16761760):
                    # Discord does not allow anything else, might change later
                    payload["colors"]["tertiary_color"] = 16761760

            elif isinstance(colour, int | Colour):
                payload["color"] = int(colour)

            else:
                raise TypeError(f"colour must be an int or Colour, not {type(colour)}")

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
    """ Represents a role object. """

    _FLAG_HOIST = 1 << 0
    _FLAG_MANAGED = 1 << 1
    _FLAG_MENTIONABLE = 1 << 2
    _FLAG_PREMIUM_SUBSCRIBER = 1 << 3
    _FLAG_AVAILABLE_FOR_PURCHASE = 1 << 4
    _FLAG_GUILD_CONNECTIONS = 1 << 5

    __slots__ = (
        "_extra_ids",
        "_flags",
        "_raw_colour",
        "_raw_icon",
        "_raw_permissions",
        "name",
        "position",
        "unicode_emoji",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        guild: "Guild | PartialGuild",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]), guild_id=guild.id)

        self.name: str = sys.intern(data["name"])
        """ The name of the role. """

        self.position: int = int(data["position"])
        """ The position of the role in the role hierarchy. """

        tags: dict = data.get("tags", {})

        self._flags: int = (
            (self._FLAG_HOIST if data["hoist"] else 0) |
            (self._FLAG_MANAGED if data.get("managed") else 0) |
            (self._FLAG_MENTIONABLE if data.get("mentionable") else 0) |
            (self._FLAG_PREMIUM_SUBSCRIBER if "premium_subscriber" in tags else 0) |
            (self._FLAG_AVAILABLE_FOR_PURCHASE if "available_for_purchase" in tags else 0) |
            (self._FLAG_GUILD_CONNECTIONS if "guild_connections" in tags else 0)
        )

        extra_ids = (
            utils.get_int(tags, "bot_id"),
            utils.get_int(tags, "integration_id"),
            utils.get_int(tags, "subscription_listing_id"),
        )
        self._extra_ids: tuple[int | None, int | None, int | None] | None = (
            extra_ids if any(extra_ids) else None
        )

        self.unicode_emoji: str | None = data.get("unicode_emoji")
        """ The unicode emoji associated with the role, if any. """

        self._raw_icon: str | None = data.get("icon")
        self._raw_permissions: int = int(data["permissions"])
        self._raw_colour: int = int(data["color"])

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Role id={self.id} name='{self.name}'>"

    @property
    def hoist(self) -> bool:
        """ Whether the role is displayed separately in the sidebar. """
        return bool(self._flags & self._FLAG_HOIST)

    @property
    def managed(self) -> bool:
        """ Whether the role is managed by an integration. """
        return bool(self._flags & self._FLAG_MANAGED)

    @property
    def mentionable(self) -> bool:
        """ Whether the role is mentionable. """
        return bool(self._flags & self._FLAG_MENTIONABLE)

    @property
    def permissions(self) -> Permissions:
        """ The permissions of the role. """
        return Permissions(self._raw_permissions)

    @property
    def colour(self) -> Colour:
        """ The colour of the role. """
        return Colour(self._raw_colour)

    @property
    def tags(self) -> dict:
        """ The tags of the role, such as `premium_subscriber`, `available_for_purchase`, `guild_connections`, etc. """
        tags: dict = {}

        if self._flags & self._FLAG_PREMIUM_SUBSCRIBER:
            tags["premium_subscriber"] = None
        if self._flags & self._FLAG_AVAILABLE_FOR_PURCHASE:
            tags["available_for_purchase"] = None
        if self._flags & self._FLAG_GUILD_CONNECTIONS:
            tags["guild_connections"] = None

        if self._extra_ids is not None:
            bot_id, integration_id, subscription_listing_id = self._extra_ids
            if bot_id is not None:
                tags["bot_id"] = str(bot_id)
            if integration_id is not None:
                tags["integration_id"] = str(integration_id)
            if subscription_listing_id is not None:
                tags["subscription_listing_id"] = str(subscription_listing_id)

        return tags

    @property
    def bot_id(self) -> int | None:
        """ The ID of the bot that manages the role, if any. """
        return self._extra_ids[0] if self._extra_ids is not None else None

    @property
    def integration_id(self) -> int | None:
        """ The ID of the integration that manages the role, if any. """
        return self._extra_ids[1] if self._extra_ids is not None else None

    @property
    def subscription_listing_id(self) -> int | None:
        """ The ID of the subscription listing for the role, if any. """
        return self._extra_ids[2] if self._extra_ids is not None else None

    @property
    def icon(self) -> Asset | None:
        """ The icon of the role if it's custom. """
        if self._raw_icon is None:
            return None

        return Asset._from_icon(
            state=self._state,
            object_id=self.id,
            icon_hash=self._raw_icon,
            path="role"
        )

    @property
    def display_icon(self) -> Asset | str | None:
        """ The display icon of the role. """
        return self.icon or self.unicode_emoji

    def is_bot_managed(self) -> bool:
        """ Returns whether the role is bot managed. """
        return self.bot_id is not None

    def is_integration(self) -> bool:
        """ Returns whether the role is an integration. """
        return self.integration_id is not None

    def is_premium_subscriber(self) -> bool:
        """ Returns whether the role is a premium subscriber. """
        return bool(self._flags & self._FLAG_PREMIUM_SUBSCRIBER)

    def is_available_for_purchase(self) -> bool:
        """ Returns whether the role is available for purchase. """
        return bool(self._flags & self._FLAG_AVAILABLE_FOR_PURCHASE)

    def is_guild_connection(self) -> bool:
        """ Returns whether the role is a guild connection. """
        return bool(self._flags & self._FLAG_GUILD_CONNECTIONS)
