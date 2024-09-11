from typing import TYPE_CHECKING, Optional, Union

from . import utils
from .asset import Asset
from .colour import Colour
from .embeds import Embed
from .file import File
from .flag import PublicFlags
from .mentions import AllowedMentions
from .object import PartialBase
from .response import ResponseType, MessageResponse
from .view import View

if TYPE_CHECKING:
    from .channel import DMChannel
    from .http import DiscordAPI
    from .message import Message

MISSING = utils.MISSING

__all__ = (
    "PartialUser",
    "User",
)


class PartialUser(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int
    ):
        super().__init__(id=int(id))
        self._state = state

    def __repr__(self) -> str:
        return f"<PartialUser id={self.id}>"

    @property
    def mention(self) -> str:
        """ `str`: Returns a string that allows you to mention the user """
        return f"<@!{self.id}>"

    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        channel_id: Optional[int] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
    ) -> "Message":
        """
        Send a message to the user

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        channel_id: `Optional[int]`
            Channel ID to send the message to, if not provided, it will create a DM channel
        embed: `Optional[Embed]`
            Embed of the message
        embeds: `Optional[list[Embed]]`
            Embeds of the message
        file: `Optional[File]`
            File of the message
        files: `Optional[Union[list[File], File]]`
            Files of the message
        view: `Optional[View]`
            Components of the message
        tts: `bool`
            Whether the message should be sent as TTS
        type: `Optional[ResponseType]`
            Which type of response should be sent
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions of the message

        Returns
        -------
        `Message`
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
            allowed_mentions=allowed_mentions,
        )

        r = await self._state.query(
            "POST",
            f"/channels/{channel_id}/messages",
            data=payload.to_multipart(is_request=True),
            headers={"Content-Type": payload.content_type}
        )

        from .message import Message
        return Message(
            state=self._state,
            data=r.response
        )

    async def create_dm(self) -> "DMChannel":
        """ `DMChannel`: Creates a DM channel with the user """
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
        """ `User`: Fetches the user """
        r = await self._state.query(
            "GET",
            f"/users/{self.id}"
        )

        return User(
            state=self._state,
            data=r.response
        )


class User(PartialUser):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(state=state, id=int(data["id"]))

        self.avatar: Optional[Asset] = None
        self.banner: Optional[Asset] = None

        self.name: str = data["username"]
        self.bot: bool = data.get("bot", False)
        self.system: bool = data.get("system", False)

        # This section is ONLY here because bots still have a discriminator
        self.discriminator: Optional[str] = data.get("discriminator", None)
        if self.discriminator == "0":
            # Instead of showing "0", just make it None....
            self.discriminator = None

        self.accent_colour: Optional[Colour] = None
        self.banner_colour: Optional[Colour] = None

        self.avatar_decoration: Optional[Asset] = None
        self.global_name: Optional[str] = data.get("global_name", None)

        self.public_flags: Optional[PublicFlags] = None

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

    def _from_data(self, data: dict):
        if data.get("avatar", None):
            self.avatar = Asset._from_avatar(
                self.id, data["avatar"]
            )

        if data.get("banner", None):
            self.banner = Asset._from_banner(
                self.id, data["banner"]
            )

        if data.get("accent_color", None):
            self.accent_colour = Colour(data["accent_color"])

        if data.get("banner_color", None):
            self.banner_colour = Colour.from_hex(data["banner_color"])

        if data.get("avatar_decoration", None):
            self.avatar_decoration = Asset._from_avatar_decoration(
                data["avatar_decoration"]
            )

        if data.get("public_flags", None):
            self.public_flags = PublicFlags(data["public_flags"])

    @property
    def global_avatar(self) -> Optional[Asset]:
        """ `Asset`: Alias for `User.avatar` """
        return self.avatar

    @property
    def display_name(self) -> str:
        """ `str`: Returns the user's display name """
        return self.global_name or self.name
