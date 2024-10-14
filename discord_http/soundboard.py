from typing import TYPE_CHECKING

from . import utils
from .file import File
from .object import PartialBase

if TYPE_CHECKING:
    from .guild import PartialGuild, Guild
    from .http import DiscordAPI

MISSING = utils.MISSING

__all__ = (
    "PartialSoundboardSound",
    "SoundboardSound",
)


class PartialSoundboardSound(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        guild_id: int | None = None
    ):
        super().__init__(id=int(id))
        self._state = state
        self.sound_id: int = self.id
        self.guild_id: int | None = guild_id

    def __repr__(self) -> str:
        return f"<PartialSoundboardSound id={self.id} guild_id={self.guild_id}>"

    @property
    def guild(self) -> "PartialGuild | None":
        """
        Returns the guild this soundboard sound is in

        Returns
        -------
        `PartialGuild`
            The guild this soundboard sound is in

        Raises
        ------
        `ValueError`
            guild_id is not defined, unable to create PartialGuild
        """
        if not self.guild_id:
            return None

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    async def fetch(self) -> "SoundboardSound":
        """
        Returns the soundboard sound data

        Returns
        -------
        `SoundboardSound`
            The soundboard sound data

        Raises
        ------
        `ValueError`
            Soundboard sound does not belong to a guild
        """

        if self.guild is None:
            raise ValueError("Soundboard sound does not belong to a guild")

        r = await self._state.query(
            "GET",
            f"/guild/{self.guild_id}/soundboard-sounds/{self.id}"
        )

        return SoundboardSound(
            state=self._state,
            data=r.response,
            guild=self.guild,
        )

    async def delete(
        self,
        *,
        reason: str | None = None
    ) -> None:
        """
        Delete the soundboard sound

        Parameters
        ----------
        reason: `str | None`
            The reason for deleting the soundboard sound

        Raises
        ------
        `ValueError`
            Soundboard sound does not belong to a guild
        """

        if self.guild_id is None:
            raise ValueError("Soundboard sound does not belong to a guild")

        await self._state.query(
            "DELETE",
            f"/guilds/{self.guild_id}/soundboard-sounds/{self.id}",
            reason=reason,
            res_method="text"
        )

    async def edit(
        self,
        *,
        name: "str | MISSING" = MISSING,
        volume: "int | MISSING" = MISSING,
        emoji_name: "str | MISSING" = MISSING,
        emoji_id: "str | MISSING" = MISSING,
        icon: "File | bytes | MISSING" = MISSING,
        reason: str | None = None,
    ) -> "SoundboardSound":
        """
        Edit the soundboard sound

        Parameters
        ----------
        name: `Optional[str]`
            The new name of the soundboard sound
        volume: `Optional[int]`
            The new volume of the soundboard sound
        emoji_name: `Optional[str]`
            The new unicode emoji of the soundboard sound
        emoji_id: `Optional[str]`
            The ID of the new custom emoji of the soundboard sound
        reason: `Union[str]`
            The reason for editing the soundboard sound

        Returns
        -------
        `Union[SoundboardSound, PartialSoundboardSound]`
            The edited soundboard sound and its data

        Raises
        ------
        `ValueError`
            - If both `emoji_name` and `emoji_id` are set
            - If there were no changes applied to the soundboard sound
            - Soundboard sound does not belong to a guild
        """
        payload = {}
        _sound: "SoundboardSound | None" = None

        if self.guild is None:
            raise ValueError("Soundboard sound does not belong to a guild")

        if name is not MISSING:
            payload["name"] = name
        if volume is not MISSING:
            payload["volume"] = volume
        if emoji_name is not MISSING:
            payload["emoji_name"] = emoji_name
        if emoji_id is not MISSING:
            payload["emoji_id"] = emoji_id
        if icon is not MISSING:
            payload["icon"] = utils.bytes_to_base64(icon)

        if (
            emoji_name is not MISSING and
            emoji_id is not MISSING
        ):
            raise ValueError("Cannot set both emoji_name and emoji_id")

        if payload:
            r = await self._state.query(
                "PATCH",
                f"/guilds/{self.guild_id}/soundboard-sounds/{self.id}",
                json=payload,
                reason=reason
            )

            _sound = SoundboardSound(
                state=self._state,
                guild=self.guild,
                data=r.response
            )

        if not _sound:
            raise ValueError(
                "There were no changes applied to the soundboard sound. "
                "No edits were taken"
            )

        return _sound


class SoundboardSound(PartialSoundboardSound):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict,
        guild: "PartialGuild | Guild | None",
    ):
        super().__init__(state=state, id=data["sound_id"], guild_id=guild.id if guild else None)

        self.name: str = data["name"]
        self.volume: int = data["volume"]
        self.emoji_id: int | None = utils.get_int(data, "emoji_id")
        self.emoji_name: int | None = data.get("emoji_name")
        self.available: bool = data["available"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<SoundboardSound id={self.id} name='{self.name}'>"
