import random

from typing import Any, Self

from . import utils

__all__ = (
    "Color",
    "Colour",
)


class Colour:
    def __init__(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"value must be an integer, not {type(value)}")

        if value < 0 or value > 0xFFFFFF:
            raise ValueError(f"value must be between 0 and 16777215, not {value}")

        self.value: int = value

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return self.to_hex()

    def __repr__(self) -> str:
        return f"<Colour value={self.value}>"

    def _get_byte(self, byte: int) -> int:
        return (self.value >> (8 * byte)) & 0xFF

    @property
    def r(self) -> int:
        """ `int`: Returns the red component of the colour """
        return self._get_byte(2)

    @property
    def g(self) -> int:
        """ `int`: Returns the green component of the colour """
        return self._get_byte(1)

    @property
    def b(self) -> int:
        """ `int`: Returns the blue component of the colour """
        return self._get_byte(0)

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> Self:
        """
        Creates a Colour object from RGB values

        Parameters
        ----------
        r: `int`
            Red value
        g: `int`
            Green value
        b: `int`
            Blue value

        Returns
        -------
        `Colour`
            The colour object
        """
        return cls((r << 16) + (g << 8) + b)

    def to_rgb(self) -> tuple[int, int, int]:
        """ `tuple[int, int, int]`: Returns the RGB values of the colour` """
        return (self.r, self.g, self.b)

    @classmethod
    def from_hex(cls, hex: str) -> Self:
        """
        Creates a Colour object from a hex string

        Parameters
        ----------
        hex: `str`
            The hex string to convert

        Returns
        -------
        `Colour`
            The colour object

        Raises
        ------
        `ValueError`
            Invalid hex colour
        """
        find_hex = utils.re_hex.search(hex)
        if not find_hex:
            raise ValueError(f"Invalid hex colour {hex!r}")

        if hex.startswith("#"):
            hex = hex[1:]
        if len(hex) == 3:
            hex = hex * 2

        return cls(int(hex[1:], 16))

    def to_hex(self) -> str:
        """ `str`: Returns the hex value of the colour """
        return f"#{self.value:06x}"

    @classmethod
    def default(cls) -> Self:
        """ `Colour`: Returns the default colour (#000000, Black) """
        return cls(0)

    @classmethod
    def random(
        cls,
        *,
        seed: Any | None = None
    ) -> Self:
        """
        Creates a random colour

        Parameters
        ----------
        seed: `Optional[Any]`
            The seed to use for the random colour to make it deterministic

        Returns
        -------
        `Colour`
            The random colour
        """
        r = random.Random(seed) if seed else random
        return cls(r.randint(0, 0xFFFFFF))


class Color(Colour):
    """ Alias for Colour """
    def __init__(self, value: int):
        super().__init__(value)

    def __repr__(self) -> str:
        return f"<Color value={self.value}>"
