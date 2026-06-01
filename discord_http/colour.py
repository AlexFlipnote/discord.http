import random

from typing import Self

__all__ = (
    "Color",
    "Colour",
)


class Colour:
    """ Represents a colour object, used in multiple places in the API. """

    __slots__ = ("value",)

    def __init__(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"value must be an integer, not {type(value)}")

        if value < 0 or value > 0xFFFFFF:
            raise ValueError(f"value must be between 0 and 16777215, not {value}")

        self.value: int = value
        """ The integer value of the colour, between 0 and 16777215 (0xFFFFFF). """

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return self.to_hex()

    def __repr__(self) -> str:
        return f"<Colour value={self.value}>"

    def __eq__(self, other: "Colour") -> bool:
        return isinstance(other, Colour) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    @property
    def r(self) -> int:
        """ Returns the red component of the colour. """
        return (self.value >> 16) & 0xFF

    @property
    def g(self) -> int:
        """ Returns the green component of the colour. """
        return (self.value >> 8) & 0xFF

    @property
    def b(self) -> int:
        """ Returns the blue component of the colour. """
        return self.value & 0xFF

    @property
    def brightness(self) -> int:
        """ Returns the perceived brightness of the colour (0-255). """
        return (self.r + self.g + self.b) // 3

    def is_dark(self) -> bool:
        """ Returns whether the colour is considered dark based on perceived luminance. """
        return (self.r * 0.299 + self.g * 0.587 + self.b * 0.114) <= 186

    def is_light(self) -> bool:
        """ Returns whether the colour is considered light based on perceived luminance. """
        return not self.is_dark

    def to_rgb(self) -> tuple[int, int, int]:
        """ Returns the RGB values of the colour`. """
        return (self.r, self.g, self.b)

    def to_hex(self) -> str:
        """ Returns the hex value of the colour. """
        return f"#{self.value:06x}"

    def to_hsl(self) -> tuple[int, int, int]:
        """ Returns the HSL (hue 0-360, saturation 0-100, lightness 0-100) values of the colour. """
        r, g, b = self.r / 255, self.g / 255, self.b / 255
        cmax, cmin = max(r, g, b), min(r, g, b)
        delta = cmax - cmin

        if delta == 0:
            h = 0
        elif cmax == r:
            h = 60 * (((g - b) / delta) % 6)
        elif cmax == g:
            h = 60 * (((b - r) / delta) + 2)
        else:
            h = 60 * (((r - g) / delta) + 4)

        ll = (cmax + cmin) / 2
        s = 0 if delta == 0 else delta / (1 - abs(2 * ll - 1))
        return round(h), round(s * 100), round(ll * 100)

    def to_hsv(self) -> tuple[int, int, int]:
        """ Returns the HSV (hue 0-360, saturation 0-100, value 0-100) values of the colour. """
        r, g, b = self.r / 255, self.g / 255, self.b / 255
        cmax, cmin = max(r, g, b), min(r, g, b)
        delta = cmax - cmin

        if delta == 0:
            h = 0
        elif cmax == r:
            h = 60 * (((g - b) / delta) % 6)
        elif cmax == g:
            h = 60 * (((b - r) / delta) + 2)
        else:
            h = 60 * (((r - g) / delta) + 4)

        s = 0 if cmax == 0 else delta / cmax
        return round(h), round(s * 100), round(cmax * 100)

    def to_cmyk(self) -> tuple[int, int, int, int]:
        """ Returns the CMYK (cyan 0-100, magenta 0-100, yellow 0-100, key/black 0-100) values of the colour. """
        if (self.r, self.g, self.b) == (0, 0, 0):
            return 0, 0, 0, 100

        c = 1 - self.r / 255
        m = 1 - self.g / 255
        y = 1 - self.b / 255
        k = min(c, m, y)
        c = (c - k) / (1 - k)
        m = (m - k) / (1 - k)
        y = (y - k) / (1 - k)
        return (
            round(c * 100),
            round(m * 100),
            round(y * 100),
            round(k * 100),
        )

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> Self:
        """
        Creates a Colour object from RGB values.

        Parameters
        ----------
        r:
            Red value
        g:
            Green value
        b:
            Blue value

        Returns
        -------
            The colour object
        """
        return cls((r << 16) + (g << 8) + b)

    @classmethod
    def from_hex(cls, hex_value: str) -> Self:
        """
        Creates a Colour object from a hex string.

        Parameters
        ----------
        hex_value:
            The hex string to convert

        Returns
        -------
            The colour object

        Raises
        ------
        `ValueError`
            Invalid hex colour
        """
        hex_value = hex_value.removeprefix("#")

        if len(hex_value) not in (3, 6):
            raise ValueError(f"Hex value must be either 3 or 6 characters long, not {len(hex_value)}")

        if len(hex_value) == 3:
            hex_value = "".join(c * 2 for c in hex_value)

        try:
            return cls(int(hex_value, 16))
        except ValueError:
            raise ValueError(f"Invalid hex colour {hex_value!r}")

    @classmethod
    def from_hsl(cls, h: int, s: int, l: int) -> Self:  # noqa: E741
        """
        Creates a Colour object from HSL values.

        Parameters
        ----------
        h:
            Hue (0-360)
        s:
            Saturation (0-100)
        l:
            Lightness (0-100)

        Returns
        -------
            The colour object
        """
        sn = s / 100
        ln = l / 100
        c = (1 - abs(2 * ln - 1)) * sn
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = ln - c / 2

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return cls.from_rgb(round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))

    @classmethod
    def from_hsv(cls, h: int, s: int, v: int) -> Self:
        """
        Creates a Colour object from HSV values.

        Parameters
        ----------
        h:
            Hue (0-360)
        s:
            Saturation (0-100)
        v:
            Value (0-100)

        Returns
        -------
            The colour object
        """
        sn = s / 100
        vn = v / 100
        c = vn * sn
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = vn - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return cls.from_rgb(round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))

    @classmethod
    def from_cmyk(cls, c: int, m: int, y: int, k: int) -> Self:
        """
        Creates a Colour object from CMYK values.

        Parameters
        ----------
        c:
            Cyan (0-100)
        m:
            Magenta (0-100)
        y:
            Yellow (0-100)
        k:
            Key/black (0-100)

        Returns
        -------
            The colour object
        """
        r = round(255 * (1 - c / 100) * (1 - k / 100))
        g = round(255 * (1 - m / 100) * (1 - k / 100))
        b = round(255 * (1 - y / 100) * (1 - k / 100))
        return cls.from_rgb(r, g, b)

    @classmethod
    def default(cls) -> Self:
        """ Returns the default colour (#000000, Black). """
        return cls(0)

    @classmethod
    def random(
        cls,
        *,
        seed: str | None = None
    ) -> Self:
        """
        Creates a random colour.

        Parameters
        ----------
        seed:
            The seed to use for the random colour to make it deterministic

        Returns
        -------
            The random colour
        """
        r = random.Random(str(seed)) if seed else random
        return cls(r.randint(0, 0xFFFFFF))

    # Discord branding colours if needed
    @classmethod
    def blurple(cls) -> Self:
        """ Returns the blurple branding colour of Discord. """
        return cls(0x5865f2)

    @classmethod
    def light_blurple(cls) -> Self:
        """ Returns the light blurple branding colour of Discord. """
        return cls(0xe0e3ff)

    # Colours based on https://flatuicolors.com/palette/defo
    # A few of them are custom to Discord however
    @classmethod
    def turquoise(cls) -> Self:
        """ Returns the turquoise colour. """
        return cls(0x1abc9c)

    @classmethod
    def green_sea(cls) -> Self:
        """ Returns the green sea colour. """
        return cls(0x16a085)

    @classmethod
    def emerald(cls) -> Self:
        """ Returns the emerald colour. """
        return cls(0x2ecc71)

    @classmethod
    def nephritis(cls) -> Self:
        """ Returns the nephritis colour. """
        return cls(0x27ae60)

    @classmethod
    def peter_river(cls) -> Self:
        """ Returns the peter river colour. """
        return cls(0x3498db)

    @classmethod
    def belize_hole(cls) -> Self:
        """ Returns the belize hole colour. """
        return cls(0x2980b9)

    @classmethod
    def amethyst(cls) -> Self:
        """ Returns the amethyst colour. """
        return cls(0x9b59b6)

    @classmethod
    def wisteria(cls) -> Self:
        """ Returns the wisteria colour. """
        return cls(0x8e44ad)

    @classmethod
    def mellow_melon(cls) -> Self:
        """ Returns the mellow melon colour. """
        return cls(0xe91e63)

    @classmethod
    def plum_perfect(cls) -> Self:
        """ Returns the plum perfect colour. """
        return cls(0xad1457)

    @classmethod
    def sun_flower(cls) -> Self:
        """ Returns the sun flower colour. """
        return cls(0xf1c40f)

    @classmethod
    def orange(cls) -> Self:
        """ Returns the orange colour. """
        return cls(0xf39c12)

    @classmethod
    def carrot(cls) -> Self:
        """ Returns the carrot colour. """
        return cls(0xe67e22)

    @classmethod
    def pumpkin(cls) -> Self:
        """ Returns the pumpkin colour. """
        return cls(0xd35400)

    @classmethod
    def alizarin(cls) -> Self:
        """ Returns the alizarin colour. """
        return cls(0xe74c3c)

    @classmethod
    def pomegranate(cls) -> Self:
        """ Returns the pomegranate colour. """
        return cls(0xc0392b)

    @classmethod
    def dusty_sky(cls) -> Self:
        """ Returns the dusty sky colour. """
        return cls(0x95a5a6)

    @classmethod
    def harrison_grey(cls) -> Self:
        """ Returns the harrison grey colour. """
        return cls(0x979c9f)

    @classmethod
    def whale_shark(cls) -> Self:
        """ Returns the whale shark colour. """
        return cls(0x607d8b)

    @classmethod
    def blue_sentinel(cls) -> Self:
        """ Returns the blue sentinel colour. """
        return cls(0x546e7a)


class Color(Colour):
    """ Alias for Colour. """

    __slots__ = ()

    def __init__(self, value: int):
        super().__init__(value)

    def __repr__(self) -> str:
        return f"<Color value={self.value}>"
