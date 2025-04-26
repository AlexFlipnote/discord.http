from typing import TYPE_CHECKING, Any

from . import utils
from .asset import Asset
from .colour import Colour
from .embeds import Embed
from .enums import DefaultAvatarType
from .file import File
from .flags import UserFlags, MessageFlags
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
    "UserClient",
)


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

        self.avatar_decoration: Asset | None = None
        self.global_name: str | None = data.get("global_name")

        self.public_flags: UserFlags | None = None

        # This might change a lot
        self.clan: dict | None = data.get("clan")
        self.collectibles: dict | None = data.get("collectibles")
        self.avatar_decoration_data: dict | None = data.get("avatar_decoration_data")

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
        if data.get("avatar"):
            self.avatar = Asset._from_avatar(
                self._state, self.id, data["avatar"]
            )

        if data.get("banner"):
            self.banner = Asset._from_banner(
                self._state, self.id, data["banner"]
            )

        if data.get("accent_color"):
            self.accent_colour = Colour(data["accent_color"])

        if data.get("banner_color"):
            self.banner_colour = Colour.from_hex(data["banner_color"])

        if data.get("avatar_decoration_data") and data["avatar_decoration_data"].get("asset"):
            self.avatar_decoration = Asset._from_avatar_decoration(
                self._state, data["avatar_decoration_data"]["asset"]
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
    def global_avatar_decoration(self) -> Asset | None:
        """ Alias for `User.avatar_decoration`. """
        return self.avatar_decoration

    @property
    def global_avatar_decoration_data(self) -> dict | None:
        """ Alias for `User.avatar_decoration_data`. """
        return self.avatar_decoration_data

    @property
    def display_avatar_decoration(self) -> Asset | None:
        """ An alias to merge with `Member.display_avatar_decoration`. """
        return self.avatar_decoration

    @property
    def display_avatar_decoration_data(self) -> dict | None:
        """ An alias to merge with `Member.display_avatar_decoration_data`. """
        return self.avatar_decoration_data


class UserClient(User):
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
