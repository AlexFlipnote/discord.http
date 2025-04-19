from datetime import datetime
from typing import Self, Literal

from .asset import Asset
from .colour import Colour

__all__ = (
    "Embed",
)

EmbedTypes = Literal["rich", "image", "video", "gifv", "article", "link", "poll_result"]


class Embed:
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

        if colour is not None:
            self.colour = Colour(int(colour))
        elif color is not None:
            self.colour = Colour(int(color))

        self.title: str | None = title
        self.description: str | None = description
        self.timestamp: datetime | None = timestamp
        self.url: str | None = url
        self.type: EmbedTypes = "rich"

        self.footer: dict = {}
        self.image: dict = {}
        self.thumbnail: dict = {}
        self.author: dict = {}
        self.fields: list[dict] = []

        if self.title is not None:
            self.title = str(self.title)

        if self.description is not None:
            self.description = str(self.description)

        if timestamp is not None:
            self.timestamp = timestamp

    def __repr__(self) -> str:
        return f"<Embed title={self.title} colour={self.colour}>"

    def copy(self) -> Self:
        """ Returns a copy of the embed """
        return self.__class__.from_dict(self.to_dict())

    def set_colour(
        self,
        value: Colour | int | None
    ) -> Self:
        """
        Set the colour of the embed

        Parameters
        ----------
        value: `Optional[Union[Colour, int]]`
            The colour to set the embed to.
            If `None`, the colour will be removed

        Returns
        -------
        `Self`
            Returns the embed you are editing
        """
        if value is None:
            self._colour = None
        else:
            self._colour = Colour(int(value))

        return self

    def set_footer(
        self,
        *,
        text: str | None = None,
        icon_url: Asset | str | None = None
    ) -> Self:
        """
        Set the footer of the embed

        Parameters
        ----------
        text: `Optional[str]`
            The text of the footer
        icon_url: `Optional[str]`
            Icon URL of the footer

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        if not any((text, icon_url)):
            self.footer.clear()
        else:
            if text:
                self.footer["text"] = str(text)
            if icon_url:
                self.footer["icon_url"] = str(icon_url)

        return self

    def remove_footer(self) -> Self:
        """
        Remove the footer from the embed

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        self.footer = {}
        return self

    def set_author(
        self,
        *,
        name: str,
        url: str | None = None,
        icon_url: Asset | str | None = None
    ) -> Self:
        """
        Set the author of the embed

        Parameters
        ----------
        name: `str`
            The name of the author
        url: `Optional[str]`
            The URL which the author name will link to
        icon_url: `Optional[Union[Asset, str]]`
            The icon URL of the author

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        self.author["name"] = str(name)

        if url is not None:
            self.author["url"] = str(url)
        if icon_url is not None:
            self.author["icon_url"] = str(icon_url)

        return self

    def remove_author(self) -> Self:
        """
        Remove the author from the embed

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        self.author = {}
        return self

    def set_image(
        self,
        *,
        url: Asset | str | None = None
    ) -> Self:
        """
        Set the image of the embed

        Parameters
        ----------
        url: `Optional[Union[Asset, str]]`
            The URL of the image

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        if url is not None:
            self.image["url"] = str(url)
        else:
            self.image.clear()

        return self

    def remove_image(self) -> Self:
        """
        Remove the image from the embed

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        self.image = {}
        return self

    def set_thumbnail(
        self,
        *,
        url: Asset | str | None = None
    ) -> Self:
        """
        Set the thumbnail of the embed

        Parameters
        ----------
        url: `Optional[Union[Asset, str]]`
            The URL of the thumbnail

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        if url is not None:
            self.thumbnail["url"] = str(url)
        else:
            self.thumbnail.clear()

        return self

    def remove_thumbnail(self) -> Self:
        """
        Remove the thumbnail from the embed

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        self.thumbnail = {}
        return self

    def add_field(
        self,
        *,
        name: str,
        value: str,
        inline: bool = True
    ) -> Self:
        """
        Add a field to the embed

        Parameters
        ----------
        name: `str`
            Title of the field
        value: `str`
            Description of the field
        inline: `bool`
            Whether the field is inline or not

        Returns
        -------
        `Embed`
            Returns the embed you are editing
        """
        self.fields.append({
            "name": str(name),
            "value": str(value),
            "inline": inline,
        })

        return self

    def remove_field(self, index: int) -> Self:
        """
        Remove a field from the embed

        Parameters
        ----------
        index: `int`
            The index of the field to remove

        Returns
        -------
        `Embed`
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
        Create an embed from a dictionary

        Parameters
        ----------
        data: `dict`
            The dictionary to create the embed from

        Returns
        -------
        `Embed`
            The embed created from the dictionary
        """
        self = cls.__new__(cls)

        self.colour = None
        if data.get("color", None) is not None:
            self.colour = Colour(data["color"])

        self.title = data.get("title", None)
        self.description = data.get("description", None)
        self.timestamp = data.get("timestamp", None)
        self.url = data.get("url", None)
        self.type = data.get("type", "rich")

        self.footer = data.get("footer", {})
        self.image = data.get("image", {})
        self.thumbnail = data.get("thumbnail", {})
        self.author = data.get("author", {})
        self.fields = data.get("fields", [])

        return self

    def to_dict(self) -> dict:
        """ The embed as a dictionary """
        embed = {}

        if self.title:
            embed["title"] = self.title
        if self.description:
            embed["description"] = self.description
        if self.url:
            embed["url"] = self.url
        if self.author:
            embed["author"] = self.author
        if self.colour:
            embed["color"] = int(self.colour)
        if self.footer:
            embed["footer"] = self.footer
        if self.image:
            embed["image"] = self.image
        if self.thumbnail:
            embed["thumbnail"] = self.thumbnail
        if self.fields:
            embed["fields"] = self.fields
        if self.timestamp:
            if isinstance(self.timestamp, datetime):
                if self.timestamp.tzinfo is None:
                    self.timestamp = self.timestamp.astimezone()
                embed["timestamp"] = self.timestamp.isoformat()

        return embed
