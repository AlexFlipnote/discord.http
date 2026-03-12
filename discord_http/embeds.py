import sys

from dataclasses import dataclass
from datetime import datetime
from typing import Self, Literal, cast

from .asset import Asset
from .colour import Colour

__all__ = (
    "Embed",
)

EmbedTypes = Literal["rich", "image", "video", "gifv", "article", "link", "poll_result"]


@dataclass(slots=True)
class EmbedAuthor:
    name: str
    url: str | None = None
    icon_url: str | None = None

    def to_dict(self) -> dict:
        data = {"name": self.name}
        if self.url:
            data["url"] = self.url
        if self.icon_url:
            data["icon_url"] = self.icon_url
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            name=data["name"],
            url=data.get("url"),
            icon_url=data.get("icon_url")
        )


@dataclass(slots=True)
class EmbedFooter:
    text: str | None
    icon_url: str | None

    def to_dict(self) -> dict:
        data = {}
        if self.text is not None:
            data["text"] = self.text
        if self.icon_url is not None:
            data["icon_url"] = self.icon_url
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            text=data.get("text"),
            icon_url=data.get("icon_url")
        )


@dataclass(slots=True)
class EmbedField:
    name: str
    value: str
    inline: bool = True

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "inline": self.inline}

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            name=data["name"],
            value=data["value"],
            inline=data.get("inline", True)
        )


@dataclass(slots=True)
class EmbedMedia:
    url: str

    def to_dict(self) -> dict:
        return {"url": self.url}

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(url=data["url"])


class Embed:
    """ Represents a Discord embed. """
    __slots__ = (
        "author",
        "colour",
        "description",
        "fields",
        "footer",
        "image",
        "thumbnail",
        "timestamp",
        "title",
        "type",
        "url",
    )

    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        colour: Colour | int | None = None,
        color: Colour | int | None = None,
        url: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.colour: Colour | int | None = None
        """ The colour of the embed, if any. """

        if colour is not None:
            self.colour = Colour(int(colour))
        elif color is not None:
            self.colour = Colour(int(color))

        self.title: str | None = title
        """ The title of the embed, if any. """

        self.description: str | None = description
        """ The description of the embed, if any. """

        self.timestamp: datetime | None = timestamp
        """ The timestamp of the embed, if any. """

        self.url: str | None = url
        """ The URL of the embed, if any. """

        self.type: EmbedTypes = "rich"
        """ The type of the embed, which can be "rich", "image", "video", "gifv", "article", "link", or "poll_result". Defaults to "rich". """

        self.footer: EmbedFooter | None = None
        """ The footer of the embed, if any. """

        self.author: EmbedAuthor | None = None
        """ The author of the embed, if any. """

        self.image: EmbedMedia | None = None
        """ The image of the embed, if any. """

        self.thumbnail: EmbedMedia | None = None
        """ The thumbnail of the embed, if any. """

        self.fields: list[EmbedField] = []
        """ The fields of the embed, if any. """

        if self.title is not None:
            self.title = str(self.title)

        if self.description is not None:
            self.description = str(self.description)

        if self.url is not None:
            self.url = str(self.url)

        if timestamp is not None:
            self.timestamp = timestamp

    def __repr__(self) -> str:
        return f"<Embed title={self.title} colour={self.colour}>"

    def __len__(self) -> int:
        total = len(self.title or "") + len(self.description or "")
        if self.footer:
            total += len(self.footer.text or "")
        if self.author:
            total += len(self.author.name or "")
        for field in self.fields:
            total += len(field.name) + len(field.value)
        return total

    def copy(self) -> Self:
        """ Returns a copy of the embed. """
        return self.__class__.from_dict(self.to_dict())

    def set_colour(
        self,
        value: Colour | int | None
    ) -> Self:
        """
        Set the colour of the embed.

        Parameters
        ----------
        value:
            The colour to set the embed to.
            If `None`, the colour will be removed

        Returns
        -------
            Returns the embed you are editing
        """
        self.colour = Colour(int(value)) if value else None
        return self

    def remove_colour(self) -> Self:
        """
        Remove the colour from the embed.

        Returns
        -------
            Returns the embed you are editing
        """
        self.colour = None
        return self

    def set_footer(
        self,
        *,
        text: str | None = None,
        icon_url: Asset | str | None = None
    ) -> Self:
        """
        Set the footer of the embed.

        Parameters
        ----------
        text:
            The text of the footer
        icon_url:
            Icon URL of the footer

        Returns
        -------
            Returns the embed you are editing
        """
        if not any((text, icon_url)):
            self.footer = None
            return self

        self.footer = EmbedFooter(
            text=str(text) if text else None,
            icon_url=str(icon_url) if icon_url else None
        )

        return self

    def remove_footer(self) -> Self:
        """
        Remove the footer from the embed.

        Returns
        -------
            Returns the embed you are editing
        """
        self.footer = None
        return self

    def set_author(
        self,
        *,
        name: str,
        url: str | None = None,
        icon_url: Asset | str | None = None
    ) -> Self:
        """
        Set the author of the embed.

        Parameters
        ----------
        name:
            The name of the author
        url:
            The URL which the author name will link to
        icon_url:
            The icon URL of the author

        Returns
        -------
            Returns the embed you are editing
        """
        self.author = EmbedAuthor(
            name=str(name),
            url=str(url) if url else None,
            icon_url=str(icon_url) if icon_url else None
        )

        return self

    def remove_author(self) -> Self:
        """
        Remove the author from the embed.

        Returns
        -------
            Returns the embed you are editing
        """
        self.author = None
        return self

    def set_image(
        self,
        *,
        url: Asset | str | None = None
    ) -> Self:
        """
        Set the image of the embed.

        Parameters
        ----------
        url:
            The URL of the image

        Returns
        -------
            Returns the embed you are editing
        """
        self.image = EmbedMedia(url=str(url)) if url else None
        return self

    def remove_image(self) -> Self:
        """
        Remove the image from the embed.

        Returns
        -------
            Returns the embed you are editing
        """
        self.image = None
        return self

    def set_thumbnail(
        self,
        *,
        url: Asset | str | None = None
    ) -> Self:
        """
        Set the thumbnail of the embed.

        Parameters
        ----------
        url:
            The URL of the thumbnail

        Returns
        -------
            Returns the embed you are editing
        """
        self.thumbnail = EmbedMedia(url=str(url)) if url else None
        return self

    def remove_thumbnail(self) -> Self:
        """
        Remove the thumbnail from the embed.

        Returns
        -------
            Returns the embed you are editing
        """
        self.thumbnail = None
        return self

    def add_field(
        self,
        *,
        name: str,
        value: str,
        inline: bool = True
    ) -> Self:
        """
        Add a field to the embed.

        Parameters
        ----------
        name:
            Title of the field
        value:
            Description of the field
        inline:
            Whether the field is inline or not

        Returns
        -------
            Returns the embed you are editing
        """
        if len(self.fields) >= 25:
            raise ValueError("Embeds cannot have more than 25 fields.")

        self.fields.append(EmbedField(
            name=str(name),
            value=str(value),
            inline=inline
        ))

        return self

    def remove_field(self, index: int) -> Self:
        """
        Remove a field from the embed.

        Parameters
        ----------
        index:
            The index of the field to remove

        Returns
        -------
            Returns the embed you are editing
        """
        try:
            del self.fields[index]
        except IndexError:
            pass

        return self

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Create an embed from a dictionary.

        Parameters
        ----------
        data:
            The dictionary to create the embed from

        Returns
        -------
            The embed created from the dictionary
        """
        self = cls.__new__(cls)

        self.title = data.get("title")
        self.description = data.get("description")
        self.timestamp = data.get("timestamp")
        self.url = data.get("url")
        self.type = cast("EmbedTypes", sys.intern(data.get("type", "rich")))

        self.colour = Colour(data["color"]) if data.get("color") is not None else None

        self.footer = EmbedFooter.from_dict(data["footer"]) if data.get("footer") else None
        self.author = EmbedAuthor.from_dict(data["author"]) if data.get("author") else None
        self.image = EmbedMedia.from_dict(data["image"]) if data.get("image") else None
        self.thumbnail = EmbedMedia.from_dict(data["thumbnail"]) if data.get("thumbnail") else None

        self.fields = [
            EmbedField.from_dict(f)
            for f in data.get("fields", [])
        ]

        return self

    def to_dict(self) -> dict:
        """ The embed as a dictionary. """
        embed = {}

        if self.title:
            embed["title"] = self.title
        if self.description:
            embed["description"] = self.description
        if self.url:
            embed["url"] = self.url
        if self.author:
            embed["author"] = self.author.to_dict()
        if self.colour:
            embed["color"] = int(self.colour)
        if self.footer:
            embed["footer"] = self.footer.to_dict()
        if self.image:
            embed["image"] = self.image.to_dict()
        if self.thumbnail:
            embed["thumbnail"] = self.thumbnail.to_dict()
        if self.fields:
            embed["fields"] = [field.to_dict() for field in self.fields]
        if self.timestamp and isinstance(self.timestamp, datetime):
            if self.timestamp.tzinfo is None:
                self.timestamp = self.timestamp.astimezone()
            embed["timestamp"] = self.timestamp.isoformat()

        return embed
