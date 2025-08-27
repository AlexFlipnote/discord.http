from typing import TYPE_CHECKING, Any

from . import utils
from .asset import Asset
from .colour import Colour
from .embeds import Embed
from .enums import DefaultAvatarType, DisplayNameEffectType, DisplayNameFontType
from .file import File
from .flags import UserFlags, MessageFlags
from .mentions import AllowedMentions
from .object import PartialBase, Snowflake
from .response import ResponseType, MessageResponse
from .view import View

if TYPE_CHECKING:
    from .channel import DMChannel
    from .http import DiscordAPI
    from .guild import Guild, PartialGuild
    from .message import Message

MISSING = utils.MISSING

__all__ = (
    "AvatarDecoration",
    "DisplayNameStyle",
    "Nameplate",
    "PartialUser",
    "PrimaryGuild",
    "User",
    "UserClient",
)


class DisplayNameStyle:
    """
    Represents the display name style of a user.

    Attributes
    ----------
    colours: list[Colour] | None
        The colors of the display name, if any
    font: DisplayNameFontType | None
        The font of the display name, if any
    effect: DisplayNameEffectType | None
        The effect of the display name, if any
    """
    def __init__(self, data: dict):
        self.colours: list[Colour] = [Colour(g) for g in data.get("colors", [])]
        self.font: DisplayNameFontType = DisplayNameFontType(data.get("font", 11))
        self.effect: DisplayNameEffectType = DisplayNameEffectType(data.get("effect", 0))

    def __repr__(self) -> str:
        return (
            f"<DisplayNameStyle colours={self.colours} font={self.font} "
            f"effect={self.effect}>"
        )


class Nameplate:
    """
    Represents a nameplate collectible of a user.

    Attributes
    ----------
    sku_id: int
        The ID of the SKU associated with the nameplate
    label: str
        The label of the nameplate
    palette: str
        The palette of the nameplate
    asset: Asset
        The asset of the nameplate
    """
    def __init__(self, state: "DiscordAPI", data: dict):
        self._state = state

        self.sku_id: int = int(data["sku_id"])
        self.label: str = data["label"]
        self.palette: str = data["palette"]
        self.asset: Asset = Asset._from_collectibles(state, data["asset"])

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

    Attributes
    ----------
    guild_id: int
        The ID of the guild
    tag: str | None
        The tag of the guild, if any
    badge: Asset | None
        The badge of the guild, if any
    """
    def __init__(self, state: "DiscordAPI", data: dict):
        self._state = state

        self.guild_id: int | None = utils.get_int(data, "identity_guild_id")
        self.tag: str | None = data.get("tag")
        self.badge: Asset | None = None

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
    """
    Represents an avatar decoration of a user.

    Attributes
    ----------
    sku_id: int
        The ID of the SKU associated with the avatar decoration
    asset: Asset
        The asset of the avatar decoration
    """
    def __init__(self, state: "DiscordAPI", data: dict):
        super().__init__(id=int(data["sku_id"]))
        self._state = state

        self.sku_id: int = int(data["sku_id"])
        self.asset = Asset._from_avatar_decoration(
            self._state, data["asset"]
        )

    def __repr__(self) -> str:
        return f"<AvatarDecoration sku_id={self.sku_id} asset='{self.asset}'>"

    def __str__(self) -> str:
        return self.asset.url

    @property
    def shop_url(self) -> str:
        """ The URL of the avatar decoration asset. """
        return f"https://discord.com/shop#itemSkuId={self.sku_id}"


class PartialUser(PartialBase):
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

    @property
    def default_avatar(self) -> Asset:
        """ Returns the default avatar of the user. """
        return Asset._from_default_avatar(
            self._state,
            (self.id >> 22) % len(DefaultAvatarType)
        )


class User(PartialUser):
    """
    Represents a user object.

    Attributes
    ----------
    avatar: Asset | None
        The avatar of the user, if any
    banner: Asset | None
        The banner of the user, if any
    name: str
        The name of the user
    bot: bool
        Whether the user is a bot
    system: bool
        Whether the user is a system user
    discriminator: str | None
        The discriminator of the user, if any
    global_name: str | None
        The global name of the user, if any
    accent_colour: Colour | None
        The accent colour of the user, if any
    banner_colour: Colour | None
        The banner colour of the user, if any
    public_flags: UserFlags | None
        The public flags of the user, if any
    avatar_decoration: AvatarDecoration | None
        The avatar decoration of the member, if available.
    nameplate: Nameplate | None
        The nameplate of the member, if available.
    primary_guild: PrimaryGuild | None
        The primary guild of the user (aka. clan), if any
    display_name_style: DisplayNameStyle | None
        The display name style of the user, if any
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.avatar: Asset | None = None
        self.banner: Asset | None = None

        self.name: str = data["username"]
        self.bot: bool = data.get("bot", False)
        self.system: bool = data.get("system", False)

        # This section is ONLY here because bots still have a discriminator
        self.discriminator: str | None = data.get("discriminator")
        if self.discriminator == "0":
            # Instead of showing "0", just make it None....
            self.discriminator = None

        self.accent_colour: Colour | None = None
        self.banner_colour: Colour | None = None

        self.global_name: str | None = data.get("global_name")

        self.public_flags: UserFlags | None = None
        self.primary_guild: PrimaryGuild | None = None
        self.avatar_decoration: AvatarDecoration | None = None
        self.nameplate: Nameplate | None = None
        self.display_name_style: DisplayNameStyle | None = None

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
            self.display_name_style = DisplayNameStyle(
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
    def display_avatar_decoration(self) -> AvatarDecoration | None:
        """ An alias to merge with `Member.display_avatar_decoration`. """
        return self.avatar_decoration

    @property
    def global_avatar_decoration(self) -> AvatarDecoration | None:
        """ Alias for `User.avatar_decoration`. """
        return self.avatar_decoration


class UserClient(User):
    """
    Represents a user client object.

    Attributes
    ----------
    verified: bool
        Whether the user is verified
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, data=data)

        self.verified: bool = data.get("verified", False)

    def __repr__(self) -> str:
        return f"<UserClient id={self.id} name='{self.name}'>"

    async def edit(
        self,
        *,
        username: str | None = MISSING,
        avatar: bytes | None = MISSING,
        banner: bytes | None = MISSING,
    ) -> "UserClient":
        """
        Edit the user.

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

        return UserClient(
            state=self._state,
            data=r.response
        )
