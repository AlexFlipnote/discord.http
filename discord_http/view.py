import asyncio
import inspect
import logging
import secrets
import time

from collections.abc import Callable
from io import BytesIO
from typing import TYPE_CHECKING

from .asset import Asset
from .colour import Colour
from .emoji import EmojiParser
from .enums import (
    ButtonStyles, ComponentType, TextStyles,
    ChannelType, SeparatorSpacingType
)
from .errors import HTTPException
from .file import File

if TYPE_CHECKING:
    from . import Snowflake
    from .channel import BaseChannel
    from .context import Context
    from .http import DiscordAPI
    from .member import Member
    from .response import BaseResponse
    from .role import Role

_log = logging.getLogger(__name__)

_components_action_row = (
    ComponentType.button,
    ComponentType.string_select,
    ComponentType.text_input,
    ComponentType.user_select,
    ComponentType.role_select,
    ComponentType.mentionable_select,
    ComponentType.channel_select,
)

_components_v2 = (
    ComponentType.action_row,
    ComponentType.section,
    ComponentType.text_display,
    ComponentType.thumbnail,
    ComponentType.media_gallery,
    ComponentType.file,
    ComponentType.separator,
)

_components_root = (
    ComponentType.action_row,
    ComponentType.section,
    ComponentType.text_display,
    ComponentType.media_gallery,
    ComponentType.file,
    ComponentType.separator,
    ComponentType.container,
)

_components_label = (
    ComponentType.text_input,
    ComponentType.string_select,
    ComponentType.role_select,
    ComponentType.user_select,
    ComponentType.mentionable_select,
    ComponentType.channel_select,
    ComponentType.file_upload,
    ComponentType.radio_group,
    ComponentType.checkbox_group,
    ComponentType.checkbox,
)

_components_inaccessible = (
    ComponentType.content_inventory_entry,
    ComponentType.checkpoint,
)

__all__ = (
    "ActionRow",
    "AttachmentComponent",
    "Button",
    "ChannelSelect",
    "CheckboxComponent",
    "CheckboxGroupComponent",
    "ComponentOption",
    "ContainerComponent",
    "FileComponent",
    "FileUploadComponent",
    "Item",
    "Link",
    "MediaGalleryComponent",
    "MediaGalleryItem",
    "MentionableSelect",
    "Modal",
    "Premium",
    "RadioComponent",
    "RoleSelect",
    "SectionComponent",
    "Select",
    "SeparatorComponent",
    "TextDisplayComponent",
    "TextInputComponent",
    "ThumbnailComponent",
    "UserSelect",
    "View",
)


def _garbage_id() -> str:
    """ Returns a random ID to satisfy Discord API. """
    return secrets.token_hex(16)


class AttachmentComponent:
    """ Represents an attachment component. """

    __slots__ = (
        "_edata",
        "_file",
        "_media",
        "_state",
        "_url",
        "content_type",
        "filename",
        "flags",
        "height",
        "placeholder",
        "placeholder_version",
        "proxy_url",
        "size",
        "spoiler",
        "url",
        "width",
    )

    def __init__(
        self,
        *,
        state: "DiscordAPI",
        data: dict
    ):
        self._state = state

        self._file: dict | None = data.get("file")
        self._media: dict | None = data.get("media")

        self._edata = self._file or self._media
        if self._edata is None:
            raise ValueError("Either file or media must be provided")

        self.spoiler: bool = data.get("spoiler", False)
        """ Whether the attachment is a spoiler or not. """

        self.filename: str | None = data.get("name", "")
        """ The filename of the attachment, if any. """

        self.size: int = data.get("size", 0)
        """ The size of the attachment in bytes. """

        self.url: str = self._edata["url"]
        """ The URL of the attachment. """

        self.proxy_url: str = self._edata["proxy_url"]
        """ The proxied URL of the attachment. """

        self.height: int | None = self._edata.get("height", None)
        """ The height of the attachment, if any. """

        self.width: int | None = self._edata.get("width", None)
        """ The width of the attachment, if any. """

        self.placeholder: str | None = self._edata.get("placeholder", None)
        """ The placeholder of the attachment, if any. """

        self.placeholder_version: int | None = self._edata.get("placeholder_version", None)
        """ The placeholder version of the attachment, if any. """

        self.content_type: str | None = self._edata.get("content_type", None)
        """ The content type of the attachment, if any. """

        self.flags: int = self._edata.get("flags", 0)
        """ The flags of the attachment, if any. """

    def __str__(self) -> str:
        if self.filename:
            return f"attachment://{self.filename}"
        return self.url

    def __repr__(self) -> str:
        return f"<AttachmentComponent url={self.url}>"

    async def fetch(self, *, use_cached: bool = False) -> bytes:
        """
        Fetches the file from the attachment URL and returns it as bytes.

        Parameters
        ----------
        use_cached:
            Whether to use the cached URL or not, defaults to `False`

        Returns
        -------
            The attachment as bytes

        Raises
        ------
        `HTTPException`
            If the request returned anything other than 2XX
        """
        r = await self._state.http.request(
            "GET",
            self.proxy_url if use_cached else self.url,
            res_method="read"
        )

        if r.status not in range(200, 300):
            raise HTTPException(r)

        return r.response

    async def save(
        self,
        path: str,
        *,
        use_cached: bool = False
    ) -> int:
        """
        Fetches the file from the attachment URL and saves it locally to the path.

        Parameters
        ----------
        path:
            Path to save the file to, which includes the filename and extension.
            Example: `./path/to/file.png`
        use_cached:
            Whether to use the cached URL or not, defaults to `False`

        Returns
        -------
            The amount of bytes written to the file
        """
        data = await self.fetch(use_cached=use_cached)
        with open(path, "wb") as f:
            return f.write(data)

    async def to_file(
        self,
        *,
        filename: str,
        spoiler: bool = False
    ) -> File:
        """
        Convert the attachment to a sendable File object for Message.send().

        Parameters
        ----------
        filename:
            Filename for the file, if empty, the attachment's filename will be used
        spoiler:
            Weather the file should be marked as a spoiler or not, defaults to `False`

        Returns
        -------
            The attachment as a File object
        """
        data = await self.fetch()

        return File(
            data=BytesIO(data),
            filename=str(filename),
            spoiler=spoiler
        )

    def to_dict(self) -> dict:
        """The attachment as a dictionary. """
        data = {
            "filename": self.filename,
            "size": self.size,
            "url": self.url,
            "proxy_url": self.proxy_url,
            "spoiler": self.spoiler,
            "flags": self.flags
        }

        if self.height:
            data["height"] = self.height
        if self.width:
            data["width"] = self.width
        if self.content_type:
            data["content_type"] = self.content_type

        return data


class Item:
    """ Base class for all components in discord.http API. """

    __slots__ = ("type",)

    def __init__(
        self,
        *,
        type: ComponentType  # noqa: A002
    ):
        self.type: ComponentType = type
        """ The type of the component. """

    def __repr__(self) -> str:
        return f"<Item type={self.type}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the item. """
        raise NotImplementedError("to_dict not implemented")


class LockedItem(Item):
    """ Used for valid components, but cannot be used directly. """

    __slots__ = ("_data",)

    def __init__(self, *, type: ComponentType, **kwargs: dict):  # noqa: A002
        self.type: ComponentType = type
        self._data: dict = kwargs

    def __repr__(self) -> str:
        return f"<LockedItem[{self.type.name}] data={self._data}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the content inventory entry. """
        return {
            "type": int(self.type),
            "data": {
                k: v
                for k, v in self._data.items()
            }
        }


class TextInputComponent(Item):
    """ Represents a text input component in a modal. """

    __slots__ = (
        "custom_id",
        "default",
        "description",
        "label",
        "max_length",
        "min_length",
        "placeholder",
        "required",
        "style",
    )

    def __init__(
        self,
        *,
        label: str | None = None,
        description: str | None = None,
        custom_id: str | None = None,
        style: TextStyles | None = None,
        placeholder: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        default: str | None = None,
        required: bool = True,
    ):
        super().__init__(type=ComponentType.text_input)

        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )
        """ The custom ID of the text input. """

        self.label: str | None = label
        """ The label of the text input. """

        self.description: str | None = description
        """ The description of the text input. """

        self.style: int = int(style or TextStyles.short)
        """ The style of the text input. """

        self.placeholder: str | None = placeholder
        """ The placeholder text of the text input. """

        self.min_length: int | None = min_length
        """ The minimum length of the text input. """

        self.max_length: int | None = max_length
        """ The maximum length of the text input. """

        self.default: str | None = default
        """ The default value of the text input. """

        self.required: bool = required
        """ Whether the text input is required or not. """

    def to_dict(self) -> dict:
        """ Returns a dict representation of the modal item. """
        if len(self.custom_id) > 100:
            raise ValueError("custom_id must be 100 characters or less")
        if self.placeholder and len(self.placeholder) > 100:
            raise ValueError("placeholder must be 100 characters or less")
        if self.default and len(self.default) > 4000:
            raise ValueError("default value must be 4000 characters or less")
        if isinstance(self.min_length, int) and self.min_length not in range(4001):
            raise ValueError("min_length must be between 0 and 4,000")
        if isinstance(self.max_length, int) and self.max_length not in range(1, 4001):
            raise ValueError("max_length must be between 1 and 4,000")

        payload = {
            "type": int(self.type),
            "custom_id": self.custom_id,
            "style": self.style,
            "required": self.required,
        }

        if self.min_length is not None:
            payload["min_length"] = int(self.min_length)
        if self.max_length is not None:
            payload["max_length"] = int(self.max_length)
        if self.placeholder is not None:
            payload["placeholder"] = str(self.placeholder)
        if self.default is not None:
            payload["value"] = str(self.default)

        return payload


class Button(Item):
    """ Represents a button component in a message. """

    __slots__ = (
        "custom_id",
        "disabled",
        "emoji",
        "label",
        "sku_id",
        "style",
        "url",
    )

    def __init__(
        self,
        *,
        label: str | None = None,
        style: ButtonStyles | str | int = ButtonStyles.primary,
        disabled: bool = False,
        custom_id: str | None = None,
        sku_id: "Snowflake | int | None" = None,
        emoji: str | dict | None = None,
        url: str | None = None
    ):
        super().__init__(type=ComponentType.button)
        special_buttons = (ButtonStyles.link, ButtonStyles.premium)

        self.label: str | None = label
        """ The label of the button. """

        self.disabled: bool = disabled
        """ Whether the button is disabled or not. """

        self.url: str | None = url
        """ The URL of the button, only required for link buttons. """

        self.emoji: str | dict | None = emoji
        """ The emoji associated with the button. """

        self.sku_id: "Snowflake | int | None" = sku_id
        """ The SKU ID of the button, only required for premium buttons. """

        self.style: ButtonStyles | str | int = style
        """ The style of the button. """

        self.custom_id: str | None = (
            str(custom_id)
            if custom_id else _garbage_id()
        )
        """ The custom ID of the button. """

        match style:
            case x if isinstance(x, ButtonStyles):
                pass

            case x if isinstance(x, int):
                self.style = ButtonStyles(style)

            case x if isinstance(x, str):
                try:
                    self.style = ButtonStyles[style]  # type: ignore
                except KeyError:
                    self.style = ButtonStyles.primary

            case _:
                self.style = ButtonStyles.primary

        if self.style in special_buttons:
            self.custom_id = None  # Force none for special buttons

    def to_dict(self) -> dict:
        """ Returns a dict representation of the button. """
        if self.style == ButtonStyles.link and not self.url:
            raise ValueError("url is required for link buttons")
        if self.style == ButtonStyles.premium and not self.sku_id:
            raise ValueError("sku_id is required for premium buttons")

        payload = {
            "type": int(self.type),
            "style": int(self.style),
            "disabled": self.disabled,
        }

        if self.sku_id:
            if self.style != ButtonStyles.premium:
                raise ValueError("Cannot have sku_id without premium style")

            # Ignore everything else if sku_id is present
            # https://discord.com/developers/docs/interactions/message-components#button-object-button-structure
            payload["sku_id"] = str(int(self.sku_id))
            return payload

        if self.custom_id and self.url:
            raise ValueError("Cannot have both custom_id and url")

        if self.emoji:
            if isinstance(self.emoji, str):
                payload["emoji"] = EmojiParser(self.emoji).to_dict()
            elif isinstance(self.emoji, dict):
                payload["emoji"] = self.emoji

        if self.label:
            if len(self.label) > 80:
                raise ValueError("button label must be 80 characters or less")
            payload["label"] = self.label

        if self.custom_id:
            if len(self.custom_id) > 100:
                raise ValueError("button custom_id must be 100 characters or less")
            payload["custom_id"] = self.custom_id

        if self.url:
            if len(self.url) > 512:
                raise ValueError("button url must be 512 characters or less")
            payload["url"] = self.url

        return payload


class Premium(Button):
    """ Button alias for the premium SKU style. """

    __slots__ = ()

    def __init__(
        self,
        sku_id: "Snowflake | int"
    ):
        super().__init__(
            sku_id=sku_id,
            style=ButtonStyles.premium
        )

    def __repr__(self) -> str:
        return f"<Premium sku_id={self.sku_id}>"


class Link(Button):
    """ Button alias for the link style. """

    __slots__ = ()

    def __init__(
        self,
        *,
        url: str,
        label: str | None = None,
        emoji: str | None = None,
        disabled: bool = False
    ):
        super().__init__(
            url=url,
            label=label,
            emoji=emoji,
            style=ButtonStyles.link,
            disabled=disabled
        )

        # Link buttons use url instead of custom_id
        self.custom_id: str | None = None
        """ The custom ID of the button. """

    def __repr__(self) -> str:
        return f"<Link url='{self.url}'>"


class Select(Item):
    """ Represents a select menu component in a message. """

    __slots__ = (
        "_default_values",
        "_options",
        "custom_id",
        "description",
        "disabled",
        "label",
        "max_values",
        "min_values",
        "options",
        "placeholder",
        "required",
    )

    def __init__(
        self,
        *,
        label: str | None = None,
        description: str | None = None,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        disabled: bool = False,
        options: list[dict] | None = None,
        required: bool | None = None,
        _type: ComponentType | None = None
    ):
        super().__init__(
            type=_type or ComponentType.string_select
        )

        self.label: str | None = label
        """ The label of the select menu (only works for modals). """

        self.description: str | None = description
        """ The description of the select menu (only works for modals). """

        self.placeholder: str | None = placeholder
        """ The placeholder text for the select menu. """

        self.min_values: int | None = min_values
        """ The minimum number of values that can be selected. """

        self.max_values: int | None = max_values
        """ The maximum number of values that can be selected. """

        self.disabled: bool = disabled
        """ Whether the select menu is disabled or not. """

        self.required: bool | None = required
        """ Whether the select menu is required or not (only works for modals). """

        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )
        """ The custom ID of the select menu. """

        self._options: list[dict] = options or []
        self._default_values: list[dict[str, str]] = []

    def __repr__(self) -> str:
        return f"<Select custom_id='{self.custom_id}'>"

    def add_item(
        self,
        *,
        label: str,
        value: str,
        description: str | None = None,
        emoji: str | None = None,
        default: bool = False
    ) -> None:
        """
        Add an item to the select menu.

        Parameters
        ----------
        label:
            Label of the item
        value:
            The value of the item, which will be shown on interaction response
        description:
            Description of the item
        emoji:
            Emoji shown on the left side of the item
        default:
            Whether the item is selected by default

        Raises
        ------
        `ValueError`
            If there are more than 25 options
        """
        if len(self._options) >= 25:
            raise ValueError("Cannot have more than 25 options in a select menu")

        payload: dict = {
            "label": label,
            "value": value,
            "default": default
        }

        if description:
            payload["description"] = description
        if emoji:
            payload["emoji"] = EmojiParser(emoji).to_dict()

        self._options.append(payload)

    def to_dict(self) -> dict:
        """ Returns a dict representation of the select menu. """
        if len(self.custom_id) > 100:
            raise ValueError("custom_id must be 100 characters or less")
        if self.min_values is not None and not (0 <= self.min_values <= 25):
            raise ValueError("min_values must be between 0 and 25")
        if self.max_values is not None and not (1 <= self.max_values <= 25):
            raise ValueError("max_values must be between 1 and 25")

        for opt in self._options:
            if len(opt.get("label", "")) > 100:
                raise ValueError("Option label must be 100 characters or less")
            if len(opt.get("value", "")) > 100:
                raise ValueError("Option value must be 100 characters or less")
            if len(opt.get("description", "")) > 100:
                raise ValueError("Option description must be 100 characters or less")

        payload = {
            "type": int(self.type),
            "custom_id": self.custom_id,
            "min_values": self.min_values,
            "max_values": self.max_values,
            "disabled": self.disabled,
        }

        if self.placeholder is not None:
            if len(self.placeholder) > 150:
                raise ValueError("placeholder must be 150 characters or less")
            payload["placeholder"] = self.placeholder
        if self._default_values:
            payload["default_values"] = self._default_values
        if self._options:
            if len(self._options) > 25:
                raise ValueError("Cannot have more than 25 options")
            payload["options"] = self._options
        if self.required is not None:
            payload["required"] = self.required

        return payload


class UserSelect(Select):
    """ Represents a user select menu component in a message. """

    __slots__ = ()

    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["Member | int"] | None = None,
        disabled: bool = False,
        label: str | None = None,
        description: str | None = None,
        required: bool = False
    ):
        super().__init__(
            _type=ComponentType.user_select,
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            label=label,
            description=description,
            required=required
        )

        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "user"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<UserSelect custom_id='{self.custom_id}'>"


class RoleSelect(Select):
    """ Represents a role select menu component in a message. """

    __slots__ = ()

    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["Role | int"] | None = None,
        disabled: bool = False,
        label: str | None = None,
        description: str | None = None,
        required: bool = False
    ):
        super().__init__(
            _type=ComponentType.role_select,
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            label=label,
            description=description,
            required=required
        )

        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "role"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<RoleSelect custom_id='{self.custom_id}'>"


class MentionableSelect(Select):
    """ Represents a mentionable select menu component in a message. """

    __slots__ = ()

    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["Member | Role | int"] | None = None,
        disabled: bool = False,
        label: str | None = None,
        description: str | None = None,
        required: bool = False
    ):
        super().__init__(
            _type=ComponentType.mentionable_select,
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            label=label,
            description=description,
            required=required
        )

        # NOTE: Will be changed to accept roles too
        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "user"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<MentionableSelect custom_id='{self.custom_id}'>"


class ChannelSelect(Select):
    """ Represents a channel select menu component in a message. """

    __slots__ = ("channel_types",)

    def __init__(
        self,
        channel_types: ChannelType | int | list[ChannelType | int],
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["BaseChannel | int"] | None = None,
        disabled: bool = False,
        label: str | None = None,
        description: str | None = None,
        required: bool = False,
    ):
        super().__init__(
            _type=ComponentType.channel_select,
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            label=label,
            description=description,
            required=required
        )

        if not isinstance(channel_types, list):
            channel_types = [channel_types]

        # Reason for types is to make sure the ints are valid ChannelTypes
        self.channel_types = [
            ChannelType(int(c)) for c in channel_types
            if isinstance(c, (ChannelType, int))
        ]
        """ The channel types that can be selected. """

        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "channel"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<ChannelSelect custom_id='{self.custom_id}' channel_types={self.channel_types}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the channel select menu. """
        payload = super().to_dict()
        payload["channel_types"] = [int(c) for c in self.channel_types]
        return payload


class FileUploadComponent(Item):
    """ Represents a file upload component in a modal. """

    __slots__ = (
        "custom_id",
        "description",
        "label",
        "max_values",
        "min_values",
        "required",
    )

    def __init__(
        self,
        *,
        custom_id: str | None = None,
        min_values: int | None = None,
        max_values: int | None = None,
        label: str | None = None,
        description: str | None = None,
        required: bool = True,
    ):
        super().__init__(
            type=ComponentType.file_upload
        )

        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )
        """ The custom ID of the file upload component. """

        self.min_values: int | None = min_values
        """ The minimum number of values that can be uploaded. """

        self.max_values: int | None = max_values
        """ The maximum number of values that can be uploaded. """

        self.required: bool = required
        """ Whether the file upload component is required or not. """

        self.label: str | None = label
        """ The label of the file upload component. """

        self.description: str | None = description
        """ The description of the file upload component. """

    def __repr__(self) -> str:
        return f"<FileUploadComponent custom_id='{self.custom_id}'>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the file upload component. """
        if len(self.custom_id) > 100:
            raise ValueError("custom_id must be 100 characters or less")

        payload = {
            "type": int(self.type),
            "custom_id": self.custom_id,
            "required": self.required,
        }

        if self.min_values is not None:
            if not (0 <= self.min_values <= 10):
                raise ValueError("min_values must be between 0 and 10")
            payload["min_values"] = int(self.min_values)

        if self.max_values is not None:
            if not (1 <= self.max_values <= 10):
                raise ValueError("max_values must be between 1 and 10")
            payload["max_values"] = int(self.max_values)

        return payload


class TextDisplayComponent(Item):
    """ Represents a text display component in a message. """

    __slots__ = ("content",)

    def __init__(
        self,
        content: str
    ):
        super().__init__(type=ComponentType.text_display)

        self.content = content
        """ The content of the text display component. """

    def __repr__(self) -> str:
        return f"<TextDisplay content='{self.content}'>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the text display. """
        return {
            "type": int(self.type),
            "content": self.content
        }


class ComponentOption:
    """ Represents an option for radio and checkbox components. """

    __slots__ = (
        "default",
        "description",
        "label",
        "value",
    )

    def __init__(
        self,
        *,
        label: str,
        value: str,
        description: str | None = None,
        default: bool = False
    ):
        self.label = label
        """ The label of the option. """

        self.value = value
        """ The value of the option. """

        self.description = description
        """ The description of the option. """

        self.default = default
        """ Whether the option is the default selection. """

    def to_dict(self) -> dict:
        """ Returns a dict representation of the option. """
        if len(self.label) > 100:
            raise ValueError("label must be 100 characters or less")
        if len(self.value) > 100:
            raise ValueError("value must be 100 characters or less")

        payload: dict = {
            "value": str(self.value),
            "label": str(self.label),
        }

        if self.default:
            payload["default"] = True

        if self.description is not None:
            if len(self.description) > 100:
                raise ValueError("description must be 100 characters or less")
            payload["description"] = str(self.description)

        return payload


class RadioComponent(Item):
    """ Represents a radio button component in a modal. """

    __slots__ = (
        "custom_id",
        "description",
        "label",
        "options",
        "required",
    )

    def __init__(
        self,
        *options: "ComponentOption",
        custom_id: str,
        label: str | None = None,
        description: str | None = None,
        required: bool = True
    ):
        super().__init__(type=ComponentType.radio_group)

        self.options = list(options)
        """ The options for the radio component. """

        self.custom_id: str = custom_id
        """ The custom ID of the radio component. """

        self.required: bool = required
        """ Whether the radio component is required or not. """

        # Label shortcuts
        self.label: str | None = label
        """ The label of the radio component. """

        self.description: str | None = description
        """ The description of the radio component. """

    def add_item(self, value: str, label: str, description: str | None = None, default: bool = False) -> None:
        """
        Add an item to the radio component.

        Parameters
        ----------
        value:
            The value of the option, which will be returned on interaction response
        label:
            The label of the option, what the user sees
        description:
            The description of the option, additional text shown below the label
        default:
            Whether the option is the default selection
        """
        if len(self.options) >= 10:
            raise ValueError("Cannot have more than 10 options in a radio component")

        self.options.append(ComponentOption(
            value=value,
            label=label,
            description=description,
            default=default
        ))

    def to_dict(self) -> dict:
        """ Returns a dict representation of the radio component. """
        if len(self.custom_id) > 100:
            raise ValueError("custom_id must be 100 characters or less")
        if not (2 <= len(self.options) <= 10):
            raise ValueError("RadioComponent must have between 2 and 10 options")

        payload = {
            "type": int(self.type),
            "custom_id": self.custom_id,
            "options": [g.to_dict() for g in self.options]
        }

        if self.required:
            payload["required"] = bool(self.required)

        return payload


class CheckboxGroupComponent(Item):
    """ Represents a checkbox group component in a modal. """

    __slots__ = (
        "custom_id",
        "description",
        "label",
        "max_values",
        "min_values",
        "options",
        "required",
    )

    def __init__(
        self,
        *options: ComponentOption,
        custom_id: str | None = None,
        label: str | None = None,
        description: str | None = None,
        min_values: int = 1,
        max_values: int | None = None,
        required: bool = True
    ):
        super().__init__(type=ComponentType.checkbox_group)
        self.custom_id: str = custom_id or _garbage_id()
        """ The custom ID of the checkbox group component. """

        self.options: list[ComponentOption] = list(options)
        """ The options for the checkbox group component. """

        self.label: str | None = label
        """ The label of the checkbox group component. """

        self.description: str | None = description
        """ The description of the checkbox group component. """

        self.min_values: int = min_values
        """ The minimum number of values that can be selected. """

        self.max_values: int | None = max_values
        """ The maximum number of values that can be selected. """

        self.required: bool = required
        """ Whether the checkbox group component is required or not. """

    def add_item(self, value: str, label: str, description: str | None = None, default: bool = False) -> None:
        """
        Add an item to the checkbox group component.

        Parameters
        ----------
        value:
            The value of the option, which will be returned on interaction response
        label:
            The label of the option, what the user sees
        description:
            The description of the option, additional text shown below the label
        default:
            Whether the option is selected by default
        """
        if len(self.options) >= 10:
            raise ValueError("Cannot have more than 10 options in a checkbox group component")

        self.options.append(ComponentOption(
            label=label,
            value=value,
            description=description,
            default=default
        ))

    def to_dict(self) -> dict:
        """ Returns a dict representation of the checkbox group component. """
        if len(self.custom_id) > 100:
            raise ValueError("custom_id must be 100 characters or less")
        if not (1 <= len(self.options) <= 10):
            raise ValueError("CheckboxGroupComponent must have between 1 and 10 options")

        if self.max_values is None:
            # If max_values is not set, set it to the number of options (up to 10)
            # self.add_item does not automatically update self.max_values
            self.max_values = min(len(self.options), 10)

        payload = {
            "type": int(self.type),
            "custom_id": self.custom_id,
            "options": [o.to_dict() for o in self.options],
        }

        if isinstance(self.min_values, int):
            if not (0 <= self.min_values <= 10):
                raise ValueError("min_values must be between 0 and 10")
            payload["min_values"] = self.min_values

        if isinstance(self.max_values, int):
            if not (1 <= self.max_values <= 10):
                raise ValueError("max_values must be between 1 and 10")
            payload["max_values"] = self.max_values

        if self.required:
            payload["required"] = self.required

        return payload


class CheckboxComponent(Item):
    """
    Represents a checkbox component in a modal.

    This is a single checkbox component, and returns a boolean value on interaction.
    """

    __slots__ = (
        "custom_id",
        "default",
        "description",
        "label",
    )

    def __init__(
        self,
        *,
        custom_id: str | None = None,
        label: str | None = None,
        description: str | None = None,
        default: bool = False
    ):
        super().__init__(type=ComponentType.checkbox)
        self.custom_id: str = custom_id or _garbage_id()
        """ The custom ID of the checkbox component. """

        self.label: str | None = label
        """ The label of the checkbox component. """

        self.description: str | None = description
        """ The description of the checkbox component. """

        self.default: bool = default
        """ Whether the checkbox is checked by default. """

    def to_dict(self) -> dict:
        """ Returns a dict representation of the checkbox component. """
        if len(self.custom_id) > 100:
            raise ValueError("custom_id must be 100 characters or less")

        return {
            "type": int(self.type),
            "custom_id": self.custom_id,
            "default": self.default
        }


class SeparatorComponent(Item):
    """ Represents a separator component in a message. """

    __slots__ = ("divider", "spacing",)

    def __init__(
        self,
        *,
        spacing: SeparatorSpacingType | None = None,
        divider: bool | None = None
    ):
        super().__init__(type=ComponentType.separator)

        self.spacing: SeparatorSpacingType | None = spacing
        """ The spacing type of the separator. """

        self.divider: bool | None = divider
        """ Whether the separator is a divider or not. """

    def __repr__(self) -> str:
        return f"<Separator spacing={self.spacing} divider={self.divider}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the separator. """
        payload: dict = {
            "type": int(self.type)
        }

        if self.spacing is not None:
            payload["spacing"] = int(self.spacing)
        if self.divider is not None:
            payload["divider"] = self.divider

        return payload


class InteractionStorage:
    """ Storage class for waiting for interactions in a command. """

    __slots__ = (
        "_call_after",
        "_event_wait",
        "_msg_cache",
        "_store_interaction",
        "_timeout",
        "_timeout_bool",
        "_timeout_expiry",
        "_users",
        "loop",
    )

    def __init__(self):
        self._event_wait = asyncio.Event()
        self._store_interaction: "Context | None" = None

        self.loop = asyncio.get_running_loop()
        self._call_after: Callable | None = None
        self._users: list["Snowflake"] = []
        self._timeout_bool = False
        self._timeout: float | None = None
        self._timeout_expiry: float | None = None
        self._msg_cache: str | int | None = None

    def __repr__(self) -> str:
        return (
            f"<InteractionStorage timeout={self._timeout} "
            f"msg={self._msg_cache}>"
        )

    def _update_event(self, value: bool) -> None:
        """
        Update the event waiter to either set or clear.

        Parameters
        ----------
        value:
            `True` means the event is set
            `False` means the event is cleared
        """
        if value is True:
            self._event_wait.set()
        elif value is False:
            self._event_wait.clear()

    async def _timeout_watcher(self) -> None:
        """ Watches for the timeout and calls on_timeout when it expires. """
        while True:
            if self._timeout is None:
                return None
            if self._timeout_expiry is None:
                return await self._dispatch_timeout()

            now = time.monotonic()
            if now >= self._timeout_expiry:
                return await self._dispatch_timeout()
            await asyncio.sleep(self._timeout_expiry - now)

    async def _dispatch_timeout(self) -> None:
        """ Dispatches the timeout event. """
        if self._event_wait.is_set():
            return

        asyncio.create_task(  # noqa: RUF006
            self.on_timeout(),
            name=f"discord.http/view-timeout-{int(time.time())}"
        )

    async def on_timeout(self) -> None:
        """ Called when the view times out. """
        self._timeout_bool = True
        self._update_event(True)

    def is_timeout(self) -> bool:
        """ Whether the view has timed out. """
        return self._timeout_bool

    async def callback(
        self,
        ctx: "Context"
    ) -> "BaseResponse | None":
        """ Called when the view is interacted with. """
        if not self._call_after:
            return None

        if (
            self._users and
            ctx.user.id not in [g.id for g in self._users]
        ):
            return ctx.response.send_message(
                "You are not allowed to interact with this message",
                ephemeral=True
            )

        self._store_interaction = ctx
        self._update_event(True)
        return await self._call_after(ctx)

    async def wait(
        self,
        ctx: "Context",
        *,
        call_after: Callable | None = None,
        users: list["Snowflake"] | None = None,
        original_response: bool = False,
        custom_id: str | int | None = None,
        timeout: float = 60,
    ) -> "Context | None":
        """
        Tell the command to wait for an interaction response.

        It will continue your code either if it was interacted with or timed out

        Parameters
        ----------
        ctx:
            Passing the current context of the bot
        call_after:
            Coroutine to call after the view is interacted with (will be ignored if timeout)
            The new context does follow with the call_after function, example:

            .. code-block:: python

                test = await view.wait(ctx, call_after=call_after, timeout=10)
                if not test:
                    return None  # Timed out

                async def call_after(ctx):
                    await ctx.response.edit_message(content="Hello world")

        users:
            List of users that are allowed to interact with the view
        original_response:
            Whether to force the original response to be used as the message target
        custom_id:
            Custom ID of the view, if not provided, it will use Context.id or Context.message
        timeout:
            How long it should take until the code simply times out

        Returns
        -------
            Returns the new context of the interaction, or `None` if timed out
        """
        users = users or []

        if not inspect.iscoroutinefunction(call_after):
            _log.warning("call_after is not a coroutine function, ignoring...")
            return None

        if users and isinstance(users, list):
            self._users = [g for g in users if getattr(g, "id", None)]

        self._call_after = call_after
        self._timeout = timeout
        self._timeout_expiry = time.monotonic() + timeout
        self.loop.create_task(
            self._timeout_watcher(),
            name=f"discord.http/view-timeout-watcher-{int(time.time())}"
        )

        self._update_event(False)

        # If user provides a custom_id
        if custom_id is not None:
            self._msg_cache = custom_id

        # If an interaction was made, and the initial Context.id is in message
        if (
            self._msg_cache is None and
            ctx.message is not None and
            ctx.message.interaction is not None
        ):
            self._msg_cache = ctx.message.interaction.id

        # If we're in the command init, use the initial Context.id
        if self._msg_cache is None:
            self._msg_cache = ctx.id

        # If for some reason msg_cache is still None
        # Or if user has spesifically asked for original_response
        if (
            self._msg_cache is None or
            original_response is True
        ):
            try:
                await asyncio.sleep(0.15)  # Make sure Discord has time to store the message
                msg = await ctx.original_response()
                self._msg_cache = msg.id
            except Exception as e:
                _log.warning(f"Failed to fetch origin message: {e}")
                return None

        ctx.bot._view_storage[self._msg_cache] = self
        await self._event_wait.wait()

        try:
            del ctx.bot._view_storage[self._msg_cache]
        except KeyError:
            pass

        if self.is_timeout():
            return None
        return self._store_interaction


class ThumbnailComponent(Item):
    """ Represents a thumbnail component in a message. """

    __slots__ = (
        "description",
        "spoiler",
        "url",
    )

    def __init__(
        self,
        url: Asset | AttachmentComponent | str,
        *,
        description: str | None = None,
        spoiler: bool = False
    ):
        super().__init__(type=ComponentType.thumbnail)

        self.url: Asset | AttachmentComponent | str = str(url)
        """ The URL of the thumbnail image. """

        self.description: str | None = description
        """ The description of the thumbnail. """

        self.spoiler: bool = spoiler
        """ Whether the thumbnail is a spoiler or not. """

    def __repr__(self) -> str:
        return f"<Thumbnail url='{self.url}'>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the thumbnail. """
        payload = {
            "type": int(self.type),
            "media": {
                "url": str(self.url)
            }
        }

        if self.description is not None:
            if len(self.description) > 1024:
                raise ValueError("description must be 1024 characters or less")
            payload["description"] = self.description
        if self.spoiler:
            payload["spoiler"] = bool(self.spoiler)

        return payload


class SectionComponent(Item):
    """ Represents a section component in a message. """

    __slots__ = (
        "accessory",
        "components",
    )

    def __init__(
        self,
        # This might change later if SectionComponent starts
        # accepting more than just TextDisplayComponent
        *components: TextDisplayComponent | str,
        accessory: Button | ThumbnailComponent | AttachmentComponent | Asset | File | str
    ):
        super().__init__(type=ComponentType.section)

        self.components: list[TextDisplayComponent | str] = list(components)
        """ The components contained within the section. """

        self.accessory: Button | ThumbnailComponent | AttachmentComponent | Asset | File | str = accessory
        """ The accessory component for the section. """

    def __repr__(self) -> str:
        return f"<SectionComponent components={self.components} accessory={self.accessory}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the section component. """
        if not (1 <= len(self.components) <= 3):
            raise ValueError("SectionComponent must have between 1 and 3 child components")

        comps: list[TextDisplayComponent] = []
        for g in self.components:
            if isinstance(g, str):
                comps.append(TextDisplayComponent(g))
            elif isinstance(g, TextDisplayComponent):
                comps.append(g)
            else:
                raise TypeError("Components must be TextDisplayComponent or str")

        payload = {
            "type": int(self.type),
            "components": [g.to_dict() for g in comps]
        }

        if isinstance(self.accessory, AttachmentComponent | Asset):
            payload["accessory"] = {
                "type": int(ComponentType.thumbnail),
                "media": {
                    "url": str(self.accessory.url)
                }
            }

        elif isinstance(self.accessory, str):
            payload["accessory"] = {
                "type": int(ComponentType.thumbnail),
                "media": {
                    "url": str(self.accessory)
                }
            }

        elif isinstance(self.accessory, File):
            payload["accessory"] = {
                "type": int(ComponentType.thumbnail),
                "media": {
                    "url": f"attachment://{self.accessory.filename}"
                }
            }

        else:
            payload["accessory"] = self.accessory.to_dict()

        return payload


class ActionRow(Item):
    """ Represents an action row component in a message, containing buttons, selects, and links. """

    __slots__ = (
        "_select_types",
        "components",
    )

    def __init__(
        self,
        *components: Button | Select | Link
    ):
        super().__init__(type=ComponentType.action_row)

        self.components: list[Button | Select | Link] = list(components)
        """ The components contained within the action row. """

        self._select_types: list[ComponentType] = [
            ComponentType.string_select,
            ComponentType.user_select,
            ComponentType.role_select,
            ComponentType.mentionable_select,
            ComponentType.channel_select
        ]

    def __repr__(self) -> str:
        return f"<ActionRow components={self.components}>"

    def add_item(
        self,
        item: Button | Select | Link
    ) -> None:
        """
        Add an item to the action row.

        Parameters
        ----------
        item:
            The item to add to the action row
        """
        self.components.append(item)

    def remove_items(
        self,
        *,
        label: str | None = None,
        custom_id: str | None = None
    ) -> int:
        """
        Remove items from the action row.

        Parameters
        ----------
        label:
            Label of the item
        custom_id:
            Custom ID of the item

        Returns
        -------
            Returns the amount of items removed
        """
        removed = 0

        for g in list(self.components):
            if (
                custom_id is not None and
                getattr(g, "custom_id", None) == custom_id
            ):
                self.components.remove(g)
                removed += 1

            elif (
                label is not None and
                isinstance(g, Button) and
                g.label == label
            ):
                self.components.remove(g)
                removed += 1

        return removed

    def to_dict(self) -> dict:
        """ Returns a dict representation of the action row. """
        for i in self.components:
            if i.type not in _components_action_row:
                raise ValueError(
                    f"Component type {i.type} is not supported inside an action row"
                )

        if len(self.components) <= 0:
            raise ValueError("Cannot have an action row with no components")
        if len(self.components) > 5:
            raise ValueError("Cannot have an action row with more than 5 components")
        if (
            len(self.components) > 1 and
            any(g.type in self._select_types for g in self.components)
        ):
            raise ValueError("Cannot have an action row with more than two items if any select menu is present")

        return {
            "type": int(self.type),
            "components": [g.to_dict() for g in self.components]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionRow":
        """ Returns an action row from a dict provided by Discord. """
        items = []

        cls_table = {
            2: Button,
            3: Select,
            5: UserSelect,
            6: RoleSelect,
            7: MentionableSelect,
            8: ChannelSelect,
            9: SectionComponent,
        }

        default_value_dropdowns = (
            UserSelect, RoleSelect, MentionableSelect, ChannelSelect,
        )

        for c in data.get("components", []):
            cls_ = cls_table[c.get("type", 2)]
            if c.get("url", None):
                cls_ = Link
                try:
                    del c["style"]
                except KeyError:
                    pass

            if c.get("type", None):
                del c["type"]
            if c.get("id", None):
                del c["id"]

            if cls_ in default_value_dropdowns:
                c["default_values"] = [
                    int(g["id"])
                    for g in c.get("default_values", [])
                ]

            items.append(cls_(**c))

        return ActionRow(*items)


class MediaGalleryItem:
    """ Represents an item in a media gallery. """

    __slots__ = (
        "description",
        "spoiler",
        "url",
    )

    def __init__(
        self,
        url: File | Asset | AttachmentComponent | str,
        *,
        description: str | None = None,
        spoiler: bool = False
    ):
        self.url: File | Asset | AttachmentComponent | str = str(url)
        """ The URL of the media item, can be a file, asset, attachment component, or a string URL. """

        self.description: str | None = description
        """ The description of the media item. """

        self.spoiler: bool = spoiler
        """ Whether the media item is marked as a spoiler. """

    def __repr__(self) -> str:
        return f"<MediaGalleryItem url={self.url}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the media gallery item. """
        if self.description and len(self.description) > 1024:
            raise ValueError("description must be 1024 characters or less")

        url = str(self.url)
        if isinstance(self.url, File):
            url = f"attachment://{self.url.filename}"

        return {
            "media": {
                "url": url
            },
            "description": self.description,
            "spoiler": self.spoiler
        }


class MediaGalleryComponent(Item):
    """ Represents a media gallery component in a message. """

    __slots__ = ("items",)

    def __init__(
        self,
        *items: MediaGalleryItem | File | Asset | str
    ):
        super().__init__(type=ComponentType.media_gallery)

        self.items: list[MediaGalleryItem | File | Asset | str] = list(items)
        """ The items contained within the media gallery. """

    def __repr__(self) -> str:
        return f"<MediaGalleryComponent items={self.items}>"

    def add_item(
        self,
        item: MediaGalleryItem | File | Asset | str
    ) -> None:
        """
        Add items to the media gallery.

        Parameters
        ----------
        item:
            Items to add to the media gallery
        """
        if len(self.items) >= 10:
            raise ValueError("Cannot have more than 10 items in a media gallery component")

        self.items.append(item)

    def to_dict(self) -> dict:
        """ Returns a dict representation of the media gallery component. """
        if not (1 <= len(self.items) <= 10):
            raise ValueError("MediaGalleryComponent must have between 1 and 10 items")

        payload: list[MediaGalleryItem] = []

        for g in self.items:
            if isinstance(g, File | Asset):
                payload.append(MediaGalleryItem(g))
            elif isinstance(g, str):
                payload.append(MediaGalleryItem(url=g))
            else:
                payload.append(g)

        return {
            "type": int(self.type),
            "items": [g.to_dict() for g in payload]
        }


class FileComponent(Item):
    """ Represents a file component in a message. """

    __slots__ = ("file", "spoiler",)

    def __init__(
        self,
        file: File | Asset | AttachmentComponent | str,
        *,
        spoiler: bool = False
    ):
        super().__init__(type=ComponentType.file)

        self.file: File | Asset | AttachmentComponent | str = file
        """ The file to be sent. """

        self.spoiler: bool = spoiler
        """ Whether the file is a spoiler. """

    def __repr__(self) -> str:
        return f"<FileComponent file={self.file}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the file component. """
        url = str(self.file)
        if isinstance(self.file, File):
            url = f"attachment://{self.file.filename}"

        return {
            "type": int(self.type),
            "file": {"url": url},
            "spoiler": self.spoiler
        }


class ContentInventoryEntry(LockedItem):
    """
    Represents a content inventory entry component in a message.

    This is used for the content inventory feature in Discord.
    """

    __slots__ = ()

    def __init__(self, *_: dict, **kwargs: dict):
        super().__init__(type=ComponentType.content_inventory_entry)
        self._data: dict = kwargs


class CheckpointComponent(LockedItem):
    """
    Represents a checkpoint component in a message.

    This is used for the checkpoint feature in Discord.
    """
    __slots__ = ()

    def __init__(self, *_: dict, **kwargs: dict):
        super().__init__(type=ComponentType.checkpoint)
        self._data: dict = kwargs


class ContainerComponent(Item):
    """ Represents a container component in a message. """

    __slots__ = (
        "colour",
        "items",
        "spoiler",
    )

    def __init__(
        self,
        *items: Item,
        colour: Colour | int | None = None,
        spoiler: bool | None = None
    ):
        super().__init__(type=ComponentType.container)

        self.items: list[Item] = list(items)
        """ The items contained within the container. """

        self.colour: Colour | int | None = colour
        """ The colour of the container, can be a Colour object or an integer. """

        self.spoiler: bool | None = spoiler
        """ Whether the container is marked as a spoiler. """

    def __repr__(self) -> str:
        return f"<ContainerComponent items={self.items}>"

    def add_item(self, item: Item) -> Item:
        """
        Add an item to the container component.

        Parameters
        ----------
        item:
            The item to add to the container component

        Returns
        -------
            Returns the item that was added
        """
        if len(self.items) >= 40:
            raise ValueError("Cannot have more than 40 items in a container component")

        if isinstance(item, ContainerComponent):
            raise ValueError("Cannot add container component to container component")

        self.items.append(item)
        return item

    def remove_index(
        self,
        index: int
    ) -> Item | None:
        """
        Remove an item from the container component.

        Parameters
        ----------
        index:
            The index of the item to remove

        Returns
        -------
            Returns whether the item was removed
        """
        try:
            return self.items.pop(index)
        except IndexError:
            return None

    def to_dict(self) -> dict:
        """ Returns a dict representation of the container component. """
        for i in self.items:
            if i.type not in _components_v2:
                raise ValueError(
                    f"Component type {i.type} is not supported inside a container"
                )

        if len(self.items) > 40:
            raise ValueError("Cannot have more than 40 items in container")

        payload = {
            "type": int(self.type),
            "components": [g.to_dict() for g in self.items]
        }

        if self.colour is not None:
            payload["accent_color"] = int(self.colour)
        if self.spoiler is not None:
            payload["spoiler"] = bool(self.spoiler)

        return payload


class View(InteractionStorage):
    """ Represents a view component in a message. """

    __slots__ = ("items",)

    def __init__(self, *items: Item):
        super().__init__()

        self.items: list[Item] = list(items)
        """ The items contained within the view, can be buttons, selects, links, etc. """

    def __repr__(self) -> str:
        return f"<View items={list(self.items)}>"

    def get_item(
        self,
        *,
        label: str | None = None,
        custom_id: str | None = None
    ) -> Item | None:
        """
        Get an item from the view that matches the parameters.

        Parameters
        ----------
        label:
            Label of the item
        custom_id:
            Custom ID of the item

        Returns
        -------
            Returns the item if found, otherwise `None`
        """
        for g in self.items:
            if (
                custom_id is not None and
                getattr(g, "custom_id", None) == custom_id
            ):
                return g
            if (
                label is not None and
                isinstance(g, Button) and
                g.label == label
            ):
                return g

        return None

    def add_item(self, item: Item) -> Item:
        """
        Add an item to the view.

        Parameters
        ----------
        item:
            The item to add to the view

        Returns
        -------
            Returns the added item
        """
        if len(self.items) >= 40:
            raise ValueError("Cannot have more than 40 items in a view")

        self.items.append(item)
        return item

    def remove_items(
        self,
        *,
        label: str | None = None,
        custom_id: str | None = None
    ) -> int:
        """
        Remove items from the view that match the parameters.

        Parameters
        ----------
        label:
            Label of the item
        custom_id:
            Custom ID of the item

        Returns
        -------
            Returns the amount of items removed
        """
        removed = 0

        for g in list(self.items):
            if (
                custom_id is not None and
                getattr(g, "custom_id", None) == custom_id
            ):
                self.items.remove(g)
                removed += 1

            elif (
                label is not None and
                isinstance(g, Button) and
                g.label == label
            ):
                self.items.remove(g)
                removed += 1

        return removed

    def to_dict(self) -> list[dict]:
        """ Returns a dict representation of the view. """
        for i in self.items:
            if i.type in _components_inaccessible:
                # Don't bother raising for inaccessible components.
                # They are sent on User side only.
                continue

            if i.type not in _components_root:
                raise ValueError(
                    f"Component type {i.type} is not supported as a stand-alone component. "
                    "Either use an action row, container or section component"
                )

        if len(self.items) > 40:
            raise ValueError("Cannot have a view with more than 40 items")

        return [g.to_dict() for g in self.items]

    @classmethod
    def from_dict(cls, *, state: "DiscordAPI", data: dict) -> "View":
        """ Returns a view from a dict provided by Discord. """
        items = []
        if not data.get("components"):
            return View(*[])

        cls_table = {
            1: ActionRow,
            2: Button,
            3: Select,
            5: UserSelect,
            6: RoleSelect,
            7: MentionableSelect,
            8: ChannelSelect,
            9: SectionComponent,
            10: TextDisplayComponent,
            11: ThumbnailComponent,
            12: MediaGalleryComponent,
            13: FileComponent,
            14: SeparatorComponent,
            16: ContentInventoryEntry,
            17: ContainerComponent,
            18: LabelComponent,
            20: CheckpointComponent
        }

        def _v2_resolver(c: dict) -> Item:
            raw_type = c.get("type", 1)
            cls = cls_table[raw_type]

            if c.get("type"):
                del c["type"]
            if c.get("id"):
                del c["id"]

            match raw_type:
                case int(ComponentType.file):
                    return FileComponent(
                        file=AttachmentComponent(state=state, data=c)
                    )

                case int(ComponentType.section):
                    if c["accessory"].get("type", None) == int(ComponentType.button):
                        if c["accessory"].get("type", None):
                            del c["accessory"]["type"]
                        if c["accessory"].get("id", None):
                            del c["accessory"]["id"]

                        acc_obj = Button(**c["accessory"])
                    else:
                        acc_obj = AttachmentComponent(state=state, data=c["accessory"])

                    texts = [
                        TextDisplayComponent(content=inner["content"])
                        for inner in c.get("components", [])
                    ]

                    return SectionComponent(*texts, accessory=acc_obj)

                case int(ComponentType.media_gallery):
                    medias = []
                    for m in c.get("items", []):
                        medias.append(
                            MediaGalleryItem(
                                url=AttachmentComponent(state=state, data=m),
                                description=m.get("description", None),
                                spoiler=m.get("spoiler", False)
                            )
                        )

                    return MediaGalleryComponent(*medias)

                case int(ComponentType.action_row):
                    return ActionRow.from_dict(c)

                case _:
                    return cls(**c)

        for comp in data.get("components", []):
            if ComponentType(comp.get("type", 1)) == ComponentType.container:
                sect_comps = []
                for c in comp.get("components", []):
                    sect_comps.append(_v2_resolver(c))
                kwargs = {}
                if comp.get("accent_color", None):
                    kwargs["colour"] = Colour(comp["accent_color"])
                if comp.get("spoiler", None):
                    kwargs["spoiler"] = bool(comp["spoiler"])

                items.append(ContainerComponent(*sect_comps, **kwargs))

            elif ComponentType(comp.get("type", 1)) == ComponentType.action_row:
                items.append(ActionRow.from_dict(comp))

            else:
                items.append(_v2_resolver(comp))

        return View(*items)


class LabelComponent(Item):
    """ Represents a label component in a modal. """

    __slots__ = (
        "component",
        "description",
        "label",
    )

    def __init__(
        self,
        *,
        label: str | None,
        description: str | None = None,
        component: (
            TextInputComponent | Select |
            FileUploadComponent | RadioComponent | CheckboxGroupComponent |
            CheckboxComponent
        )
    ):
        super().__init__(type=ComponentType.label)

        self.component = component
        """ The component contained within the label. """

        self.label: str | None = self.component.label or label
        """ The label of the component. """

        self.description: str | None = self.component.description or description
        """ The description of the component. """

    def __repr__(self) -> str:
        return f"<LabelComponent label='{self.label}' component={self.component}>"

    def to_dict(self) -> dict:
        """ Returns a dict representation of the label component. """
        if self.component.type not in _components_label:
            raise ValueError(
                f"Component type {self.component.type} is not supported as a label component."
            )

        if not isinstance(self.label, str):
            if self.label is None:
                raise TypeError(
                    f"{type(self.component)} is being used inside a LabelComponent, but has no label set. "
                    "(Provide one via the 'label' parameter)"
                )
            raise TypeError(f"Label for {type(self.component)} must be provided and be a string")
        if len(self.label) > 45:
            raise ValueError("Label text must be 45 characters or less")

        payload = {
            "type": int(self.type),
            "label": self.label,
            "component": self.component.to_dict()
        }

        if self.description is not None:
            if len(self.description) > 100:
                raise ValueError("Description text must be 100 characters or less")
            payload["description"] = self.description

        return payload


class Modal(InteractionStorage):
    """ Represents a modal component in a message. """

    __slots__ = (
        "custom_id",
        "items",
        "title",
    )

    def __init__(
        self,
        *,
        title: str,
        custom_id: str | None = None
    ):
        super().__init__()

        self.title: str = title
        """ The title of the modal. """

        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )
        """ The custom ID of the modal. """

        self.items: list[TextDisplayComponent | LabelComponent | FileUploadComponent] = []
        """ The items contained within the modal. """

    def add_item(
        self,
        component: (
            TextDisplayComponent | TextInputComponent | Select |
            FileUploadComponent | RadioComponent | CheckboxGroupComponent |
            CheckboxComponent
        ),
        *,
        label: str | None = None,
        description: str | None = None,
    ) -> LabelComponent | TextDisplayComponent:
        """
        Add an item to the modal.

        Parameters
        ----------
        component:
            The component to add to the modal.
        label:
            The label of the component, overwrites component.label
        description:
            The description of the component, overwrites component.description, by default None

        Returns
        -------
            The created label component

        Raises
        ------
        TypeError
            If the component is not a TextInputComponent or Select
        """
        if len(self.items) >= 5:
            raise ValueError("Cannot have more than 5 items in a modal")

        if isinstance(component, TextDisplayComponent):
            # This one is allowed as top-level
            self.items.append(component)
            return component

        item = LabelComponent(
            component=component,
            label=label,
            description=description,
        )

        self.items.append(item)
        return item

    def to_dict(self) -> dict:
        """ Returns a dict representation of the modal. """
        if len(self.items) > 5:
            raise ValueError("Modal can only have 5 items at most")

        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": [g.to_dict() for g in self.items]
        }
