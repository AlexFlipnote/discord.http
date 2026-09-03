import sys

from typing import TYPE_CHECKING, Any, NamedTuple

from . import utils
from .asset import Asset
from .colour import Colour
from .embeds import Embed
from .enums import (
    DefaultAvatarType, DisplayNameEffectType, DisplayNameFontType,
    ApplicationEventWebhookStatus, TeamMembershipState,
    ApplicationRoleConnectionMetadataType
)
from .file import File
from .flags import UserFlags, MessageFlags, ApplicationFlags
from .mentions import AllowedMentions
from .object import PartialBase, Snowflake
from .response import ResponseType, MessageResponse
from .view import View

if TYPE_CHECKING:
    from .entitlements import PartialSKU
    from .channel import DMChannel
    from .guild import Guild, PartialGuild
    from .http import DiscordAPI
    from .message import Message

MISSING = utils.MISSING

__all__ = (
    "Application",
    "ApplicationRoleConnectionMetadata",
    "AvatarDecoration",
    "DisplayNameStyles",
    "Nameplate",
    "PartialUser",
    "PrimaryGuild",
    "Team",
    "TeamMember",
    "User",
)


class DisplayNameStyles:
    """
    Represents the display name style of a user.

    .. warning::
        This is not officially documented by Discord, things can change.
    """

    __slots__ = (
        "colours",
        "effect",
        "font",
    )

    def __init__(self, data: dict):
        self.colours: list[Colour] = [Colour(g) for g in data.get("colors", [])]
        """ The colors of the display name, if any. """

        self.font: DisplayNameFontType = DisplayNameFontType(
            data.get("font_id", int(DisplayNameFontType.default))
        )
        """ The font of the display name, if any. """

        self.effect: DisplayNameEffectType = DisplayNameEffectType(
            data.get("effect_id", int(DisplayNameEffectType.solid))
        )
        """ The effect of the display name, if any. """

    def __repr__(self) -> str:
        return (
            f"<DisplayNameStyles colours={self.colours} font={self.font} "
            f"effect={self.effect}>"
        )

    def to_dict(self) -> dict:
        """ Converts the display name style to a dictionary. """
        return {
            "colors": [int(c) for c in self.colours],
            "font_id": int(self.font),
            "effect_id": int(self.effect)
        }

    @classmethod
    def create(
        cls,
        *,
        colours: list[Colour] | Colour,
        font: DisplayNameFontType,
        effect: DisplayNameEffectType,
    ) -> "DisplayNameStyles":
        """
        Creates a display name style object.

        Used to easily have an object to pass to the API when
        editing the application's display name style.

        Parameters
        ----------
        colours
            The colors of the display name, if any.
        font
            The font of the display name, if any.
        effect
            The effect of the display name, if any.

        Returns
        -------
            The display name style object.
        """
        if not isinstance(colours, list):
            colours = [colours]

        return cls(data={
            "colors": [int(c) for c in colours],
            "font_id": int(font),
            "effect_id": int(effect)
        })


class Nameplate:
    """ Represents a nameplate collectible of a user. """

    __slots__ = (
        "_state",
        "asset",
        "label",
        "palette",
        "sku_id",
    )

    def __init__(self, state: "DiscordAPI", data: dict):
        self._state = state

        self.sku_id: int = int(data["sku_id"])
        """ The ID of the SKU associated with the nameplate. """

        self.label: str = data["label"]
        """ The label of the nameplate. """

        self.palette: str = data["palette"]
        """ The palette of the nameplate. """

        self.asset: Asset = Asset._from_collectibles(state, data["asset"])
        """ The asset of the nameplate. """

    def __repr__(self) -> str:
        return f"<Nameplate sku_id={self.sku_id} label='{self.label}' palette='{self.palette}'>"

    def __str__(self) -> str:
        return self.asset.url

    @property
    def shop_url(self) -> str:
        """ The URL of the avatar decoration asset. """
        return f"https://discord.com/shop#itemSkuId={self.sku_id}"


class PrimaryGuild:
    """
    Represents a primary guild of a user.

    This is commonly known as 'clan'.
    """

    __slots__ = (
        "_state",
        "badge",
        "guild_id",
        "tag",
    )

    def __init__(self, state: "DiscordAPI", data: dict):
        self._state = state

        self.guild_id: int | None = utils.get_int(data, "identity_guild_id")
        """ The ID of the guild. """

        self.tag: str | None = sys.intern(t) if (t := data.get("tag")) else None
        """ The tag of the guild, if any. """

        self.badge: Asset | None = None
        """ The badge of the guild, if any. """

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<PrimaryGuild guild_id={self.guild_id} tag='{self.tag}'>"

    def _from_data(self, data: dict) -> None:
        if self.guild_id and (badge := data.get("badge")):
            self.badge = Asset._from_guild_clan_badge(
                self._state, self.guild_id, badge
            )

    def guild(self) -> "Guild | PartialGuild | None":
        """ Returns the guild object. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        return self._state.bot.get_partial_guild(
            self.guild_id
        )


class AvatarDecoration(Snowflake):
    """ Represents an avatar decoration of a user. """

    __slots__ = (
        "_state",
        "asset",
        "sku_id",
    )

    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(id=int(data["sku_id"]))
        self._state = state

        self.sku_id: int = int(data["sku_id"])
        """ The ID of the SKU associated with the avatar decoration. """

        self.asset = Asset._from_avatar_decoration(
            self._state, data["asset"]
        )
        """ The asset of the avatar decoration. """

    def __repr__(self) -> str:
        return f"<AvatarDecoration sku_id={self.sku_id} asset='{self.asset}'>"

    def __str__(self) -> str:
        return self.asset.url

    @property
    def shop_url(self) -> str:
        """ The URL of the avatar decoration asset. """
        return f"https://discord.com/shop#itemSkuId={self.sku_id}"


class PartialUser(PartialBase):
    """ Represents a partial user object. """

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
        return f"<PartialUser id={self.id}>"

    def __str__(self) -> str:
        return "PartialUser"

    @property
    def mention(self) -> str:
        """ A string that allows you to mention the user. """
        return f"<@!{self.id}>"

    @property
    def default_avatar(self) -> Asset:
        """ The default avatar of the user. """
        return Asset._from_default_avatar(
            self._state,
            (self.id >> 22) % len(DefaultAvatarType)
        )

    @property
    def display_avatar(self) -> Asset:
        """ The display avatar of the member. """
        return self.default_avatar

    async def send(
        self,
        content: str | None = MISSING,
        *,
        channel_id: int | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        view: View | None = MISSING,
        tts: bool | None = False,
        type: ResponseType | int = 4,  # ruff: ignore[builtin-argument-shadowing]
        flags: MessageFlags | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        delete_after: float | None = None
    ) -> "Message":
        """
        Send a message to the user.

        Parameters
        ----------
        content
            Content of the message
        channel_id
            Channel ID to send the message to, if not provided, it will create a DM channel
        embed
            Embed of the message
        embeds
            Embeds of the message
        file
            File of the message
        files
            Files of the message
        view
            Components of the message
        tts
            Whether the message should be sent as TTS
        type
            Which type of response should be sent
        flags
            Flags of the message
        allowed_mentions
            Allowed mentions of the message
        delete_after
            How long to wait before deleting the message

        Returns
        -------
            The message that was sent
        """
        if channel_id is MISSING:
            fetch_channel = await self.create_dm()
            channel_id = fetch_channel.id

        payload = MessageResponse(
            content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            view=view,
            tts=tts,
            type=type,
            flags=flags,
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            ),
        )

        r = await self._state.query(
            "POST",
            f"/channels/{channel_id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        from .message import Message
        msg = Message(
            state=self._state,
            data=r.response
        )

        if delete_after is not None:
            await msg.delete(delay=float(delete_after))
        return msg

    async def create_dm(self) -> "DMChannel":
        """ Creates a DM channel with the user. """
        r = await self._state.query(
            "POST",
            "/users/@me/channels",
            json={"recipient_id": self.id}
        )

        from .channel import DMChannel
        return DMChannel(
            state=self._state,
            data=r.response
        )

    async def fetch(self) -> "User":
        """ Fetches the user. """
        r = await self._state.query(
            "GET",
            f"/users/{self.id}"
        )

        return User(
            state=self._state,
            data=r.response
        )

    async def edit(
        self,
        *,
        username: str | None = MISSING,
        avatar: bytes | None = MISSING,
        banner: bytes | None = MISSING,
    ) -> "User":
        """
        Edit the user (only works for the current bot).

        Parameters
        ----------
        username
            The username to change the user to
        avatar
            New avatar for the user
        banner
            New banner for the user

        Returns
        -------
            The user that was edited
        """
        if self.id != self._state.bot.user.id:
            raise TypeError("Can only edit the bot user.")

        payload: dict[str, Any] = {}

        if username is not MISSING:
            payload["username"] = username

        if avatar is not MISSING:
            if avatar is not None:
                payload["avatar"] = utils.bytes_to_base64(avatar)
            else:
                payload["avatar"] = None

        if banner is not MISSING:
            if banner is not None:
                payload["banner"] = utils.bytes_to_base64(banner)
            else:
                payload["banner"] = None

        r = await self._state.query(
            "PATCH",
            "/users/@me",
            json=payload
        )

        return User(
            state=self._state,
            data=r.response
        )


class _UserExtra(NamedTuple):
    """ Raw values for the fields most users don't have set at all. """
    banner: str | None
    accent_colour: int | None
    banner_colour: str | None
    avatar_decoration: dict | None
    nameplate: dict | None
    name_style: dict | None
    primary_guild: dict | None


class User(PartialUser):
    """ Represents a user object. """

    __slots__ = (
        "__weakref__",
        "_extra",
        "_raw_avatar",
        "_raw_public_flags",
        "bot",
        "discriminator",
        "global_name",
        "name",
        "system",
        "verified",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.name: str = sys.intern(data["username"])
        """ The name of the user. """

        self.bot: bool = data.get("bot", False)
        """ Whether the user is a bot. """

        self.system: bool = data.get("system", False)
        """ Whether the user is a system user. """

        self.verified: bool = data.get("verified", False)
        """ Whether the user is verified (usually for bots). """

        # This section is ONLY here because bots still have a discriminator
        self.discriminator: str | None = data.get("discriminator")
        """ The discriminator of the user, if any. """

        if self.discriminator == "0":
            # Instead of showing "0", just make it None....
            self.discriminator = None

        self.global_name: str | None = sys.intern(g) if (g := data.get("global_name")) else None
        """ The global name of the user, if any. """

        self._from_data(data)

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} name='{self.name}' "
            f"global_name='{self.global_name}'>"
        )

    def __str__(self) -> str:
        if self.discriminator:
            return f"{self.name}#{self.discriminator}"
        return self.name

    def _from_data(self, data: dict) -> None:
        collectibles = data.get("collectibles", {}) or {}  # Fallback if None

        self._raw_avatar: str | None = data.get("avatar")
        self._raw_public_flags: int | None = data.get("public_flags")

        extra = _UserExtra(
            banner=data.get("banner"),
            accent_colour=data.get("accent_color"),
            banner_colour=data.get("banner_color"),
            avatar_decoration=data.get("avatar_decoration_data"),
            nameplate=collectibles.get("nameplate"),
            name_style=data.get("display_name_styles"),
            primary_guild=data.get("primary_guild"),
        )
        self._extra: _UserExtra | None = extra if any(extra) else None

    @property
    def avatar(self) -> Asset | None:
        """ The avatar of the user, if any. """
        if not self._raw_avatar:
            return None
        return Asset._from_avatar(self._state, self.id, self._raw_avatar)

    @property
    def public_flags(self) -> UserFlags | None:
        """ The public flags of the user, if any. """
        if not self._raw_public_flags:
            return None
        return UserFlags(self._raw_public_flags)

    @property
    def banner(self) -> Asset | None:
        """ The banner of the user, if any. """
        banner = self._extra.banner if self._extra else None
        if not banner:
            return None
        return Asset._from_banner(self._state, self.id, banner)

    @property
    def accent_colour(self) -> Colour | None:
        """ The accent colour of the user, if any. """
        accent_colour = self._extra.accent_colour if self._extra else None
        if not accent_colour:
            return None
        return Colour(accent_colour)

    @property
    def banner_colour(self) -> Colour | None:
        """ The banner colour of the user, if any. """
        banner_colour = self._extra.banner_colour if self._extra else None
        if not banner_colour:
            return None
        return Colour.from_hex(banner_colour)

    @property
    def avatar_decoration(self) -> AvatarDecoration | None:
        """ The avatar decoration of the member, if available. """
        avatar_decoration = self._extra.avatar_decoration if self._extra else None
        if not avatar_decoration:
            return None
        return AvatarDecoration(self._state, avatar_decoration)

    @property
    def nameplate(self) -> Nameplate | None:
        """ The nameplate of the member, if available. """
        nameplate = self._extra.nameplate if self._extra else None
        if not nameplate:
            return None
        return Nameplate(state=self._state, data=nameplate)

    @property
    def name_style(self) -> DisplayNameStyles | None:
        """ The display name style of the user, if any. """
        name_style = self._extra.name_style if self._extra else None
        if not name_style:
            return None
        return DisplayNameStyles(data=name_style)

    @property
    def primary_guild(self) -> PrimaryGuild | None:
        """ The primary guild of the user (aka. clan), if any. """
        primary_guild = self._extra.primary_guild if self._extra else None
        if not primary_guild:
            return None
        return PrimaryGuild(state=self._state, data=primary_guild)

    @property
    def global_avatar(self) -> Asset | None:
        """ Alias for `User.avatar`. """
        return self.avatar

    @property
    def global_banner(self) -> Asset | None:
        """ Alias for `User.banner`. """
        return self.banner

    @property
    def display_name(self) -> str:
        """ The user's display name. """
        return self.global_name or self.name

    @property
    def display_avatar(self) -> Asset:
        """ The display avatar of the member. """
        return self.avatar or self.default_avatar

    @property
    def display_banner(self) -> Asset | None:
        """ An alias to merge with `Member.display_banner`. """
        return self.banner

    @property
    def display_name_style(self) -> DisplayNameStyles | None:
        """ An alias to merge with `Member.display_name_style`. """
        return self.name_style

    @property
    def display_avatar_decoration(self) -> AvatarDecoration | None:
        """ An alias to merge with `Member.display_avatar_decoration`. """
        return self.avatar_decoration

    @property
    def global_avatar_decoration(self) -> AvatarDecoration | None:
        """ Alias for `User.avatar_decoration`. """
        return self.avatar_decoration

    def is_default_avatar(self) -> bool:
        """ Returns whether the user has a default avatar. """
        return self.avatar is None

    def _copy_from(self, other: "User") -> None:
        """ Refreshes this user's fields in place from another (freshly parsed) User instance. """
        for attr in User.__slots__:
            if attr == "__weakref__":
                continue
            setattr(self, attr, getattr(other, attr))


class TeamMember(PartialBase):
    """ Represents a member of a developer team. """

    __slots__ = (
        "_state",
        "membership_state",
        "role",
        "team_id",
        "user",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        team_id: int,
        data: dict
    ):
        super().__init__(id=int(data["user"]["id"]))
        self._state = state

        self.team_id: int = team_id
        """ The ID of the team this member belongs to. """

        self.membership_state: TeamMembershipState = TeamMembershipState(data["membership_state"])
        """ The membership state of the team member. """

        self.role: str = data.get("role", "")
        """ The role of the team member. """

        self.user: User = User(state=self._state, data=data["user"])
        """ The user associated with the team member. """

    def __repr__(self) -> str:
        return f"<TeamMember id={self.id} role='{self.role}'>"

    def __str__(self) -> str:
        return self.role


class Team(PartialBase):
    """ Represents a Discord developer team. """

    __slots__ = (
        "_state",
        "icon",
        "members",
        "name",
        "owner_user_id",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(id=int(data["id"]))
        self._state = state

        self.name: str = data["name"]
        """ The name of the team. """

        self.icon: Asset | None = None
        """ The icon of the team, if any. """

        self.owner_user_id: int = int(data["owner_user_id"])
        """ The ID of the user that owns the team. """

        self.members: list[TeamMember] = [
            TeamMember(state=self._state, team_id=self.id, data=g)
            for g in data.get("members", [])
        ]
        """ The members of the team. """

    def __repr__(self) -> str:
        return f"<Team id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def _from_data(self, data: dict) -> None:
        if icon := data.get("icon"):
            self.icon = Asset._from_icon(
                state=self._state,
                object_id=self.id,
                icon_hash=icon,
                path="team"
            )

    @property
    def owner(self) -> PartialUser:
        """ The user that owns the team. """
        return PartialUser(state=self._state, id=self.owner_user_id)


class ApplicationRoleConnectionMetadata:
    """ Represents a single application role connection metadata record. """

    __slots__ = (
        "description",
        "description_localizations",
        "key",
        "name",
        "name_localizations",
        "type",
    )

    def __init__(
        self,
        *,
        type: ApplicationRoleConnectionMetadataType | int,  # ruff: ignore[builtin-argument-shadowing]
        key: str,
        name: str,
        description: str,
        name_localizations: dict[str, str] | None = None,
        description_localizations: dict[str, str] | None = None,
    ):
        self.type: ApplicationRoleConnectionMetadataType = ApplicationRoleConnectionMetadataType(int(type))
        """ The type of comparison the metadata value is checked against. """

        self.key: str = key
        """ The dictionary key for the metadata field. """

        self.name: str = name
        """ The name of the metadata field. """

        self.description: str = description
        """ The description of the metadata field. """

        self.name_localizations: dict[str, str] = name_localizations or {}
        """ The localizations of the name of the metadata field. """

        self.description_localizations: dict[str, str] = description_localizations or {}
        """ The localizations of the description of the metadata field. """

    def __repr__(self) -> str:
        return f"<ApplicationRoleConnectionMetadata key='{self.key}'>"

    def __str__(self) -> str:
        return self.key

    @classmethod
    def from_dict(cls, data: dict) -> "ApplicationRoleConnectionMetadata":
        """ Creates an ApplicationRoleConnectionMetadata from a dict provided by Discord. """
        return cls(
            type=data["type"],
            key=data["key"],
            name=data["name"],
            description=data["description"],
            name_localizations=data.get("name_localizations"),
            description_localizations=data.get("description_localizations"),
        )

    def to_dict(self) -> dict:
        """ Returns a dict representation of the metadata record. """
        payload = {
            "type": int(self.type),
            "key": self.key,
            "name": self.name,
            "description": self.description,
        }

        if self.name_localizations:
            payload["name_localizations"] = self.name_localizations
        if self.description_localizations:
            payload["description_localizations"] = self.description_localizations

        return payload


class Application(PartialBase):
    """ Represents a user client object. """

    __slots__ = (
        "_state",
        "approximate_guild_count",
        "approximate_user_authorization_count",
        "approximate_user_install_count",
        "bot",
        "bot_public",
        "bot_require_code_grant",
        "cover_image",
        "custom_install_url",
        "description",
        "event_webhooks_status",
        "event_webhooks_types",
        "event_webhooks_url",
        "flags",
        "guild",
        "icon",
        "install_params",
        "integration_types_config",
        "interactions_endpoint_url",
        "name",
        "owner",
        "primary_sku",
        "privacy_policy_url",
        "redirect_uris",
        "role_connections_verification_url",
        "rpc_origins",
        "slug",
        "tags",
        "team",
        "terms_of_service_url",
        "verified",
        "verify_key",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(id=int(data["id"]))
        self._state = state

        self.name: str = data["name"]
        """ The name of the application. """

        self.icon: Asset | None = None
        """ The icon of the application, if any. """

        self.description: str | None = data.get("description")
        """ The description of the application, if any. """

        self.rpc_origins: list[str] = data.get("rpc_origins", [])
        """ The RPC origins of the application. """

        self.bot_public: bool = data.get("bot_public", False)
        """ Whether the bot is public. """

        self.bot_require_code_grant: bool = data.get("bot_require_code_grant", False)
        """ Whether the bot requires code grant. """

        self.bot: User | None = None
        """ The bot user of the application, if any. """

        self.terms_of_service_url: str | None = data.get("terms_of_service_url")
        """ The URL of the terms of service of the application, if any. """

        self.privacy_policy_url: str | None = data.get("privacy_policy_url")
        """ The URL of the privacy policy of the application, if any. """

        self.owner: PartialUser | None = None
        """ The owner of the application, if any. """

        self.verify_key: str = data.get("verify_key", "")
        """ The verify key of the application. """

        self.guild: "PartialGuild | None" = None
        """ The guild of the application, if the application is a game sold on Discord. """

        self.primary_sku: "PartialSKU | None" = None
        """ The primary SKU of the application, if the application is a game sold on Discord. """

        self.slug: str | None = data.get("slug")
        """ The slug of the application, if any. """

        self.cover_image: Asset | None = None
        """ The cover image of the application, if any. """

        self.flags: ApplicationFlags = ApplicationFlags(
            int(raw_flags_new)
            if (raw_flags_new := data.get("flags_new")) is not None
            else data.get("flags", 0)
        )
        """ The flags of the application. """

        self.approximate_guild_count: int | None = data.get("approximate_guild_count")
        """ The approximate number of guilds the application is in, if the application is a game sold on Discord. """

        self.approximate_user_install_count: int | None = data.get("approximate_user_install_count")
        """ The approximate number of users that have the application installed. """

        self.approximate_user_authorization_count: int | None = data.get("approximate_user_authorization_count")
        """ The approximate number of users that have authorized the application. """

        self.redirect_uris: list[str] = data.get("redirect_uris", [])
        """ The redirect URIs of the application, if any. """

        self.interactions_endpoint_url: str | None = data.get("interactions_endpoint_url")
        """ The interactions endpoint URL of the application, if any. """

        self.role_connections_verification_url: str | None = data.get("role_connections_verification_url")
        """ The role connections verification URL of the application, if any. """

        self.event_webhooks_url: str | None = data.get("event_webhooks_url")
        """ The event webhooks URL of the application, if any. """

        self.event_webhooks_status: ApplicationEventWebhookStatus = ApplicationEventWebhookStatus(
            data.get("event_webhooks_status", int(ApplicationEventWebhookStatus.disabled))
        )
        """ The event webhooks status of the application. """

        self.event_webhooks_types: list[str] = data.get("event_webhooks_types", [])
        """ The event webhooks types of the application. """

        self.tags: list[str] = data.get("tags", [])
        """ The tags of the application. """

        self.custom_install_url: str | None = data.get("custom_install_url")
        """ The custom install URL of the application, if any. """

        self.install_params: dict | None = data.get("install_params")
        """ The install params of the application, if any. """

        self.integration_types_config: dict = data.get("integration_types_config", {})
        """ The integration types config of the application. """

        self.team: Team | None = None
        """ The team that owns the application, if any. """

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Application id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name

    def _from_data(self, data: dict) -> None:
        if owner := data.get("owner"):
            self.owner = PartialUser(
                state=self._state,
                id=int(owner["id"])
            )

        if bot := data.get("bot"):
            self.bot = User(
                state=self._state,
                data=bot
            )

        if (guild_id := data.get("guild_id")) or (guild := data.get("guild")):
            from .guild import PartialGuild
            self.guild = PartialGuild(
                state=self._state,
                id=int(guild_id) if guild_id else int(guild["id"])
            )

        if icon := data.get("icon"):
            self.icon = Asset._from_application_image(
                self._state,
                self.id,
                icon
            )

        if cover_image := data.get("cover_image"):
            self.cover_image = Asset._from_application_image(
                self._state,
                self.id,
                cover_image
            )

        if primary_sku_id := data.get("primary_sku_id"):
            from .entitlements import PartialSKU
            self.primary_sku = PartialSKU(
                state=self._state,
                id=int(primary_sku_id)
            )

        if team := data.get("team"):
            self.team = Team(
                state=self._state,
                data=team
            )

    async def edit(
        self,
        *,
        custom_install_url: str | None = MISSING,
        description: str | None = MISSING,
        role_connections_verification_url: str | None = MISSING,
        install_params: dict | None = MISSING,
        integration_types_config: dict | None = MISSING,
        flags: ApplicationFlags | int | None = MISSING,
        icon: File | bytes | None = MISSING,
        cover_image: File | bytes | None = MISSING,
        interactions_endpoint_url: str | None = MISSING,
        tags: list[str] | None = MISSING,
        event_webhooks_url: str | None = MISSING,
        event_webhooks_status: ApplicationEventWebhookStatus | int | None = MISSING,
        event_webhooks_types: list[str] | None = MISSING,
    ) -> "Application":
        """
        Edit the current application.

        Only limited intent flags can be updated through `flags`.

        Parameters
        ----------
        custom_install_url
            New custom install URL of the application
        description
            New description of the application
        role_connections_verification_url
            New role connections verification URL of the application
        install_params
            New install params of the application
        integration_types_config
            New integration types config of the application
        flags
            New flags of the application
        icon
            New icon of the application
        cover_image
            New cover image of the application
        interactions_endpoint_url
            New interactions endpoint URL of the application
        tags
            New tags of the application
        event_webhooks_url
            New event webhooks URL of the application
        event_webhooks_status
            New event webhooks status of the application
        event_webhooks_types
            New event webhooks types of the application

        Returns
        -------
            The edited application
        """
        payload: dict = {}

        if custom_install_url is not MISSING:
            payload["custom_install_url"] = custom_install_url

        if description is not MISSING:
            payload["description"] = description

        if role_connections_verification_url is not MISSING:
            payload["role_connections_verification_url"] = role_connections_verification_url

        if install_params is not MISSING:
            payload["install_params"] = install_params

        if integration_types_config is not MISSING:
            payload["integration_types_config"] = integration_types_config

        if flags is not MISSING:
            payload["flags"] = int(flags) if flags else 0

        if icon is not MISSING:
            payload["icon"] = (
                utils.bytes_to_base64(icon)
                if icon is not None else None
            )

        if cover_image is not MISSING:
            payload["cover_image"] = (
                utils.bytes_to_base64(cover_image)
                if cover_image is not None else None
            )

        if interactions_endpoint_url is not MISSING:
            payload["interactions_endpoint_url"] = interactions_endpoint_url

        if tags is not MISSING:
            payload["tags"] = tags or []

        if event_webhooks_url is not MISSING:
            payload["event_webhooks_url"] = event_webhooks_url

        if event_webhooks_status is not MISSING:
            resolved_status = ApplicationEventWebhookStatus(
                int(event_webhooks_status or ApplicationEventWebhookStatus.disabled)
            )

            if resolved_status is ApplicationEventWebhookStatus.disabled_by_discord:
                raise ValueError(
                    "event_webhooks_status cannot be set to disabled_by_discord, "
                    "that state can only be set by Discord itself"
                )

            payload["event_webhooks_status"] = int(resolved_status)

        if event_webhooks_types is not MISSING:
            payload["event_webhooks_types"] = event_webhooks_types or []

        r = await self._state.query(
            "PATCH",
            "/applications/@me",
            json=payload
        )

        app = Application(state=self._state, data=r.response)

        if (
            self._state.bot.application and
            self._state.bot.application.id == self.id
        ):
            self._state.bot.application = app

        return app

    async def fetch_role_connection_metadata(self) -> list[ApplicationRoleConnectionMetadata]:
        """ Fetches the role connection metadata records for the application. """
        r = await self._state.query(
            "GET",
            f"/applications/{self.id}/role-connections/metadata"
        )

        return [
            ApplicationRoleConnectionMetadata.from_dict(g)
            for g in r.response
        ]

    async def edit_role_connection_metadata(
        self,
        records: list[ApplicationRoleConnectionMetadata]
    ) -> list[ApplicationRoleConnectionMetadata]:
        """
        Updates the role connection metadata records for the application.

        Parameters
        ----------
        records
            The new metadata records for the application (max 5)

        Returns
        -------
            The updated metadata records
        """
        r = await self._state.query(
            "PUT",
            f"/applications/{self.id}/role-connections/metadata",
            json=[g.to_dict() for g in records]
        )

        return [
            ApplicationRoleConnectionMetadata.from_dict(g)
            for g in r.response
        ]
