from typing import TYPE_CHECKING, Literal, overload

from . import utils
from .embeds import Embed
from .enums import ResponseType
from .file import File
from .flags import MessageFlags
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
    """
    Represents a partial webhook object.

    Attributes
    ----------
    id: int
        The ID of the webhook
    token: str | None
        The token of the webhook, if any
    """
    def __init__(
        self,
        *,
        state: "DiscordAPI",
        id: int,  # noqa: A002
        token: str | None = None
    ):
        super().__init__(id=int(id))
        self._state = state
        self._retry_codes = []
        self.token: str | None = token

    def __repr__(self) -> str:
        return f"<PartialWebhook id={self.id}>"

    async def fetch(self) -> "Webhook":
        """ Fetch the webhook. """
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
        content: str | None = MISSING,
        *,
        username: str | None = MISSING,
        avatar_url: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        ephemeral: bool | None = False,
        view: View | None = MISSING,
        type: ResponseType | int = 4,
        allowed_mentions: AllowedMentions | None = MISSING,
        wait: Literal[False],
        flags: MessageFlags | None = MISSING,
        thread_id: int | None = MISSING,
        poll: "Poll | None" = MISSING,
    ) -> None:
        ...

    @overload
    async def send(
        self,
        content: str | None = MISSING,
        *,
        username: str | None = MISSING,
        avatar_url: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        ephemeral: bool | None = False,
        view: View | None = MISSING,
        type: ResponseType | int = 4,
        allowed_mentions: AllowedMentions | None = MISSING,
        wait: bool = True,
        flags: MessageFlags | None = MISSING,
        thread_id: int | None = MISSING,
        poll: "Poll | None" = MISSING,
    ) -> "WebhookMessage":
        ...

    async def send(
        self,
        content: str | None = MISSING,
        *,
        username: str | None = MISSING,
        avatar_url: str | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        ephemeral: bool | None = False,
        view: View | None = MISSING,
        type: ResponseType | int = 4,  # noqa: A002
        allowed_mentions: AllowedMentions | None = MISSING,
        wait: bool = True,
        flags: MessageFlags | None = MISSING,
        thread_id: int | None = MISSING,
        poll: "Poll | None" = MISSING,
    ) -> "WebhookMessage | None":
        """
        Send a message with the webhook.

        Parameters
        ----------
        content:
            Content of the message
        username:
            Username of the webhook
        avatar_url:
            Avatar URL of the webhook
        embed:
            Embed of the message
        embeds:
            Embeds of the message
        file:
            File of the message
        files:
            Files of the message
        ephemeral:
            Whether the message should be sent as ephemeral
        view:
            Components of the message
        type:
            Which type of response should be sent
        allowed_mentions:
            Allowed mentions of the message
        wait:
            Whether to wait for the message to be sent
        flags:
            Flags of the message
        thread_id:
            Thread ID to send the message to
        poll:
            Poll to send with the message

        Returns
        -------
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
        if view is not MISSING:
            params["with_components"] = "true"

        payload = MessageResponse(
            content=content,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            ephemeral=ephemeral,
            view=view,
            type=type,
            flags=flags,
            poll=poll,
            allowed_mentions=(
                allowed_mentions or
                self._state.bot._default_allowed_mentions
            )
        )

        multidata = MultipartData()

        if isinstance(payload.files, list):
            for i, file in enumerate(payload.files):
                multidata.attach(
                    f"file{i}",
                    file,  # type: ignore
                    filename=file.filename
                )

        modified_payload = payload.to_dict(is_request=True)
        if username is not MISSING:
            modified_payload["username"] = str(username)
        if avatar_url is not MISSING:
            if not avatar_url.startswith("https://"):
                raise ValueError("avatar_url must start with https://")
            modified_payload["avatar_url"] = str(avatar_url)

        multidata.attach("payload_json", modified_payload)

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
        reason: str | None = None
    ) -> None:
        """
        Delete the webhook.

        Parameters
        ----------
        reason:
            The reason for deleting the webhook
        """
        if self.token is None:
            await self._state.query(
                "DELETE",
                f"/webhooks/{self.id}",
                res_method="text"
            )

            return

        await self._state.query(
            "DELETE",
            f"/webhooks/{self.id}/{self.token}",
            res_method="text",
            reason=reason
        )

    async def edit(
        self,
        *,
        name: str | None = MISSING,
        avatar: File | bytes | None = MISSING,
        channel_id: int | None = MISSING,
        reason: str | None = None
    ) -> "Webhook":
        """
        Edit the webhook.

        Parameters
        ----------
        name:
            Name of the webhook
        avatar:
            Avatar of the webhook
        channel_id:
            Channel ID to move the webhook to
        reason:
            Reason for the audit log

        Returns
        -------
            The webhook that was edited
        """
        payload = {}

        if name is not MISSING:
            payload["name"] = str(name)
        if avatar is not MISSING:
            payload["avatar"] = utils.bytes_to_base64(avatar)  # type: ignore

        api_url = f"/webhooks/{self.id}"

        if channel_id is not MISSING and self.token is MISSING:
            payload["channel_id"] = str(channel_id)
            api_url += f"/{self.token}"

        r = await self._state.query(
            "PATCH",
            api_url,
            json=payload,
            reason=reason
        )

        return Webhook(
            state=self._state,
            data=r.response
        )


class Webhook(PartialWebhook):
    """
    Represents a webhook object.

    Attributes
    ----------
    application_id: int | None
        The ID of the application that created the webhook, if any
    name: str | None
        The name of the webhook, if any
    avatar: str | None
        The avatar of the webhook, if any
    url: str | None
        The URL of the webhook, if any
    channel_id: int | None
        The ID of the channel this webhook is in, if any
    guild_id: int | None
        The ID of the guild this webhook is in, if any
    """
    def __init__(self, *, state: "DiscordAPI", data: dict):
        self.application_id: int | None = utils.get_int(data, "application_id")

        super().__init__(
            state=state,
            id=(
                self.application_id or
                utils.get_int(data, "id") or
                0
            ),
            token=data.get("token")
        )

        self.name: str | None = data.get("name")
        self.avatar: str | None = None
        self.url: str | None = data.get("url")

        self.channel_id: int | None = utils.get_int(data, "channel_id")
        self.guild_id: int | None = utils.get_int(data, "guild_id")

        self._from_data(data)

    def __repr__(self) -> str:
        return f"<Webhook id={self.id} name='{self.name}'>"

    def __str__(self) -> str:
        return self.name or "Unknown"

    def _from_data(self, data: dict) -> None:
        self.user: User | None = None
        if data.get("user"):
            self.user = User(
                state=self._state,
                data=data["user"]
            )

    @classmethod
    def from_state(cls, *, state: "DiscordAPI", data: dict) -> "Webhook":
        """
        Creates a webhook from data, usually used for followup responses.

        Parameters
        ----------
        state:
            The state to use for the webhook
        data:
            The data to use for the webhook

        Returns
        -------
            The webhook that was created
        """
        cls_ = cls(state=state, data=data)
        cls_._retry_codes = [404]
        return cls_

    @property
    def guild(self) -> "Guild | PartialGuild | None":
        """ Returns the guild the webhook is in. """
        if not self.guild_id:
            return None

        cache = self._state.cache.get_guild(self.guild_id)
        if cache:
            return cache

        from .guild import PartialGuild
        return PartialGuild(state=self._state, id=self.guild_id)

    @property
    def channel(self) -> "PartialChannel | None":
        """ Returns the channel the webhook is in. """
        if self.channel_id:
            from .channel import PartialChannel
            return PartialChannel(
                state=self._state,
                id=self.channel_id
            )

        return None
