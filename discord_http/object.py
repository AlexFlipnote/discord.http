from datetime import datetime

from . import utils

__all__ = (
    "PartialBase",
    "Snowflake",
)


class Snowflake:
    """ A class to represent a Discord Snowflake. """
    def __init__(
        self,
        id: int | str  # noqa: A002
    ):
        try:
            id = int(id)  # noqa: A001
        except ValueError:
            raise TypeError(f"id must be an integer or convertible to integer, not {type(id)}")

        self.id: int = id

    def __repr__(self) -> str:
        return f"<Snowflake id={self.id}>"

    def __int__(self) -> int:
        return self.id

    def __hash__(self) -> int:
        return self.id >> 22

    def __eq__(self, other: "Snowflake | int") -> bool:
        if isinstance(other, Snowflake):
            return self.id == other.id
        if isinstance(other, int):
            return self.id == other
        return False

    def __gt__(self, other: "Snowflake | int") -> bool:
        if isinstance(other, Snowflake):
            return self.id > other.id
        if isinstance(other, int):
            return self.id > other
        raise TypeError(
            f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
        )

    def __lt__(self, other: "Snowflake | int") -> bool:
        if isinstance(other, Snowflake):
            return self.id < other.id
        if isinstance(other, int):
            return self.id < other
        raise TypeError(
            f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
        )

    def __ge__(self, other: "Snowflake | int") -> bool:
        if isinstance(other, Snowflake):
            return self.id >= other.id
        if isinstance(other, int):
            return self.id >= other
        raise TypeError(
            f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
        )

    def __le__(self, other: "Snowflake | int") -> bool:
        if isinstance(other, Snowflake):
            return self.id <= other.id
        if isinstance(other, int):
            return self.id <= other
        raise TypeError(
            f"Cannot compare 'Snowflake' to '{type(other).__name__}'"
        )

    @property
    def created_at(self) -> datetime:
        """ The datetime of the snowflake. """
        return utils.snowflake_time(self.id)


class PartialBase(Snowflake):
    """
    A base class for partial objects.

    This class is based on the Snowflae class standard,
    but with a few extra attributes.
    """
    def __init__(self, *, id: int):  # noqa: A002
        super().__init__(id=int(id))

    def __repr__(self) -> str:
        return f"<PartialBase id={self.id}>"

    def is_partial(self) -> bool:
        """
        Returns True if the object is partial.

        This depends on the class name starting with Partial or not.
        """
        return self.__class__.__name__.startswith("Partial")
