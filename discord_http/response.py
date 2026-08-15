from aiohttp import MultipartWriter
from typing import TYPE_CHECKING, Any

from . import utils
from .embeds import Embed
from .enums import ResponseType
from .file import File
from .flags import MessageFlags
from .mentions import AllowedMentions
from .object import Snowflake
from .view import View, Modal

if TYPE_CHECKING:
    from .http import DiscordAPI
    from .message import MessageReference, Poll
    from .user import PartialUser, User

MISSING = utils.MISSING

__all__ = (
    "AutocompleteResponse",
    "DeferResponse",
    "MessageResponse",
    "Ping",
)


class Ping(Snowflake):
    """
    Represents a ping response from the Discord API.

    Usually reserved for internal use.
    """

    __slots__ = (
        "_raw_user",
        "_state",
        "application_id",
        "version",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        super().__init__(id=int(data["id"]))

        self._state = state
        self._raw_user = data["user"]

        self.application_id: int = int(data["application_id"])
        """ The ID of the application that created the ping. """

        self.version: int = int(data["version"])
        """ The version of the ping. """

    def __repr__(self) -> str:
        return f"<Ping application={self.application} user='{self.user}'>"

    @property
    def application(self) -> "PartialUser":
        """ The partial user object of the application. """
        from .user import PartialUser
        return PartialUser(state=self._state, id=self.application_id)

    @property
    def user(self) -> "User":
        """ The user object of the bot. """
        from .user import User
        return User(state=self._state, data=self._raw_user)


class BaseResponse:
    """ Represents a base response for interactions. """

    __slots__ = ()

    def __init__(self):
        pass

    @property
    def content_type(self) -> str:
        """ The content type of the response. """
        multidata = utils.MultipartData()
        return multidata.content_type

    def to_dict(self) -> dict:
        """ Default method to convert the response to a `dict`. """
        raise NotImplementedError

    def to_multipart(self) -> bytes:
        """ Default method to covnert the response to multipart data. """
        raise NotImplementedError


class DeferResponse(BaseResponse):
    """ Represents a response that defers the interaction. """

    __slots__ = (
        "ephemeral",
        "flags",
        "thinking",
    )

    def __init__(
        self,
        *,
        thinking: bool = False,
        ephemeral: bool = False,
        flags: MessageFlags | None = None,
    ):
        self.ephemeral = ephemeral
        """ Whether the response is ephemeral or not. """

        self.thinking = thinking
        """ Whether the response is thinking or not. """

        self.flags = flags or MessageFlags(0)
        """ The flags for the response. """

        if self.ephemeral:
            self.flags |= MessageFlags.ephemeral

    def to_dict(self) -> dict:
        """ Returns the response as a `dict`. """
        return {
            "type": (
                int(ResponseType.deferred_channel_message_with_source)
                if self.thinking else int(ResponseType.deferred_update_message)
            ),
            "data": {
                "flags": int(self.flags)
            }
        }

    def to_multipart(self) -> MultipartWriter:
        """ Returns the multipart data. """
        multidata = utils.MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class AutocompleteResponse(BaseResponse):
    """ Represents an autocomplete response. """

    __slots__ = ("choices",)

    def __init__(
        self,
        choices: dict[Any, str]
    ):
        self.choices = choices
        """ A dictionary of choices, where keys are sent to Discord and values are shown to the user. """

    def to_dict(self) -> dict:
        """ Returns the response as a `dict`. """
        return {
            "type": int(ResponseType.application_command_autocomplete_result),
            "data": {
                "choices": [
                    {"name": value, "value": key}
                    for key, value in self.choices.items()
                ][:25]  # Discord only allows 25 choices, so we limit it
            }
        }

    def to_multipart(self) -> MultipartWriter:
        """ Returns the multipart data. """
        multidata = utils.MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class ModalResponse(BaseResponse):
    """ Represents a modal response. """

    __slots__ = ("modal",)

    def __init__(self, modal: Modal):
        self.modal = modal
        """ The modal to be displayed to the user. """

    def to_dict(self) -> dict:
        """ Returns the response as a `dict`. """
        return {
            "type": int(ResponseType.modal),
            "data": self.modal.to_dict()
        }

    def to_multipart(self) -> MultipartWriter:
        """ Returns the multipart data. """
        multidata = utils.MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class EmptyResponse(BaseResponse):
    """
    Represents an empty response.

    This is used when no data is needed to be sent back to Discord.
    Instead, you respond later with a normal message.
    """

    __slots__ = ()

    def __init__(self):
        pass

    def to_dict(self) -> dict:
        """ Returns the response as a `dict`. """
        return {}

    def to_multipart(self) -> bytes:
        """ Returns the multipart data. """
        return b""


class MessageResponse(BaseResponse):
    """ Represents a message response. """

    __slots__ = (
        "allowed_mentions",
        "attachments",
        "content",
        "embeds",
        "ephemeral",
        "files",
        "flags",
        "message_reference",
        "poll",
        "tts",
        "type",
        "view",
    )

    def __init__(
        self,
        content: str | None = MISSING,
        *,
        file: File | None = MISSING,
        files: list[File] | None = MISSING,
        embed: Embed | None = MISSING,
        embeds: list[Embed] | None = MISSING,
        attachment: File | None = MISSING,
        attachments: list[File] | None = MISSING,
        view: View | None = MISSING,
        tts: bool | None = False,
        allowed_mentions: AllowedMentions | None = MISSING,
        message_reference: "MessageReference | None" = MISSING,
        poll: "Poll | None" = MISSING,
        type: ResponseType | int = 4,  # ruff: ignore[builtin-argument-shadowing]
        ephemeral: bool | None = False,
        flags: MessageFlags | None = MISSING,
    ):
        self.content = content
        """ The content of the message. """

        self.files = files
        """ The files to be sent with the message. A single file may be passed via `file` instead. """

        self.embeds = embeds
        """ The embeds to be sent with the message. A single embed may be passed via `embed` instead. """

        self.attachments = attachments
        """ The attachments to be sent with the message. A single attachment may be passed via `attachment` instead. """

        self.ephemeral = ephemeral
        """ Whether the message should be ephemeral or not. """

        self.view = view
        """ A view to be sent with the message. """

        self.tts = tts
        """ Whether the message should be sent as a TTS message. """

        self.type = type
        """ The type of the response. Defaults to `ResponseType.message`. """

        self.allowed_mentions = allowed_mentions
        """ Allowed mentions for the message. """

        self.message_reference = message_reference
        """ A reference to another message, if applicable. """

        self.poll = poll
        """ A poll to be sent with the message. """

        self.flags = flags or MessageFlags(0)
        """ Flags for the message response. """

        if file is not MISSING and files is not MISSING:
            raise TypeError("Cannot pass both file and files")
        if file is not MISSING:
            self.files = [file]

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError("Cannot pass both embed and embeds")
        if embed is not MISSING:
            self.embeds = [embed]

        if attachment is not MISSING and attachments is not MISSING:
            raise TypeError("Cannot pass both attachment and attachments")
        if attachment is not MISSING:
            self.attachments = [attachment]

        if embed is None or embeds is None:
            self.embeds = []
        if file is None or files is None:
            self.files = []
        if attachment is None or attachments is None:
            self.attachments = []

        if self.view is not MISSING and self.view is None:
            self.view = View()

        if self.attachments is not MISSING:
            self.files = (
                [a for a in self.attachments if isinstance(a, File)]
                if self.attachments is not None else None
            )

        if self.ephemeral:
            self.flags |= MessageFlags.ephemeral

    def to_dict(self, is_request: bool = False) -> dict:
        """
        The JSON data that is sent to Discord.

        Parameters
        ----------
        is_request
            Whether the data is being sent to Discord or not.

        Returns
        -------
            The JSON data that can either be sent
            to Discord or forwarded to a new parser
        """
        output: dict[str, Any] = {
            "flags": int(self.flags)
        }

        if self.content is not MISSING:
            # Just force anything to a string, unless it's a None
            output["content"] = (
                str(self.content)
                if self.content is not None
                else None
            )

        if self.tts:
            output["tts"] = bool(self.tts)

        if self.message_reference is not MISSING:
            output["message_reference"] = self.message_reference.to_dict()

        if self.embeds is not MISSING:
            output["embeds"] = [
                embed.to_dict() for embed in self.embeds  # type: ignore
                if isinstance(embed, Embed)
            ]

        if self.poll is not MISSING:
            output["poll"] = self.poll.to_dict()

        if self.view is not MISSING:
            if not self.view.items:
                output["components"] = []
            else:
                output["components"] = self.view.to_dict()

        if self.allowed_mentions is not MISSING:
            output["allowed_mentions"] = self.allowed_mentions.to_dict()

        if self.attachments is not MISSING:
            if self.attachments is None:
                output["attachments"] = []
            else:
                index = 0
                file_payload = []
                for a in self.attachments:
                    if not isinstance(a, File):
                        continue
                    file_payload.append(a.to_dict(index))
                    index += 1
                output["attachments"] = file_payload

        if is_request:
            return output
        return {"type": int(self.type), "data": output}

    def to_multipart(self, is_request: bool = False) -> MultipartWriter:
        """
        The multipart data that is sent to Discord.

        Parameters
        ----------
        is_request
            Whether the data is being sent to Discord or not.

        Returns
        -------
            The multipart data that can either be sent to Discord or forwarded to a new parser
        """
        multidata = utils.MultipartData()

        if isinstance(self.files, list):
            for i, file in enumerate(self.files):
                multidata.attach(
                    f"files[{i}]",
                    file,  # type: ignore
                    filename=file.filename
                )

        multidata.attach(
            "payload_json",
            self.to_dict(is_request=is_request)
        )

        return multidata.finish()
