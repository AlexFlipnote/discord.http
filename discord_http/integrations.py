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
    """ Represents an account associated with an integration. """

    __slots__ = ("_state", "id", "name",)

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ) -> None:
        self._state = state

        self.name: str = data.get("name", "")
        """ The name of the account. """

        self.id: str | int = str(data["id"])
        """ The ID of the account. """

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
    """ Represents a bot/OAuth2 application for integrations. """

    __slots__ = (
        "_bot",
        "_icon",
        "_state",
        "description",
        "is_discoverable",
        "is_monetized",
        "is_verified",
        "name",
        "summary",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
    ) -> None:
        super().__init__(id=int(data["id"]))

        self._state: "DiscordAPI" = state
        self._icon: str | None = data["icon"]
        self._bot: dict | None = data.get("bot")

        self.name: str = data["name"]
        """ The name of the application. """

        self.description: str = data["description"]
        """ The description of the application. """

        self.summary: str = data.get("summary", "")
        """ The summary of the application. """

        self.is_monetized: bool = data.get("is_monetized", False)
        """ Whether the application is monetized. """

        self.is_verified: bool = data.get("is_verified", False)
        """ Whether the application is verified. """

        self.is_discoverable: bool = data.get("is_discoverable", False)
        """ Whether the application is discoverable. """

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
    """

    __slots__ = (
        "_state",
        "application_id",
        "guild_id",
    )

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
        """ The guild associated with this integration. """

        self.application_id: int | None = (
            int(application_id)
            if application_id else None
        )
        """ The ID of the application associated with this integration. """

    def __str__(self) -> str:
        return "PartialIntegration"

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
    """ Represents a guild integration. """

    __slots__ = (
        "_account",
        "_application",
        "_bot",
        "_user",
        "enable_emoticons",
        "enabled",
        "expire_behavior",
        "expire_grace_period",
        "name",
        "revoked",
        "role_id",
        "scopes",
        "subscriber_count",
        "synced_at",
        "syncing",
        "type",
    )

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
        self._bot: dict | None = data.get("bot")
        self._account: dict | None = data.get("account")

        self.name: str = data["name"]
        """ The name of the integration. """

        self.type: str = data["type"]
        """ The type of the integration. (e.g. "twitch", "youtube" or "discord"). """

        self.enabled: bool = data["enabled"]
        """ Whether the integration is enabled. """

        self.syncing: bool = data.get("syncing", False)
        """ Whether the integration is syncing. This is not applicable to bot integrations. """

        self.role_id: int | None = data.get("role_id")
        """ ID of the role that the integration uses for "subscribers". TThis is not applicable to bot integrations. """

        self.enable_emoticons: bool = data.get("enable_emoticons", False)
        """ Whether emoticons should be synced for this integration (twitch only currently) This is not applicable to bot integrations. """

        self.expire_behavior: ExpireBehaviour | None = (
            ExpireBehaviour(expire_behavior)
            if (expire_behavior := data.get("expire_behavior"))
            else None
        )
        """ The behavior of expiring subscribers. This is not applicable to bot integrations. """

        self.expire_grace_period: int | None = data.get("expire_grace_period")
        """ The grace period before expiring subscribers. This is not applicable to bot integrations. """

        self.synced_at: datetime | None = (
            utils.parse_time(synced_at)
            if (synced_at := data.get("synced_at"))
            else None
        )
        """ The time the integration was last synced. This is not applicable to bot integrations. """

        self.subscriber_count: int = data.get("subscriber_count", 0)
        """ The number of subscribers for the integration. This is not applicable to bot integrations. """

        self.revoked: bool = data.get("revoked", False)
        """ Whether the integration has been revoked. """

        self.scopes: list[str] = data.get("scopes", [])
        """ The scopes of the application has been granted. """

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
    def bot(self) -> User | None:
        """ The bot associated with this integration, if available."""
        if not self._bot:
            return None

        return User(
            state=self._state,
            data=self._bot
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
