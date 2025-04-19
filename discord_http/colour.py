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
        """ Returns the red component of the colour """
        return self._get_byte(2)

    @property
    def g(self) -> int:
        """ Returns the green component of the colour """
        return self._get_byte(1)

    @property
    def b(self) -> int:
        """ Returns the blue component of the colour """
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
        """ Returns the RGB values of the colour` """
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

        return cls(int(hex, 16))

    def to_hex(self) -> str:
        """ Returns the hex value of the colour """
        return f"#{self.value:06x}"

    @classmethod
    def default(cls) -> Self:
        """ Returns the default colour (#000000, Black) """
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

    # Colours based on https://flatuicolors.com/palette/defo
    # A few of them are custom to Discord however

    @classmethod
    def turquoise(cls) -> Self:
        """ Returns the turquoise colour """
        return cls(0x1abc9c)

    @classmethod
    def green_sea(cls) -> Self:
        """ Returns the green sea colour """
        return cls(0x16a085)

    @classmethod
    def emerald(cls) -> Self:
        """ Returns the emerald colour """
        return cls(0x2ecc71)

    @classmethod
    def nephritis(cls) -> Self:
        """ Returns the nephritis colour """
        return cls(0x27ae60)

    @classmethod
    def peter_river(cls) -> Self:
        """ Returns the peter river colour """
        return cls(0x3498db)

    @classmethod
    def belize_hole(cls) -> Self:
        """ Returns the belize hole colour """
        return cls(0x2980b9)

    @classmethod
    def amethyst(cls) -> Self:
        """ Returns the amethyst colour """
        return cls(0x9b59b6)

    @classmethod
    def wisteria(cls) -> Self:
        """ Returns the wisteria colour """
        return cls(0x8e44ad)

    @classmethod
    def mellow_melon(cls) -> Self:
        """ Returns the mellow melon colour """
        return cls(0xe91e63)

    @classmethod
    def plum_perfect(cls) -> Self:
        """ Returns the plum perfect colour """
        return cls(0xad1457)

    @classmethod
    def sun_flower(cls) -> Self:
        """ Returns the sun flower colour """
        return cls(0xf1c40f)

    @classmethod
    def orange(cls) -> Self:
        """ Returns the orange colour """
        return cls(0xf39c12)

    @classmethod
    def carrot(cls) -> Self:
        """ Returns the carrot colour """
        return cls(0xe67e22)

    @classmethod
    def pumpkin(cls) -> Self:
        """ Returns the pumpkin colour """
        return cls(0xd35400)

    @classmethod
    def alizarin(cls) -> Self:
        """ Returns the alizarin colour """
        return cls(0xe74c3c)

    @classmethod
    def pomegranate(cls) -> Self:
        """ Returns the pomegranate colour """
        return cls(0xc0392b)

    @classmethod
    def dusty_sky(cls) -> Self:
        """ Returns the dusty sky colour """
        return cls(0x95a5a6)

    @classmethod
    def harrison_grey(cls) -> Self:
        """ Returns the harrison grey colour """
        return cls(0x979c9f)

    @classmethod
    def whale_shark(cls) -> Self:
        """ Returns the whale shark colour """
        return cls(0x607d8b)

    @classmethod
    def blue_sentinel(cls) -> Self:
        """ Returns the blue sentinel colour """
        return cls(0x546e7a)


class Color(Colour):
    """ Alias for Colour """
    def __init__(self, value: int):
        super().__init__(value)

    def __repr__(self) -> str:
        return f"<Color value={self.value}>"
