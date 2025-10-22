from datetime import datetime
from typing import TYPE_CHECKING

from . import utils
from .asset import Asset
from .enums import ExpireBehaviour
from .object import PartialBase
from .user import User

if TYPE_CHECKING:
    from .http import DiscordAPI
    from .guild import PartialGuild, Guild


class IntegrationAccount:
    """
    Represents an account associated with an integration.

    Attributes
    ----------
    id: str | int
        The ID of the account.
    name: str
        The name of the account.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ) -> None:
        self._state = state
        self.name: str = data.get("name", "")

        self.id: str | int = str(data["id"])
        if self.id.isdigit():
            self.id = int(self.id)

    def __repr__(self) -> str:
        return f"<IntegrationAccount id={self.id} name={self.name}>"

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        if not isinstance(self.id, int):
            raise TypeError("IntegrationAccount.id is not an int")
        return self.id


class IntegrationApplication(PartialBase):
    """
    Represents a bot/OAuth2 application for integrations.

    Attributes
    ----------
    name: str
        The name of the application.
    description: str
        The description of the application.
    summary: str
        The summary of the application.
    is_monetized: bool
        Whether the application is monetized.
    is_verified: bool
        Whether the application is verified.
    is_discoverable: bool
        Whether the application is discoverable.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ) -> None:
        super().__init__(id=int(data["id"]))

        self._state: "DiscordAPI" = state

        self.name: str = data["name"]
        self._icon: str | None = data["icon"]
        self.description: str = data["description"]
        self._bot: dict | None = data.get("bot")

        self.summary: str = data.get("summary", "")
        self.is_monetized: bool = data.get("is_monetized", False)
        self.is_verified: bool = data.get("is_verified", False)
        self.is_discoverable: bool = data.get("is_discoverable", False)

    @property
    def icon(self) -> Asset | None:
        """ The icon of the application, if available."""
        if not self._icon:
            return None

        return Asset._from_icon(
            state=self._state,
            object_id=self.id,
            icon_hash=self._icon,
            path="app"
        )

    @property
    def bot(self) -> User | None:
        """ The bot associated with this application, if available. """
        if not self._bot:
            return None

        return User(
            state=self._state,
            data=self._bot
        )


class PartialIntegration(PartialBase):
    """
    Represents a partial integration object.

    This is mosly used to get the ids of objects if not in cache.

    Attributes
    ----------
    guild_id: int
        The guild associated with this integration.
    application_id: int | None
        The ID of the application associated with this integration.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        guild_id: int,
        application_id: int | None = None,
    ) -> None:
        super().__init__(id=int(id))
        self._state = state
        self.guild_id: int = guild_id
        self.application_id: int | None = (
            int(application_id)
            if application_id else None
        )

    @property
    def guild(self) -> "PartialGuild | Guild":
        """:class:`PartialGuild` | :class:`Guild`: The guild associated with this integration."""
        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    async def delete(self) -> None:
        """
        Delete this integration for the guild.

        This deletes any associated webhooks and
        kicks the associated bot if there is one.

        This requires the `MANAGE_GUILD` permission.
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild.id}/integrations/{self.id}",
            res_method="text"
        )


class Integration(PartialIntegration):
    """
    Represents a guild integration.

    Attributes
    ----------
    id: int
        The ID of the integration.
    name: str
        The name of the integration.
    guild: PartialGuild | Guild
        The guild associated with this integration.
    type: str
        The type of the integration.
        (e.g. "twitch", "youtube" or "discord")
    enabled: bool
        Whether the integration is enabled.
    syncing: bool
        Whether the integration is syncing.
        This is not applicable to bot integrations.
    role_id: int | None
        ID of the role that the integration uses for "subscribers".
        TThis is not applicable to bot integrations.
    enable_emoticons: bool
        Whether emoticons should be synced for this
        integration (twitch only currently)
        This is not applicable to bot integrations.
    expire_behavior: ExpireBehaviour | None
        The behavior of expiring subscribers.
        This is not applicable to bot integrations.
    expire_grace_period: int | None
        The grace period before expiring subscribers.
        This is not applicable to bot integrations.
    synced_at: datetime | None
        The time the integration was last synced.
        This is not applicable to bot integrations.
    subscriber_count: int
        The number of subscribers for the integration.
        This is not applicable to bot integrations.
    revoked: bool
        Whether the integration has been revoked.
    scopes: list[str]
        The scopes of the application has been granted.
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | Guild"
    ) -> None:
        super().__init__(
            state=state,
            id=int(data["id"]),
            guild_id=guild.id,
            application_id=utils.get_int(data.get("application", {}), "id")
        )

        self._application: dict | None = data.get("application")
        self._state: "DiscordAPI" = state
        self._user: dict | None = data.get("user")
        self._account: dict | None = data.get("account")

        self.name: str = data["name"]
        self.type: str = data["type"]

        self.enabled: bool = data["enabled"]
        self.syncing: bool = data.get("syncing", False)
        self.role_id: int | None = data.get("role_id")
        self.enable_emoticons: bool = data.get("enable_emoticons", False)
        self.expire_behavior: ExpireBehaviour | None = (
            ExpireBehaviour(expire_behavior)
            if (expire_behavior := data.get("expire_behavior"))
            else None
        )
        self.expire_grace_period: int | None = data.get("expire_grace_period")
        self.synced_at: datetime | None = (
            utils.parse_time(synced_at)
            if (synced_at := data.get("synced_at"))
            else None
        )
        self.subscriber_count: int = data.get("subscriber_count", 0)
        self.revoked: bool = data.get("revoked", False)
        self.scopes: list[str] = data.get("scopes", [])

    @property
    def user(self) -> User | None:
        """ The user associated with this integration, if available."""
        if not self._user:
            return None

        return User(
            state=self._state,
            data=self._user
        )

    @property
    def account(self) -> IntegrationAccount | dict | None:
        """ The account associated with this integration, if available."""
        if not self._account:
            return None

        return IntegrationAccount(
            state=self._state,
            data=self._account
        )

    @property
    def application(self) -> IntegrationApplication | None:
        """ The bot/OAuth2 application for discord integrations, if available."""
        if not self._application:
            return None

        return IntegrationApplication(
            state=self._state,
            data=self._application
        )
