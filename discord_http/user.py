import sys

from typing import TYPE_CHECKING, Any

from . import utils
from .asset import Asset
from .colour import Colour
from .embeds import Embed
from .enums import (
    DefaultAvatarType, DisplayNameEffectType, DisplayNameFontType,
    ApplicationEventWebhookStatus
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
    "AvatarDecoration",
    "DisplayNameStyles",
    "Nameplate",
    "PartialUser",
    "PrimaryGuild",
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
        colours:
            The colors of the display name, if any.
        font:
            The font of the display name, if any.
        effect:
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
        if self.guild_id and data.get("badge"):
            self.badge = Asset._from_guild_clan_badge(
                self._state, self.guild_id, data["badge"]
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
        id: int  # noqa: A002
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialUser id={self.id}>"

    @property
    def mention(self) -> str:
        """ Returns a string that allows you to mention the user. """
        return f"<@!{self.id}>"

    @property
    def default_avatar(self) -> Asset:
        """ Returns the default avatar of the user. """
        return Asset._from_default_avatar(
            self._state,
            (self.id >> 22) % len(DefaultAvatarType)
        )

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
        type: ResponseType | int = 4,  # noqa: A002
        flags: MessageFlags | None = MISSING,
        allowed_mentions: AllowedMentions | None = MISSING,
        delete_after: float | None = None
    ) -> "Message":
        """
        Send a message to the user.

        Parameters
        ----------
        content:
            Content of the message
        channel_id:
            Channel ID to send the message to, if not provided, it will create a DM channel
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        file:
            File of the message
        files:
            Files of the message
        view:
            Components of the message
        tts:
            Whether the message should be sent as TTS
        type:
            Which type of response should be sent
        flags:
            Flags of the message
        allowed_mentions:
            Allowed mentions of the message
        delete_after:
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
        username:
            The username to change the user to
        avatar:
            New avatar for the user
        banner:
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


class User(PartialUser):
    """ Represents a user object. """

    __slots__ = (
        "accent_colour",
        "avatar",
        "avatar_decoration",
        "banner",
        "banner_colour",
        "bot",
        "discriminator",
        "global_name",
        "name",
        "name_style",
        "nameplate",
        "primary_guild",
        "public_flags",
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

        self.avatar: Asset | None = None
        """ The avatar of the user, if any. """

        self.banner: Asset | None = None
        """ The banner of the user, if any. """

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

        self.accent_colour: Colour | None = None
        """ The accent colour of the user, if any. """

        self.banner_colour: Colour | None = None
        """ The banner colour of the user, if any. """

        self.global_name: str | None = sys.intern(g) if (g := data.get("global_name")) else None
        """ The global name of the user, if any. """

        self.public_flags: UserFlags | None = None
        """ The public flags of the user, if any. """

        self.primary_guild: PrimaryGuild | None = None
        """ The primary guild of the user (aka. clan), if any. """

        self.avatar_decoration: AvatarDecoration | None = None
        """ The avatar decoration of the member, if available. """

        self.nameplate: Nameplate | None = None
        """ The nameplate of the member, if available. """

        self.name_style: DisplayNameStyles | None = None
        """ The display name style of the user, if any. """

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

        if data.get("avatar"):
            self.avatar = Asset._from_avatar(
                self._state, self.id, data["avatar"]
            )

        if data.get("primary_guild"):
            self.primary_guild = PrimaryGuild(
                state=self._state,
                data=data["primary_guild"]
            )

        if data.get("display_name_styles"):
            self.name_style = DisplayNameStyles(
                data=data["display_name_styles"]
            )

        if data.get("banner"):
            self.banner = Asset._from_banner(
                self._state, self.id, data["banner"]
            )

        if data.get("accent_color"):
            self.accent_colour = Colour(data["accent_color"])

        if data.get("banner_color"):
            self.banner_colour = Colour.from_hex(data["banner_color"])

        if data.get("avatar_decoration_data"):
            self.avatar_decoration = AvatarDecoration(
                self._state, data["avatar_decoration_data"]
            )

        if collectibles.get("nameplate"):
            self.nameplate = Nameplate(
                state=self._state,
                data=collectibles["nameplate"]
            )

        if data.get("public_flags"):
            self.public_flags = UserFlags(data["public_flags"])

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
        """ Returns the user's display name. """
        return self.global_name or self.name

    @property
    def display_avatar(self) -> Asset:
        """ Returns the display avatar of the member. """
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
        "description",
        "event_webhooks_status",
        "event_webhooks_types",
        "event_webhooks_url",
        "flags",
        "guild",
        "icon",
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

        self.flags: ApplicationFlags = ApplicationFlags(data.get("flags", 0))
        """ The flags of the application. """

        self.approximate_guild_count: int | None = data.get("approximate_guild_count")
        """ The approximate number of guilds the application is in, if the application is a game sold on Discord. """

        self.approximate_user_install_count: int | None = data.get("approximate_user_install_count")
        """ The approximate number of users that have the application installed, if the application is a game sold on Discord. """

        self.approximate_user_authorization_count: int | None = data.get("approximate_user_authorization_count")
        """ The approximate number of users that have authorized the application, if the application is a game sold on Discord. """

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

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Application id={self.id} name='{self.name}'>"

    def _from_data(self, data: dict) -> None:
        if data.get("owner"):
            self.owner = PartialUser(
                state=self._state,
                id=int(data["owner"]["id"])
            )

        if data.get("bot"):
            self.bot = User(
                state=self._state,
                data=data["bot"]
            )

        if data.get("guild_id"):
            from .guild import PartialGuild
            self.guild = PartialGuild(
                state=self._state,
                id=int(data["guild_id"])
            )

        if data.get("icon"):
            self.icon = Asset._from_application_image(
                self._state,
                self.id,
                data["icon"]
            )

        if data.get("cover_image"):
            self.cover_image = Asset._from_application_image(
                self._state,
                self.id,
                data["cover_image"]
            )

        if data.get("primary_sku_id"):
            from .entitlements import PartialSKU
            self.primary_sku = PartialSKU(
                state=self._state,
                id=int(data["primary_sku_id"])
            )
