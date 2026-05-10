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

    def __repr__(self) -> str:
        return f"<PartialIntegration id={self.id} guild_id={self.guild_id} application_id={self.application_id}>"

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
        "account",
        "application",
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
        "user",
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

        self._state: "DiscordAPI" = state

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

        self.user: User | None = None
        """ The user associated with this integration, if available. """

        self.account: IntegrationAccount | None = None
        """ The account associated with this integration, if available. """

        self.application: IntegrationApplication | None = None
        """ The bot/OAuth2 application for discord integrations, if available. """

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Integration id={self.id} name={self.name} type={self.type}>"

    def _from_data(self, data: dict) -> None:
        if data.get("user"):
            self.user = User(state=self._state, data=data["user"])

        if data.get("account"):
            self.account = IntegrationAccount(state=self._state, data=data["account"])

        if data.get("application"):
            self.application = IntegrationApplication(state=self._state, data=data["application"])

    @property
    def bot(self) -> User | None:
        """
        Alias for `application.bot`.

        The bot user associated with this integration, if available.
        """
        return self.application.bot if self.application else None


class IntegrationApplication(PartialBase):
    """ Represents a bot/OAuth2 application for integrations. """

    __slots__ = (
        "_state",
        "bot",
        "description",
        "icon",
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

        self.bot: User | None = None
        """ The bot associated with this application, if available. """

        self.icon: Asset | None = None
        """ The icon of the application, if available. """

        self._from_data(data)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<IntegrationApplication id={self.id} name={self.name}>"

    def _from_data(self, data: dict) -> None:
        """ Update the application with new data. """
        if data.get("bot"):
            self.bot = User(
                state=self._state,
                data=data["bot"]
            )

        if data.get("icon"):
            self.icon = Asset._from_icon(
                state=self._state,
                object_id=self.id,
                icon_hash=data["icon"],
                path="app"
            )
