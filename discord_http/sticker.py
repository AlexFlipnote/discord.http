from typing import TYPE_CHECKING

from . import utils
from .enums import StickerType, StickerFormatType
from .object import PartialBase

if TYPE_CHECKING:
    from .guild import Guild, PartialGuild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "PartialSticker",
    "Sticker",
)


class PartialSticker(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        name: str | None = None,
        guild_id: int | None = None
    ):
        super().__init__(id=int(id))
        self._state = state

        self.name: str | None = name
        self.guild_id: int | None = guild_id

    def __repr__(self) -> str:
        return f"<PartialSticker id={self.id}>"

    async def fetch(self) -> "Sticker":
        """ Returns the sticker data. """
        r = await self._state.query(
            "GET",
            f"/stickers/{self.id}"
        )

        self.guild_id = utils.get_int(r.response, "guild_id")

        return Sticker(
            state=self._state,
            data=r.response,
            guild=self.guild,
        )

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """
        Returns the guild this sticker is in.

        Returns
        -------
            The guild this sticker is in

        Raises
        ------
        `ValueError`
            guild_id is not defined, unable to create PartialGuild
        """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    async def edit(
        self,
        *,
        name: str | None = MISSING,
        description: str | None = MISSING,
        tags: str | None = MISSING,
        guild_id: int | None = None,
        reason: str | None = None
    ) -> "Sticker":
        """
        Edits the sticker.

        Parameters
        ----------
        guild_id:
            Guild ID to edit the sticker from
        name:
            Replacement name for the sticker
        description:
            Replacement description for the sticker
        tags:
            Replacement tags for the sticker
        reason:
            The reason for editing the sticker

        Returns
        -------
            The edited sticker

        Raises
        ------
        `ValueError`
            No guild_id was passed
        """
        guild_id = guild_id or self.guild_id
        if guild_id is None:
            raise ValueError("guild_id is a required argument")

        payload = {}

        if name is not MISSING:
            payload["name"] = name
        if description is not MISSING:
            payload["description"] = description
        if tags is not MISSING:
            payload["tags"] = utils.unicode_name(str(tags))

        r = await self._state.query(
            "PATCH",
            f"/guilds/{guild_id}/stickers/{self.id}",
            json=payload,
            reason=reason
        )

        self.guild_id = int(r.response["guild_id"])

        return Sticker(
            state=self._state,
            data=r.response,
            guild=self.guild,
        )

    async def delete(
        self,
        *,
        guild_id: int | None = None,
        reason: str | None = None
    ) -> None:
        """
        Deletes the sticker.

        Parameters
        ----------
        guild_id:
            Guild ID to delete the sticker from
        reason:
            The reason for deleting the sticker

        Raises
        ------
        `ValueError`
            No guild_id was passed or guild_id is not defined
        """
        guild_id = guild_id or self.guild_id
        if guild_id is None:
            raise ValueError(
                "guild_id is a required argument "
                "since it was not provided by object"
            )

        await self._state.query(
            "DELETE",
            f"/guilds/{guild_id}/stickers/{self.id}",
            res_method="text",
            reason=reason
        )

    @property
    def url(self) -> str:
        """ Returns the sticker's URL. """
        return f"https://media.discordapp.net/stickers/{self.id}.png"


class Sticker(PartialSticker):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | None",
    ):
        super().__init__(
            state=state,
            id=int(data["id"]),
            name=data["name"],
            guild_id=guild.id if guild else None
        )

        self.available: bool = data.get("available", False)
        self.available: bool = data["available"]
        self.description: str = data["description"]
        self.format_type: StickerFormatType = StickerFormatType(data["format_type"])
        self.pack_id: int | None = utils.get_int(data, "pack_id")
        self.sort_value: int | None = utils.get_int(data, "sort_value")
        self.tags: str = data["tags"]
        self.type: StickerType = StickerType(data["type"])

        # Re-define types
        self.name: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Sticker id={self.id} name='{self.name}'>"

    @property
    def url(self) -> str:
        """ Returns the sticker's URL. """
        img_format = "png"
        if self.format_type == StickerFormatType.gif:
            img_format = "gif"

        return f"https://media.discordapp.net/stickers/{self.id}.{img_format}"

    async def edit(
        self,
        *,
        name: str | None = MISSING,
        description: str | None = MISSING,
        tags: str | None = MISSING,
        reason: str | None = None
    ) -> "Sticker":
        """
        Edits the sticker.

        Parameters
        ----------
        name:
            Name of the sticker
        description:
            Description of the sticker
        tags:
            Tags of the sticker
        reason:
            The reason for editing the sticker

        Returns
        -------
        `Sticker`
            The edited sticker
        """
        if not self.guild:
            raise ValueError("Sticker is not in a guild")

        return await super().edit(
            guild_id=self.guild.id,
            name=name,
            description=description,
            tags=tags,
            reason=reason
        )

    async def delete(
        self,
        *,
        reason: str | None = None
    ) -> None:
        """
        Deletes the sticker.

        Parameters
        ----------
        reason:
            The reason for deleting the sticker

        Raises
        ------
        `ValueError`
            Guild is not defined
        """
        if not self.guild:
            raise ValueError("Sticker is not in a guild")

        await super().delete(guild_id=self.guild.id, reason=reason)
