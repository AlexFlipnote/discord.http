import re

from typing import TYPE_CHECKING, Self

from . import utils
from .asset import Asset
from .object import PartialBase, Snowflake
from .role import PartialRole

if TYPE_CHECKING:
    from .guild import Guild, PartialGuild
    from .http import DiscordAPI
    from .user import User

MISSING = utils.MISSING

__all__ = (
    "Emoji",
    "EmojiParser",
    "PartialEmoji",
)


class EmojiParser:
    """
    Used to accept any input and convert to either a normal emoji or a Discord emoji automatically.

    It is used for things like reactions, forum, components, etc

    Attributes
    ----------
    raw: str
        The raw emoji string that was passed to the constructor.
    id: int | None
        The ID of the emoji if it's a Discord emoji, otherwise None.
    animated: bool
        Whether the emoji is animated or not.
    discord_emoji: bool
        Whether the emoji is a Discord emoji or not.
    name: str
        The name of the emoji. If it's a Discord emoji, it will be the name of the emoji.

    Examples
    --------
    - `EmojiParser("👍")`
    - `EmojiParser("<:name:1234567890>")`
    - `EmojiParser("1234567890")`
    """
    def __init__(self, emoji: str):
        self.raw: str = emoji

        self.id: int | None = None
        self.animated: bool = False
        self.discord_emoji: bool = False

        is_custom: re.Match | None = utils.re_emoji.search(emoji)

        if is_custom:
            animated, name, id_ = is_custom.groups()
            self.discord_emoji = True
            self.animated = bool(animated)
            self.name: str = name
            self.id = int(id_)

        elif emoji.isdigit():
            self.discord_emoji = True
            self.id = int(emoji)
            self.name: str = emoji

        else:
            self.name: str = emoji

    def __repr__(self) -> str:
        if self.discord_emoji:
            return f"<EmojiParser name='{self.name}' id={self.id}>"
        return f"<EmojiParser name='{self.name}'>"

    def __str__(self) -> str:
        return self.raw

    def __int__(self) -> int | None:
        if self.discord_emoji:
            return self.id
        return None

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Create an emoji from a dictionary.

        Parameters
        ----------
        data:
            The dictionary to create the emoji from

        Returns
        -------
            The emoji
        """
        if data.get("id") is None:
            return cls(data["name"])

        return cls(
            f"<{'a' if data.get('animated') else ''}:"
            f"{data['name']}:{data['id']}>"
        )

    @property
    def url(self) -> str | None:
        """ Returns the URL of the emoji if it's a Discord emoji. """
        if self.discord_emoji:
            return f"{Asset.BASE}/emojis/{self.id}.{'gif' if self.animated else 'png'}"
        return None

    def to_dict(self) -> dict:
        """ Returns a dict representation of the emoji. """
        if self.discord_emoji:
            # Include animated if it's a Discord emoji
            return {"id": self.id, "name": self.name, "animated": self.animated}
        return {"name": self.name, "id": None}

    def to_forum_dict(self) -> dict:
        """ Returns a dict representation of emoji to forum/media channel. """
        payload = {
            "emoji_name": self.name,
            "emoji_id": None
        }

        if self.discord_emoji:
            return {"emoji_name": None, "emoji_id": str(self.id)}

        return payload

    def to_reaction(self) -> str:
        """ Returns a string representation of the emoji. """
        if self.discord_emoji:
            return f"{self.name}:{self.id}"
        return self.name


class PartialEmoji(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        guild_id: int | None = None
    ):
        super().__init__(id=int(id))
        self._state = state

        self.guild_id: int | None = guild_id

    def __repr__(self) -> str:
        return f"<PartialEmoji id={self.id}>"

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ The guild of the member. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def url(self) -> str:
        """
        `str`: Returns the URL of the emoji.

        It will always be PNG as it's a partial emoji.
        """
        return f"{Asset.BASE}/emojis/{self.id}.png"

    async def fetch(self) -> "Emoji":
        """
        `Emoji`: Fetches the emoji.

        If `guild_id` is not defined, it will fetch the emoji from the application.
        """
        if self.guild_id:
            r = await self._state.query(
                "GET",
                f"/guilds/{self.guild_id}/emojis/{self.id}"
            )

            return Emoji(
                state=self._state,
                guild=self.guild,
                data=r.response
            )

        r = await self._state.query(
            "GET",
            f"/applications/{self._state.application_id}/emojis/{self.id}"
        )

        return Emoji(
            state=self._state,
            data=r.response
        )

    async def delete(
        self,
        *,
        reason: str | None = None
    ) -> None:
        """
        Deletes the emoji.

        If `guild_id` is not defined, it will delete the emoji from the application.

        Parameters
        ----------
        reason:
            The reason for deleting the emoji.
        """
        if self.guild_id:
            await self._state.query(
                "DELETE",
                f"/guilds/{self.guild.id}/emojis/{self.id}",
                res_method="text",
                reason=reason
            )

        else:
            await self._state.query(
                "DELETE",
                f"/applications/{self._state.application_id}/emojis/{self.id}",
                res_method="text"
            )

    async def edit(
        self,
        *,
        name: str | None = MISSING,
        roles: list[PartialRole | int] | None = MISSING,
        reason: str | None = None
    ) -> "Emoji":
        """
        Edits the emoji.

        Parameters
        ----------
        name:
            The new name of the emoji.
        roles:
            Roles that are allowed to use the emoji. (Only for guilds)
        reason:
            The reason for editing the emoji. (Only for guilds)

        Returns
        -------
            The edited emoji.

        Raises
        ------
        ValueError
            Whenever guild_id is not defined
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = name

        if isinstance(roles, list):
            payload["roles"] = [
                int(r) for r in roles
                if isinstance(r, Snowflake)
            ]

        if self.guild_id:
            r = await self._state.query(
                "PATCH",
                f"/guilds/{self.guild.id}/emojis/{self.id}",
                json=payload,
                reason=reason
            )

            return Emoji(
                state=self._state,
                guild=self.guild,
                data=r.response
            )

        if not payload.get("name"):
            raise ValueError(
                "name is required when guild_id for emoji is not defined"
            )

        r = await self._state.query(
            "PATCH",
            f"/applications/{self._state.application_id}/emojis/{self.id}",
            json={"name": payload["name"]},
        )

        return Emoji(
            state=self._state,
            data=r.response
        )


class Emoji(PartialEmoji):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | None" = None,
    ):
        super().__init__(
            state=state,
            id=int(data["id"]),
            guild_id=guild.id if guild else None
        )

        self.name: str = data["name"]
        self.animated: bool = data.get("animated", False)
        self.available: bool = data.get("available", True)
        self.require_colons: bool = data.get("require_colons", True)
        self.managed: bool = data.get("managed", False)

        self.user: "User | None" = None
        self.roles: list[PartialRole] = [
            PartialRole(state=state, id=r, guild_id=guild.id)
            for r in data.get("roles", [])
        ]

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Emoji id={self.id} name='{self.name}' animated={self.animated}>"

    def __str__(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"

    def _from_data(self, data: dict) -> None:
        if data.get("user"):
            from .user import User
            self.user = User(state=self._state, data=data["user"])

    @property
    def url(self) -> str:
        """ Returns the URL of the emoji. """
        return f"{Asset.BASE}/emojis/{self.id}.{'gif' if self.animated else 'png'}"
