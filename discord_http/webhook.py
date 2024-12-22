from typing import TYPE_CHECKING, Optional, Union, Literal, overload

from . import utils
from .embeds import Embed
from .enums import ResponseType
from .file import File
from .mentions import AllowedMentions
from .multipart import MultipartData
from .object import PartialBase
from .response import MessageResponse
from .user import User
from .view import View

if TYPE_CHECKING:
    from .channel import PartialChannel
    from .guild import Guild, PartialGuild
    from .http import DiscordAPI
    from .message import WebhookMessage, Poll

__all__ = (
    "PartialWebhook",
    "Webhook",
)

MISSING = utils.MISSING


class PartialWebhook(PartialBase):
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,
        token: Optional[str] = None
    ):
        super().__init__(id=int(id))
        self._state = state
        self._retry_codes = []
        self.token: Optional[str] = token

    def __repr__(self) -> str:
        return f"<PartialWebhook id={self.id}>"

    async def fetch(self) -> "Webhook":
        """ `Webhook`: Fetch the webhook """
        r = await self._state.query(
            "GET",
            f"/webhooks/{self.id}"
        )

        return Webhook(
            state=self._state,
            data=r.response
        )

    @overload
    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        username: Optional[str] = MISSING,
        avatar_url: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        ephemeral: Optional[bool] = False,
        view: Optional[View] = MISSING,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        wait: Literal[False],
        thread_id: Optional[int] = MISSING,
        poll: Optional["Poll"] = MISSING,
    ) -> None:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        username: Optional[str] = MISSING,
        avatar_url: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        ephemeral: Optional[bool] = False,
        view: Optional[View] = MISSING,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        wait: bool = True,
        thread_id: Optional[int] = MISSING,
        poll: Optional["Poll"] = MISSING,
    ) -> "WebhookMessage":
        ...

    async def send(
        self,
        content: Optional[str] = MISSING,
        *,
        username: Optional[str] = MISSING,
        avatar_url: Optional[str] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        ephemeral: Optional[bool] = False,
        view: Optional[View] = MISSING,
        type: Union[ResponseType, int] = 4,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        wait: bool = True,
        thread_id: Optional[int] = MISSING,
        poll: Optional["Poll"] = MISSING,
    ) -> Optional["WebhookMessage"]:
        """
        Send a message with the webhook

        Parameters
        ----------
        content: `Optional[str]`
            Content of the message
        username: `Optional[str]`
            Username of the webhook
        avatar_url: `Optional[str]`
            Avatar URL of the webhook
        embed: `Optional[Embed]`
            Embed of the message
        embeds: `Optional[list[Embed]]`
            Embeds of the message
        file: `Optional[File]`
            File of the message
        files: `Optional[Union[list[File], File]]`
            Files of the message
        ephemeral: `bool`
            Whether the message should be sent as ephemeral
        view: `Optional[View]`
            Components of the message
        type: `Optional[ResponseType]`
            Which type of response should be sent
        allowed_mentions: `Optional[AllowedMentions]`
            Allowed mentions of the message
        wait: `bool`
            Whether to wait for the message to be sent
        thread_id: `Optional[int]`
            Thread ID to send the message to
        poll: `Optional[Poll]`
            Poll to send with the message

        Returns
        -------
        `Optional[WebhookMessage]`
            The message that was sent, if `wait` is `True`.

        Raises
        ------
        `ValueError`
            - If the webhook has no token
            - If `avatar_url` does not start with `https://`
        """
        if self.token is None:
            raise ValueError("Cannot send a message with a webhook that has no token")

        params = {}
        if thread_id is not MISSING:
            params["thread_id"] = str(thread_id)
        if wait is True:
            params["wait"] = "true"

        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            ephemeral=ephemeral,
            view=view,
            type=type,
            poll=poll,
            allowed_mentions=allowed_mentions
        )

        multidata = MultipartData()

        if isinstance(payload.files, list):
            for i, file in enumerate(payload.files):
                multidata.attach(
                    f"file{i}",
                    file,  # type: ignore
                    filename=file.filename
                )

        _modified_payload = payload.to_dict(is_request=True)
        if username is not MISSING:
            _modified_payload["username"] = str(username)
        if avatar_url is not MISSING:
            if not avatar_url.startswith("https://"):
                raise ValueError("avatar_url must start with https://")
            _modified_payload["avatar_url"] = str(avatar_url)

        multidata.attach("payload_json", _modified_payload)

        r = await self._state.query(
            "POST",
            f"/webhooks/{self.id}/{self.token}",
            webhook=True,
            params=params,
            data=multidata.finish(),
            headers={"Content-Type": multidata.content_type},
            retry_codes=self._retry_codes
        )

        if wait is True:
            from .message import WebhookMessage
            return WebhookMessage(
                state=self._state,
                data=r.response,
                application_id=self.id,
                token=self.token
            )

        return None

    async def delete(
        self,
        *,
        reason: Optional[str] = None
    ) -> None:
        """
        Delete the webhook

        Parameters
        ----------
        reason: `Optional[str]`
            The reason for deleting the webhook
        """
        if self.token is None:
            await self._state.query(
                "DELETE",
                f"/webhooks/{self.id}",
                res_method="text"
            )

            return None

        await self._state.query(
            "DELETE",
            f"/webhooks/{self.id}/{self.token}",
            res_method="text",
            reason=reason
        )

    async def edit(
        self,
        *,
        name: Optional[str] = MISSING,
        avatar: Optional[Union[File, bytes]] = MISSING,
        channel_id: Optional[int] = MISSING,
        reason: Optional[str] = None
    ) -> "Webhook":
        """
        Edit the webhook

        Parameters
        ----------
        name: `Optional[str]`
            Name of the webhook
        avatar: `Optional[File]`
            Avatar of the webhook
        channel_id: `Optional[int]`
            Channel ID to move the webhook to
        reason: `Optional[str]`
            Reason for the audit log

        Returns
        -------
        `Webhook`
            The webhook that was edited
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = str(name)
        if avatar is not MISSING:
            payload["avatar"] = utils.bytes_to_base64(avatar)  # type: ignore

        _api_url = f"/webhooks/{self.id}"

        if channel_id is not MISSING and self.token is MISSING:
            payload["channel_id"] = str(channel_id)
            _api_url += f"/{self.token}"

        r = await self._state.query(
            "PATCH",
            _api_url,
            json=payload,
            reason=reason
        )

        return Webhook(
            state=self._state,
            data=r.response
        )


class Webhook(PartialWebhook):
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self.application_id: Optional[int] = utils.get_int(data, "application_id")

        super().__init__(
            state=state,
            id=(
                self.application_id or
                utils.get_int(data, "id") or
                0
            ),
            token=data.get("token", None)
        )

        self.name: Optional[str] = data.get("name", None)
        self.avatar: Optional[str] = None
        self.url: Optional[str] = data.get("url", None)

        self.channel_id: Optional[int] = utils.get_int(data, "channel_id")
        self.guild_id: Optional[int] = utils.get_int(data, "guild_id")

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Webhook id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name or "Unknown"

    def _from_data(self, data: dict) -> None:
        self.user: Optional[User] = None
        if data.get("user", None):
            self.user = User(
                state=self._state,
                data=data["user"]
            )

    @classmethod
    def from_state(cls, *, state: "DiscordAPI", data: dict) -> "Webhook":
        """
        Creates a webhook from data, usually used for followup responses

        Parameters
        ----------
        state: `DiscordAPI`
            The state to use for the webhook
        data: `dict`
            The data to use for the webhook

        Returns
        -------
        `Webhook`
            The webhook that was created
        """
        _cls = cls(state=state, data=data)
        _cls._retry_codes = [404]
        return _cls

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ `Optional[PartialGuild]`: Returns the guild the webhook is in """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> Optional["PartialChannel"]:
        """ `Optional[PartialChannel]`: Returns the channel the webhook is in """
        if self.channel_id:
            from .channel import PartialChannel
            return PartialChannel(
                state=self._state,
                id=self.channel_id
            )

        return None
