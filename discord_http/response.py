from typing import TYPE_CHECKING, Union, Any, Optional

from . import utils
from .embeds import Embed
from .enums import ResponseType
from .file import File
from .flags import MessageFlags
from .mentions import AllowedMentions
from .multipart import MultipartData
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
        self.version: int = int(data["version"])

    def __repr__(self) -> str:
        return f"<Ping application={self.application} user='{self.user}'>"

    @property
    def application(self) -> "PartialUser":
        """ `User`: Returns the user object of the bot """
        from .user import PartialUser
        return PartialUser(state=self._state, id=self.application_id)

    @property
    def user(self) -> "User":
        """ `User`: Returns the user object of the bot """
        from .user import User
        return User(state=self._state, data=self._raw_user)


class BaseResponse:
    def __init__(self):
        pass

    @property
    def content_type(self) -> str:
        """ `str`: Returns the content type of the response """
        multidata = MultipartData()
        return multidata.content_type

    def to_dict(self) -> dict:
        """ Default method to convert the response to a `dict` """
        raise NotImplementedError

    def to_multipart(self) -> bytes:
        """ Default method to convert the response to a `bytes` """
        raise NotImplementedError


class DeferResponse(BaseResponse):
    def __init__(
        self,
        *,
        ephemeral: bool = False,
        thinking: bool = False,
        flags: MessageFlags | None = None,
    ):
        self.ephemeral = ephemeral
        self.thinking = thinking
        self.flags = flags or MessageFlags(0)

        if self.ephemeral:
            self.flags |= MessageFlags.ephemeral

    def to_dict(self) -> dict:
        """ `dict`: Returns the response as a `dict` """
        return {
            "type": (
                int(ResponseType.deferred_channel_message_with_source)
                if self.thinking else int(ResponseType.deferred_update_message)
            ),
            "data": {
                "flags": int(self.flags)
            }
        }

    def to_multipart(self) -> bytes:
        """ `bytes`: Returns the response as a `bytes` """
        multidata = MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class AutocompleteResponse(BaseResponse):
    def __init__(
        self,
        choices: dict[Any, str]
    ):
        self.choices = choices

    def to_dict(self) -> dict:
        """ `dict`: Returns the response as a `dict` """
        return {
            "type": int(ResponseType.application_command_autocomplete_result),
            "data": {
                "choices": [
                    {"name": value, "value": key}
                    for key, value in self.choices.items()
                ][:25]  # Discord only allows 25 choices, so we limit it
            }
        }

    def to_multipart(self) -> bytes:
        """ `bytes`: Returns the response as a `bytes` """
        multidata = MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class ModalResponse(BaseResponse):
    def __init__(self, modal: Modal):
        self.modal = modal

    def to_dict(self) -> dict:
        """ `dict`: Returns the response as a `dict` """
        return {
            "type": int(ResponseType.modal),
            "data": self.modal.to_dict()
        }

    def to_multipart(self) -> bytes:
        """ `bytes`: Returns the response as a `bytes` """
        multidata = MultipartData()
        multidata.attach("payload_json", self.to_dict())

        return multidata.finish()


class MessageResponse(BaseResponse):
    def __init__(
        self,
        content: Optional[str] = MISSING,
        *,
        file: Optional[File] = MISSING,
        files: Optional[list[File]] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Optional[list[Embed]] = MISSING,
        attachment: Optional[File] = MISSING,
        attachments: Optional[list[File]] = MISSING,
        view: Optional[View] = MISSING,
        tts: Optional[bool] = False,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        message_reference: Optional["MessageReference"] = MISSING,
        poll: Optional["Poll"] = MISSING,
        type: Union[ResponseType, int] = 4,
        ephemeral: Optional[bool] = False,
        flags: MessageFlags | None = MISSING,
    ):
        self.content = content
        self.files = files
        self.embeds = embeds
        self.attachments = attachments
        self.ephemeral = ephemeral
        self.view = view
        self.tts = tts
        self.type = type
        self.allowed_mentions = allowed_mentions
        self.message_reference = message_reference
        self.poll = poll
        self.flags = flags or MessageFlags(0)

        if file is not MISSING and files is not MISSING:
            raise TypeError("Cannot pass both file and files")
        if file is not MISSING:
            self.files = [file]

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError("Cannot pass both embed and embeds")
        if embed is not MISSING:
            if embed is None:
                self.embeds = []
            else:
                self.embeds = [embed]

        if attachment is not MISSING and attachments is not MISSING:
            raise TypeError("Cannot pass both attachment and attachments")
        if attachment is not MISSING:
            if attachment is None:
                self.attachments = []
            else:
                self.attachments = [attachment]

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
        is_request: `bool`
            Whether the data is being sent to Discord or not.

        Returns
        -------
        `dict`
            The JSON data that can either be sent
            to Discord or forwarded to a new parser
        """
        output: dict[str, Any] = {
            "flags": int(self.flags)
        }

        if self.content is not MISSING:
            output["content"] = self.content

        if self.tts:
            output["tts"] = self.tts

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
            output["components"] = self.view.to_dict()

        if self.allowed_mentions is not MISSING:
            output["allowed_mentions"] = self.allowed_mentions.to_dict()

        if self.attachments is not MISSING:
            if self.attachments is None:
                output["attachments"] = []
            else:
                _index = 0
                _file_payload = []
                for a in self.attachments:
                    if not isinstance(a, File):
                        continue
                    _file_payload.append(a.to_dict(_index))
                    _index += 1
                output["attachments"] = _file_payload

        if is_request:
            return output
        return {"type": int(self.type), "data": output}

    def to_multipart(self, is_request: bool = False) -> bytes:
        """
        The multipart data that is sent to Discord.

        Parameters
        ----------
        is_request: `bool`
            Whether the data is being sent to Discord or not.

        Returns
        -------
        `bytes`
            The multipart data that can either be sent
        """
        multidata = MultipartData()

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
