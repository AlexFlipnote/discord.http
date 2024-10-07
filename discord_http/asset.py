from typing import Self, TYPE_CHECKING

from .errors import HTTPException

if TYPE_CHECKING:
    from .http import DiscordAPI

__all__ = (
    "Asset",
)


class Asset:
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
        self._url: str = url
        self._animated: bool = animated
        self._key: str = key

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        shorten = self._url.replace(self.BASE, "")
        return f"<Asset url={shorten}>"

    async def fetch(self) -> bytes:
        """
        Fetches the asset

        Returns
        -------
        `bytes`
            The asset data
        """
        r = await self._state.http.request(
            "GET", self.url, res_method="read"
        )

        if r.status not in range(200, 300):
            raise HTTPException(r)

        return r.response

    async def save(self, path: str) -> int:
        """
        Fetches the file from the attachment URL and saves it locally to the path

        Parameters
        ----------
        path: `str`
            Path to save the file to, which includes the filename and extension.
            Example: `./path/to/file.png`

        Returns
        -------
        `int`
            The amount of bytes written to the file
        """
        data = await self.fetch()
        with open(path, "wb") as f:
            return f.write(data)

    @property
    def url(self) -> str:
        """
        The URL of the asset

        Returns
        -------
        `str`
            The URL of the asset
        """
        return self._url

    @property
    def key(self) -> str:
        """
        The key of the asset

        Returns
        -------
        `str`
            The key of the asset
        """
        return self._key

    def is_animated(self) -> bool:
        """
        Whether the asset is animated or not

        Returns
        -------
        `bool`
            Whether the asset is animated or not
        """
        return self._animated

    @classmethod
    def _from_avatar(
        cls,
        state: "DiscordAPI",
        user_id: int,
        avatar: str
    ) -> Self:
        animated = avatar.startswith("a_")
        format = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/avatars/{user_id}/{avatar}.{format}?size=1024",
            key=avatar,
            animated=animated
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
        format = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/guilds/{guild_id}/users/{member_id}/avatars/{avatar}.{format}?size=1024",
            key=avatar,
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
        format = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/{path}/{guild_id}/{image}.{format}?size=1024",
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
        animated = (
            decoration.startswith("v2_a_") or
            decoration.startswith("a_")
        )

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
        format = "gif" if animated else "png"
        return cls(
            state=state,
            url=f"{cls.BASE}/banners/{user_id}/{banner}.{format}?size=1024",
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
