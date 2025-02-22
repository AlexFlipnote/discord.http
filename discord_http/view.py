import asyncio
import inspect
import logging
import secrets
import time

from typing import TYPE_CHECKING, Callable

from .asset import Asset
from .colour import Colour
from .emoji import EmojiParser
from .enums import (
    ButtonStyles, ComponentType, TextStyles,
    ChannelType, SeparatorSpacingType
)

if TYPE_CHECKING:
    from . import Snowflake
    from .channel import BaseChannel
    from .context import Context
    from .member import Member
    from .response import BaseResponse
    from .role import Role

_log = logging.getLogger(__name__)

_components_v1 = (
    ComponentType.action_row,
    ComponentType.button,
    ComponentType.string_select,
    ComponentType.text_input,
    ComponentType.user_select,
    ComponentType.role_select,
    ComponentType.mentionable_select,
    ComponentType.channel_select,
    ComponentType.container,
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

__all__ = (
    "ActionRow",
    "Button",
    "ChannelSelect",
    "ContainerComponent",
    "FileComponent",
    "Item",
    "Link",
    "MediaGalleryComponent",
    "MediaGalleryItem",
    "MentionableSelect",
    "Modal",
    "ModalItem",
    "Premium",
    "RoleSelect",
    "SectionComponent",
    "Select",
    "SeparatorComponent",
    "TextDisplayComponent",
    "ThumbnailComponent",
    "UserSelect",
    "View",
)


def _garbage_id() -> str:
    """ `str`: Returns a random ID to satisfy Discord API """
    return secrets.token_hex(16)


class Item:
    def __init__(self, *, type: int, row: int | None = None):
        self.row: int | None = row
        self.type: int = type

    def __repr__(self) -> str:
        return f"<Item type={self.type} row={self.row}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the item """
        raise NotImplementedError("to_dict not implemented")


class ModalItem:
    def __init__(
        self,
        *,
        label: str,
        custom_id: str | None = None,
        style: TextStyles | None = None,
        placeholder: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        default: str | None = None,
        required: bool = True,
    ):
        self.label: str = label
        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )
        self.style: int = int(style or TextStyles.short)

        self.placeholder: str | None = placeholder
        self.min_length: int | None = min_length
        self.max_length: int | None = max_length
        self.default: str | None = default
        self.required: bool = required

        if (
            isinstance(self.min_length, int) and
            self.min_length not in range(0, 4001)
        ):
            raise ValueError("min_length must be between 0 and 4,000")

        if (
            isinstance(self.max_length, int) and
            self.max_length not in range(1, 4001)
        ):
            raise ValueError("max_length must be between 1 and 4,000")

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the modal item """
        payload = {
            "type": 4,
            "label": self.label,
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
    def __init__(
        self,
        *,
        label: str | None = None,
        style: ButtonStyles | str | int = ButtonStyles.primary,
        disabled: bool = False,
        row: int | None = None,
        custom_id: str | None = None,
        sku_id: "Snowflake | int | None" = None,
        emoji: str | dict | None = None,
        url: str | None = None
    ):
        super().__init__(type=int(ComponentType.button), row=row)

        self.label: str | None = label
        self.disabled: bool = disabled
        self.url: str | None = url
        self.emoji: str | dict | None = emoji
        self.sku_id: "Snowflake | int | None" = sku_id
        self.style: ButtonStyles | str | int = style
        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )

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

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the button """
        payload = {
            "type": self.type,
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
            payload["label"] = self.label

        if self.custom_id:
            payload["custom_id"] = self.custom_id

        if self.url:
            payload["url"] = self.url

        return payload


class Premium(Button):
    def __init__(
        self,
        *,
        sku_id: "Snowflake | int",
        row: int | None = None,
    ):
        """
        Button alias for the premium SKU style

        Parameters
        ----------
        sku_id: `Union[Snowflake, int]`
            SKU ID of the premium button
        row: `Optional[int]`
            Row of the button
        """
        super().__init__(
            sku_id=sku_id,
            style=ButtonStyles.premium,
            row=row
        )

    def __repr__(self) -> str:
        return f"<Premium sku_id={self.sku_id}>"


class Link(Button):
    def __init__(
        self,
        *,
        url: str,
        label: str | None = None,
        row: int | None = None,
        emoji: str | None = None,
        disabled: bool = False
    ):
        """
        Button alias for the link style

        Parameters
        ----------
        url: `str`
            URL to open when the button is clicked
        label: `Optional[str]`
            Label of the button
        row: `Optional[int]`
            Row of the button
        emoji: `Optional[str]`
            Emoji shown on the left side of the button
        """
        super().__init__(
            url=url,
            label=label,
            emoji=emoji,
            style=ButtonStyles.link,
            row=row,
            disabled=disabled
        )

        # Link buttons use url instead of custom_id
        self.custom_id: str | None = None

    def __repr__(self) -> str:
        return f"<Link url='{self.url}'>"


class Select(Item):
    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        row: int | None = None,
        disabled: bool = False,
        options: list[dict] | None = None,
        _type: int | None = None
    ):
        super().__init__(
            row=row,
            type=_type or int(ComponentType.string_select)
        )

        self.placeholder: str | None = placeholder
        self.min_values: int | None = min_values
        self.max_values: int | None = max_values
        self.disabled: bool = disabled
        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )

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
        Add an item to the select menu

        Parameters
        ----------
        label: `str`
            Label of the item
        value: `str`
            The value of the item, which will be shown on interaction response
        description: `Optional[str]`
            Description of the item
        emoji: `Optional[str]`
            Emoji shown on the left side of the item
        default: `bool`
            Whether the item is selected by default

        Raises
        ------
        `ValueError`
            If there are more than 25 options
        """
        if len(self._options) > 25:
            raise ValueError("Cannot have more than 25 options")

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
        """ `dict`: Returns a dict representation of the select menu """
        payload = {
            "type": self.type,
            "custom_id": self.custom_id,
            "min_values": self.min_values,
            "max_values": self.max_values,
            "disabled": self.disabled,
        }

        if self.placeholder is not None:
            payload["placeholder"] = self.placeholder
        if self._default_values:
            payload["default_values"] = self._default_values
        if self._options:
            payload["options"] = self._options

        return payload


class UserSelect(Select):
    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["Member | int"] | None = None,
        row: int | None = None,
        disabled: bool = False
    ):
        super().__init__(
            row=row,
            _type=int(ComponentType.user_select),
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled
        )

        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "user"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<UserSelect custom_id='{self.custom_id}'>"


class RoleSelect(Select):
    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["Role | int"] | None = None,
        row: int | None = None,
        disabled: bool = False
    ):
        super().__init__(
            row=row,
            _type=int(ComponentType.role_select),
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled
        )

        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "role"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<RoleSelect custom_id='{self.custom_id}'>"


class MentionableSelect(Select):
    def __init__(
        self,
        *,
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["Member | Role | int"] | None = None,
        row: int | None = None,
        disabled: bool = False
    ):
        super().__init__(
            row=row,
            _type=int(ComponentType.mentionable_select),
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled
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
    def __init__(
        self,
        *channels: "ChannelType | BaseChannel",
        placeholder: str | None = None,
        custom_id: str | None = None,
        min_values: int | None = 1,
        max_values: int | None = 1,
        default_values: list["BaseChannel | int"] | None = None,
        row: int | None = None,
        disabled: bool = False
    ):
        super().__init__(
            row=row,
            _type=int(ComponentType.channel_select),
            placeholder=placeholder,
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled
        )

        self._channel_types = []

        for c in channels:
            if isinstance(c, ChannelType):
                self._channel_types.append(int(c))
            else:
                self._channel_types.append(int(c.type))

        if isinstance(default_values, list):
            self._default_values = [
                {"id": str(int(g)), "type": "channel"}
                for g in default_values
            ]

    def __repr__(self) -> str:
        return f"<ChannelSelect custom_id='{self.custom_id}'>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the channel select menu """
        payload = super().to_dict()
        payload["channel_types"] = self._channel_types
        return payload


class TextDisplayComponent(Item):
    def __init__(
        self,
        *,
        content: str
    ):
        super().__init__(type=int(ComponentType.text_display))
        self.content = content

    def __repr__(self) -> str:
        return f"<TextDisplay content='{self.content}'>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the text display """
        return {
            "type": self.type,
            "content": self.content
        }


class SeparatorComponent(Item):
    def __init__(
        self,
        *,
        spacing: SeparatorSpacingType | None = None,
        divider: bool | None = None
    ):
        super().__init__(type=int(ComponentType.separator))

        self.spacing: SeparatorSpacingType | None = spacing
        self.divider: bool | None = divider

    def __repr__(self) -> str:
        return f"<Separator spacing={self.spacing} divider={self.divider}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the separator """
        payload = {
            "type": self.type
        }

        if self.spacing is not None:
            payload["spacing"] = int(self.spacing)
        if self.divider is not None:
            payload["divider"] = self.divider

        return payload


class InteractionStorage:
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
        Update the event waiter to either set or clear

        Parameters
        ----------
        value: `bool`
            `True` means the event is set
            `False` means the event is cleared
        """
        if value is True:
            self._event_wait.set()
        elif value is False:
            self._event_wait.clear()

    async def _timeout_watcher(self) -> None:
        """ Watches for the timeout and calls on_timeout when it expires """
        while True:
            if self._timeout is None:
                return
            if self._timeout_expiry is None:
                return await self._dispatch_timeout()

            now = time.monotonic()
            if now >= self._timeout_expiry:
                return await self._dispatch_timeout()
            await asyncio.sleep(self._timeout_expiry - now)

    async def _dispatch_timeout(self) -> None:
        """ Dispatches the timeout event """
        if self._event_wait.is_set():
            return

        asyncio.create_task(
            self.on_timeout(),
            name=f"discordhttp-timeout-{int(time.time())}"
        )

    async def on_timeout(self) -> None:
        """ Called when the view times out """
        self._timeout_bool = True
        self._update_event(True)

    def is_timeout(self) -> bool:
        """ `bool`: Whether the view has timed out """
        return self._timeout_bool

    async def callback(
        self,
        ctx: "Context"
    ) -> "BaseResponse | None":
        """ Called when the view is interacted with """
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
        call_after: Callable,
        users: list["Snowflake"] | None = [],
        original_response: bool = False,
        custom_id: str | int | None = None,
        timeout: float = 60,
    ) -> "Context | None":
        """
        Tell the command to wait for an interaction response
        It will continue your code either if it was interacted with or timed out

        Parameters
        ----------
        ctx: `Context`
            Passing the current context of the bot
        call_after: `Coroutine`
            Coroutine to call after the view is interacted with (will be ignored if timeout)
            The new context does follow with the call_after function, example:

            .. code-block:: python

                test = await view.wait(ctx, call_after=call_after, timeout=10)
                if not test:
                    return None  # Timed out

                async def call_after(ctx):
                    await ctx.response.edit_message(content="Hello world")

        users: `Optional[list[Snowflake]]`
            List of users that are allowed to interact with the view
        original_response: `bool`
            Whether to force the original response to be used as the message target
        custom_id: `str | None`
            Custom ID of the view, if not provided, it will use Context.id or Context.message
        timeout: `float`
            How long it should take until the code simply times out

        Returns
        -------
        `Optional[Context]`
            Returns the new context of the interaction, or `None` if timed out
        """
        if not inspect.iscoroutinefunction(call_after):
            _log.warning("call_after is not a coroutine function, ignoring...")
            return None

        if users and isinstance(users, list):
            self._users = [g for g in users if getattr(g, "id", None)]

        self._call_after = call_after
        self._timeout = timeout
        self._timeout_expiry = time.monotonic() + timeout
        self.loop.create_task(self._timeout_watcher())

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
                _msg = await ctx.original_response()
                self._msg_cache = _msg.id
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
    def __init__(
        self,
        url: Asset | str,
        *,
        description: str | None = None,
        spoiler: bool = False
    ):
        super().__init__(type=int(ComponentType.thumbnail))

        self.url: str = str(url)
        self.description: str | None = description
        self.spoiler: bool = spoiler

    def __repr__(self) -> str:
        return f"<Thumbnail url='{self.url}'>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the thumbnail """
        payload = {
            "type": self.type,
            "media": {
                "url": str(self.url)
            }
        }

        if self.description is not None:
            payload["description"] = self.description
        if self.spoiler:
            payload["spoiler"] = bool(self.spoiler)

        return payload


class SectionComponent(Item):
    def __init__(
        self,
        *,
        components: list[TextDisplayComponent],
        accessory: Button | ThumbnailComponent
    ):
        super().__init__(type=int(ComponentType.section))

        self.components: list[TextDisplayComponent] = components
        self.accessory: Button | ThumbnailComponent = accessory

        # Just for backwards compatibility
        self.custom_id: None = None

    def __repr__(self) -> str:
        return f"<SectionComponent components={self.components} accessory={self.accessory}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the section component """
        return {
            "type": self.type,
            "components": [g.to_dict() for g in self.components],
            "accessory": self.accessory.to_dict()
        }


class ActionRow(Item):
    def __init__(
        self,
        *components: Button | Select | Link
    ):
        super().__init__(type=int(ComponentType.action_row))

        self.components = components

    def __repr__(self) -> str:
        return f"<ActionRow components={self.components}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the action row """
        return {
            "type": self.type,
            "components": [g.to_dict() for g in self.components]
        }


class MediaGalleryItem:
    def __init__(
        self,
        url: Asset | str,
        *,
        description: str | None = None,
        spoiler: bool = False
    ):
        self.url: Asset | str = str(url)
        self.description: str | None = description
        self.spoiler: bool = spoiler

    def __repr__(self) -> str:
        return f"<MediaGalleryItem url={self.url}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the media gallery item """
        return {
            "media": {
                "url": str(self.url)
            },
            "description": self.description,
            "spoiler": self.spoiler
        }


class MediaGalleryComponent(Item):
    def __init__(
        self,
        *items: MediaGalleryItem
    ):
        super().__init__(type=int(ComponentType.media_gallery))
        self.items = items

    def __repr__(self) -> str:
        return f"<MediaGalleryComponent items={self.items}>"

    def add_item(
        self,
        item: MediaGalleryItem
    ) -> None:
        """
        Add items to the media gallery

        Parameters
        ----------
        items: `MediaGalleryItem`
            Items to add to the media gallery
        """
        self.items = self.items + (item,)

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the media gallery component """
        return {
            "type": self.type,
            "items": [g.to_dict() for g in self.items]
        }


class FileComponent(Item):
    def __init__(
        self,
        file: Asset | str,
        *,
        spoiler: bool = False
    ):
        super().__init__(type=int(ComponentType.file))
        self.file: Asset | str = file
        self.spoiler: bool = spoiler

    def __repr__(self) -> str:
        return f"<FileComponent file={self.file}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the file component """
        return {
            "type": self.type,
            "file": {
                "url": str(self.file)
            },
            "spoiler": self.spoiler
        }


class ContainerComponent:
    def __init__(
        self,
        *items: Item,
        colour: Colour | int | None = None,
        spoiler: bool | None = None,
        row: int | None = None
    ):
        for i in items:
            if i.type not in _components_v2:
                raise ValueError(
                    f"Component type {i.type} is not supported inside a container"
                )

        self.items = items
        self.colour: Colour | int | None = colour
        self.spoiler: bool | None = spoiler
        self.row: int | None = row
        self.type: int = int(ComponentType.container)

        if len(items) <= 0:
            raise ValueError("Cannot have no items in container")
        if len(items) > 5:
            raise ValueError("Cannot have more than 5 items in container")

    def __repr__(self) -> str:
        return f"<ContainerComponent items={self.items}>"

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the container component """
        payload = {
            "type": int(ComponentType.container),
            "components": [g.to_dict() for g in self.items]
        }

        if self.colour is not None:
            payload["accent_color"] = int(self.colour)
        if self.spoiler is not None:
            payload["spoiler"] = bool(self.spoiler)

        return payload


class View(InteractionStorage):
    def __init__(
        self,
        *items: Button | Select | Link | SectionComponent
    ):
        super().__init__()

        for i in items:
            if i.type not in _components_v1:
                raise ValueError(
                    f"Component type {i.type} is not supported on a standard view"
                )

        self.items = items

        self._select_types: list[int] = [
            int(ComponentType.string_select),
            int(ComponentType.user_select),
            int(ComponentType.role_select),
            int(ComponentType.mentionable_select),
            int(ComponentType.channel_select)
        ]

    def __repr__(self) -> str:
        return f"<View items={list(self.items)}>"

    def get_item(
        self,
        *,
        label: str | None = None,
        custom_id: str | None = None
    ) -> Button | Select | Link | SectionComponent | None:
        """
        Get an item from the view that matches the parameters

        Parameters
        ----------
        label: `Optional[str]`
            Label of the item
        custom_id: `Optional[str]`
            Custom ID of the item

        Returns
        -------
        `Optional[Union[Button, Select, Link]]`
            Returns the item if found, otherwise `None`
        """
        for g in self.items:
            if (
                custom_id is not None and
                g.custom_id == custom_id
            ):
                return g
            if (
                label is not None and
                isinstance(g, Button) and
                g.label == label
            ):
                return g

        return None

    def add_item(
        self,
        item: Button | Select | Link
    ) -> Button | Select | Link:
        """
        Add an item to the view

        Parameters
        ----------
        item: `Union[Button, Select, Link]`
            The item to add to the view

        Returns
        -------
        `Union[Button, Select, Link]`
            Returns the added item
        """
        self.items = self.items + (item,)
        return item

    def remove_items(
        self,
        *,
        label: str | None = None,
        custom_id: str | None = None
    ) -> int:
        """
        Remove items from the view that match the parameters

        Parameters
        ----------
        label: `Optional[str]`
            Label of the item
        custom_id: `Optional[str]`
            Custom ID of the item

        Returns
        -------
        `int`
            Returns the amount of items removed
        """
        temp = []
        removed = 0

        for g in self.items:
            if (
                custom_id is not None and
                g.custom_id == custom_id
            ):
                removed += 1
                continue
            if (
                label is not None and
                isinstance(g, Button) and
                g.label == label
            ):
                removed += 1
                continue

            temp.append(g)

        self.items = tuple(temp)

        return removed

    def to_dict(self) -> list[dict]:
        """ `list[dict]`: Returns a dict representation of the view """
        components: list[list[Item | ContainerComponent]] = [[] for _ in range(5)]

        for g in self.items:
            if g.row is None:
                g.row = next((
                    i for i, _ in enumerate(components)
                    if len(components[i]) < 5 and
                    not any(
                        g.type in self._select_types
                        for g in components[i]
                    )
                ), 0)

            if isinstance(g, Select):
                if len(components[g.row]) >= 1:
                    raise ValueError(
                        "Cannot add select menu to row with other view items"
                    )
            elif isinstance(g, ContainerComponent):
                if len(components[g.row]) >= 1:
                    raise ValueError(
                        "Cannot add section component to row with other view items"
                    )
            else:
                if any(isinstance(i, Select) for i in components[g.row]):
                    raise ValueError(
                        "Cannot add component to row with select menu"
                    )

            if len(components[g.row]) >= 5:
                raise ValueError(
                    f"Cannot have more than 5 items in row {g.row}"
                )

            components[g.row].append(g)

        payload = []

        for c in components:
            if len(c) <= 0:
                continue

            if len(c) == 1 and isinstance(c[0], ContainerComponent):
                payload.append(c[0].to_dict())

            else:
                payload.append({
                    "type": int(ComponentType.action_row),
                    "components": [g.to_dict() for g in c]
                })

        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "View":
        """ `View`: Returns a view from a dict provided by Discord """
        items = []
        if not data.get("components", None):
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
            17: ContainerComponent,
        }

        for i, comp in enumerate(data.get("components", [])):
            if comp.get("type", 1) == int(ComponentType.container):

                # TODO: Support backwards compatibility for v2 containers
                continue

                _sect_comps = []
                for c in comp.get("components", []):
                    cls = cls_table[c.get("type", 2)]

                    if c.get("type", None):
                        del c["type"]
                    if c.get("id", None):
                        del c["id"]

                    _sect_comps.append(cls(**c))

                items.append(ContainerComponent(*_sect_comps, row=i))

            else:
                for c in comp.get("components", []):
                    cls = cls_table[c.get("type", 2)]
                    if c.get("url", None):
                        cls = Link
                        try:
                            del c["style"]
                        except KeyError:
                            pass

                    if c.get("type", None):
                        del c["type"]
                    if c.get("id", None):
                        del c["id"]

                    items.append(cls(row=i, **c))

        return View(*items)


class Modal(InteractionStorage):
    def __init__(
        self,
        *,
        title: str,
        custom_id: str | None = None
    ):
        super().__init__()

        self.title: str = title
        self.custom_id: str = (
            str(custom_id)
            if custom_id else _garbage_id()
        )

        self.items: list[ModalItem] = []

    def add_item(
        self,
        *,
        label: str,
        custom_id: str | None = None,
        style: TextStyles | None = None,
        placeholder: str | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        default: str | None = None,
        required: bool = True,
    ) -> ModalItem:
        """
        Add an item to the modal

        Parameters
        ----------
        label: `str`
            Label of the item
        custom_id: `Optional[str]`
            Custom ID of the item
        style: `Optional[TextStyles]`
            Style of the item
        placeholder: `Optional[str]`
            Placeholder of the item
        min_length: `Optional[int]`
            Minimum length of the item
        max_length: `Optional[int]`
            Maximum length of the item
        default: `Optional[str]`
            Default value of the item
        required: `bool`
            Whether the item is required

        Returns
        -------
        `ModalItem`
            Returns the created modal item from the items list
        """
        item = ModalItem(
            label=label,
            custom_id=custom_id,
            style=style,
            placeholder=placeholder,
            min_length=min_length,
            max_length=max_length,
            default=default,
            required=required
        )

        self.items.append(item)
        return item

    def to_dict(self) -> dict:
        """ `dict`: Returns a dict representation of the modal """
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": [
                {"type": 1, "components": [g.to_dict()]}
                for g in self.items
            ]
        }
