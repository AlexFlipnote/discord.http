from datetime import datetime
from typing import TYPE_CHECKING

from . import utils
from .object import PartialBase
from .asset import Asset
from .enums import ExpireBehaviour
from .user import User

if TYPE_CHECKING:
    from .http import DiscordAPI

    from .guild import PartialGuild, Guild

class PartialIntegration(PartialBase):
    """Represents a partial integration object.

    This is mosly used to get the ids of objects if not in cache.

    Attributes
    ----------
    id: :class:`int`
        The ID of the integration.
    guild: :class:`PartialGuild` | :class:`Guild`
        The guild associated with this integration.
    application_id: Optional[:class:`int`]
        The ID of the application associated with this integration.
    """

    __slots__ = ("id", "guild", "application_id")
    def __init__(
        self,
        *,
        id: str,
        guild: "PartialGuild | Guild",
        application_id: int | None = None,
    ) -> None:
        super().__init__(id=int(id))
        self.guild: "PartialGuild | Guild" = guild
        self.application_id: int | None = (
            int(application_id)
            if application_id else None
        )

class IntegrationAccount(PartialBase):
    """Represents an integration's account.

    Attributes
    ----------
    id: :class:`int`
        The ID of the account.
    name: :class:`str`
        The name of the account.
    """
    __slots__ = ("id", "name",)
    def __init__(
        self,
        *,
        id: str,
        name: str
    ) -> None:
        super().__init__(id=int(id))
        self.name: str = name


class IntegrationApplication(PartialBase):
    """Represents a bot/OAuth2 application
    for integrations

    Attributes
    ----------
    id: :class:`int`
        The ID of the application.
    name: :class:`str`
        The name of the application.
    description: :class:`str`
        The description of the application.
    """
    __slots__ = (
        "_state",
        "_bot"
        "_icon",
        "id",
        "name",
        "description",
    )
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ) -> None:
        super().__init__(id=data["id"])

        self._state: "DiscordAPI" = state

        self.name: str = data["name"]
        self._icon: str | None = data["icon"]
        self.description: str = data["description"]
        self._bot: dict | None = data.get("bot")

    @property
    def icon(self) -> Asset | None:
        """Optional[:class:`Asset`]: The icon of the application, if available."""
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
        """Optional[:class:`User`]: The bot associated with this
        application, if available.
        """
        if not self._bot:
            return None

        return User(
            state=self._state,
            data=self._bot
        )



class Integration(PartialIntegration):
    """Represents a guild integration.

    Attributes
    ----------
    id: :class:`int`
        The ID of the integration.
    name: :class:`str`
        The name of the integration.
    guild: class:`PartialGuild` | :class:`Guild`
        The guild associated with this integration.
    type: :class:`str`
        The type of the integration.
        (e.g. "twitch", "youtube" or "discord")
    enabled: :class:`bool`
        Whether the integration is enabled.
    syncing: :class:`bool`
        Whether the integration is syncing.

        This is not applicable to bot integrations.
    role_id: Optional[:class:`int`]
        ID of the role that the integration uses for "subscribers".

        TThis is not applicable to bot integrations.
    enable_emoticons: :class:`bool`
    	Whether emoticons should be synced for this
        integration (twitch only currently)

        This is not applicable to bot integrations.
    expire_behavior: Optional[:class:`ExpireBehaviour`]
        The behavior of expiring subscribers.

        This is not applicable to bot integrations.
    expire_grace_period: Optional[:class:`int`]
        The grace period before expiring subscribers.

        This is not applicable to bot integrations.
    synced_at: Optional[:class:`datetime`]
        The time the integration was last synced.

        This is not applicable to bot integrations.
    subscriber_count: :class:`int`
        The number of subscribers for the integration.

        This is not applicable to bot integrations.
    revoked: :class:`bool`
        Whether the integration has been revoked.
    scopes: List[:class:`str`]
        The scopes of the application has been granted.
    """
    __slots__ = (
        "_state",
        "_user",
        "_application",
        "_account",
        "id",
        "name",
        "type",
        "enabled",
        "syncing",
        "role_id",
        "enable_emoticons",
        "expire_behavior",
        "expire_grace_period",
        "synced_at",
        "subscriber_count",
        "revoked",
        "scopes"
    )
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | Guild"
    ) -> None:
        super().__init__(
            id=data["id"],
            guild=guild,
            application_id=data.get("application", {}.get("id"))
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
        """Optional[:class:`User`]: The user associated with this integration, if available."""
        if not self._user:
            return None

        return User(
            state=self._state,
            data=self._user
        )

    @property
    def account(self) -> IntegrationAccount | None:
        """Optional[:class:`IntegrationAccount`]: The account associated with this integration, if available."""
        if not self._account:
            return None

        return IntegrationAccount(
            id=self._account["id"],
            name=self._account["name"]
        )

    @property
    def application(self) -> IntegrationApplication | None:
        """Optional[:class:`IntegrationApplication`]: The bot/OAuth2 application for discord integrations, if available."""
        if not self._application:
            return None

        return IntegrationApplication(
            state=self._state,
            data=self._application
        )

    async def delete(self) -> None:
        """Delete this integration for the guild.

        This deletes any associated webhooks and
        kicks the associated bot if there is one.

        This requires the `MANAGE_GUILD` permission.
        """
        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild.id}/integrations/{self.id}"
        )

