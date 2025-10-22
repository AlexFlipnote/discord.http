import os

from typing import Self, TYPE_CHECKING, Literal

from . import utils
from .errors import HTTPException

if TYPE_CHECKING:
    from .http import DiscordAPI

StaticFormatTypes = Literal["webp", "jpeg", "jpg", "png"]
AssetFormatTypes = Literal["webp", "jpeg", "jpg", "png", "gif"]

MISSING = utils.MISSING

__all__ = (
    "Asset",
)


class Asset:
    """
    Represents a Discord asset (e.g. an image or video).

    Attributes
    ----------
    url: str
        The URL of the asset
    key: str
        The key of the asset
    animated: bool
        Whether the asset is animated
    """
    BASE = "https://cdn.discordapp.com"
    PROXY = "https://media.discordapp.net"

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        url: str,
        key: str,
        animated: bool = False
    ):
        self._state = state

        self.url: str = url
        self.key: str = key
        self.animated: bool = animated

    def __str__(self) -> str:
        return self.url

    def __repr__(self) -> str:
        shorten = self.url.replace(self.BASE, "")
        return f"<Asset url={shorten}>"

    async def fetch(self, *, fallback: bool = False) -> bytes:
        """
        Fetches the asset.

        Parameters
        ----------
        fallback: bool
            Whether to fallback to a missing texture if the asset returns anything but `HTTP 2XX`.
            Defaults to `False`.

        Returns
        -------
            The asset data
        """
        r = await self._state.http.request(
            "GET", self.url, res_method="read"
        )

        if r.status not in range(200, 300):
            if fallback:
                # Return "Missing Texture" meme if the asset is not found and fallback is enabled
                return utils.create_missing_texture()
            raise HTTPException(r)

        return r.response

    async def save(self, path: str) -> int:
        """
        Fetches the file from the attachment URL and saves it locally to the path.

        Parameters
        ----------
        path: `str`
            Path to save the file to, which includes the filename and extension.
            Example: `./path/to/file.png`

        Returns
        -------
            The amount of bytes written to the file
        """
        data = await self.fetch()
        with open(path, "wb") as f:
            return f.write(data)

    def replace(
        self,
        *,
        size: int = MISSING,
        format: AssetFormatTypes = MISSING  # noqa: A002
    ) -> Self:
        """
        Replace the asset with new values.

        Parameters
        ----------
        size: `int`
            The size of the asset
        format: `AssetFormatTypes`
            The format of the asset

        Returns
        -------
            The new asset object
        """
        url = utils.URL(self.url)
        path, _ = os.path.splitext(url.path)
        prev_size = url.query.get("size")

        if format is not MISSING:
            url = url.with_path(f"{path}.{format}")

            # If we have a size, we need to keep it.
            # URL.with_path removes it from the query.
            if prev_size is not None:
                url = url.with_query(size=prev_size)

        if size is not MISSING:
            url = url.with_query(size=size)

        url = str(url)
        return self.__class__(
            state=self._state,
            url=url,
            key=self.key,
            animated=self.animated
        )

    def with_static_format(
        self,
        format: StaticFormatTypes  # noqa: A002
    ) -> Self:
        """
        Replace the asset with a static format.

        Parameters
        ----------
        format: `StaticFormatTypes`
            The static format to use

        Returns
        -------
            The new asset object, if animated, it will return no changes
        """
        if self.animated:
            return self
        return self.replace(format=format)

    @classmethod
    def _from_avatar(
        cls,
        state: "DiscordAPI",
        user_id: int,
        avatar: str
    ) -> Self:
        animated = avatar.startswith("a_")
        format_ = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/avatars/{user_id}/{avatar}.{format_}?size=1024",
            key=avatar,
            animated=animated
        )

    @classmethod
    def _from_default_avatar(
        cls,
        state: "DiscordAPI",
        num: int
    ) -> Self:
        return cls(
            state=state,
            url=f"{cls.BASE}/embed/avatars/{num}.png",
            key=str(num)
        )

    @classmethod
    def _from_collectibles(
        cls,
        state: "DiscordAPI",
        image: str
    ) -> Self:
        return cls(
            state=state,
            url=f"{cls.BASE}/assets/collectibles/{image}img.png",
            key=image
        )

    @classmethod
    def _from_guild_avatar(
        cls,
        state: "DiscordAPI",
        guild_id: int,
        member_id: int,
        avatar: str
    ) -> Self:
        animated = avatar.startswith("a_")
        format_ = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/guilds/{guild_id}/users/{member_id}/avatars/{avatar}.{format_}?size=1024",
            key=avatar,
            animated=animated
        )

    @classmethod
    def _from_guild_clan_badge(
        cls,
        state: "DiscordAPI",
        guild_id: int,
        badge: str
    ) -> Self:
        animated = badge.startswith("a_")
        format_ = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/clan-badges/{guild_id}/{badge}.{format_}?size=1024",
            key=badge,
            animated=animated
        )

    @classmethod
    def _from_guild_banner(
        cls,
        state: "DiscordAPI",
        guild_id: int,
        member_id: int,
        banner: str
    ) -> Self:
        animated = banner.startswith("a_")
        format_ = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/guilds/{guild_id}/users/{member_id}/banners/{banner}.{format_}?size=1024",
            key=banner,
            animated=animated
        )

    @classmethod
    def _from_guild_image(
        cls,
        state: "DiscordAPI",
        guild_id: int,
        image: str,
        path: str
    ) -> Self:
        animated = image.startswith("a_")
        format_ = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/{path}/{guild_id}/{image}.{format_}?size=1024",
            key=image,
            animated=animated,
        )

    @classmethod
    def _from_scheduled_event_cover_image(
        cls,
        state: "DiscordAPI",
        scheduled_event_id: int,
        cover_image: str
    ) -> Self:
        return cls(
            state=state,
            url=f"{cls.BASE}/guild-events/{scheduled_event_id}/{cover_image}.png?size=1024",
            key=cover_image,
            animated=False,
        )

    @classmethod
    def _from_icon(
        cls,
        state: "DiscordAPI",
        object_id: int,
        icon_hash: str,
        path: str
    ) -> Self:
        return cls(
            state=state,
            url=f"{cls.BASE}/{path}-icons/{object_id}/{icon_hash}.png?size=1024",
            key=icon_hash,
            animated=False,
        )

    @classmethod
    def _from_avatar_decoration(
        cls,
        state: "DiscordAPI",
        decoration: str
    ) -> Self:
        animated = decoration.startswith(("v2_a_", "a_"))

        return cls(
            state=state,
            url=f"{cls.BASE}/avatar-decoration-presets/{decoration}.png?size=96&passthrough=true",
            key=decoration,
            animated=animated
        )

    @classmethod
    def _from_banner(
        cls,
        state: "DiscordAPI",
        user_id: int,
        banner: str
    ) -> Self:
        animated = banner.startswith("a_")
        format_ = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/banners/{user_id}/{banner}.{format_}?size=1024",
            key=banner,
            animated=animated
        )

    @classmethod
    def _from_activity_asset(
        cls,
        state: "DiscordAPI",
        activity_id: int,
        image: str
    ) -> Self:
        url = f"{cls.BASE}/app-assets/{activity_id}/{image}.png"
        if image.startswith("mp:"):
            url = f"{cls.PROXY}/{image}"

        return cls(
            state=state,
            url=url,
            key=image
        )
