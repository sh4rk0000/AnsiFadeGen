"""Colour parsing: names, ``#rgb`` / ``#rrggbb`` hex, and ``r,g,b`` triplets."""

from __future__ import annotations

import re
from typing import List, Tuple

RGB = Tuple[int, int, int]


class ColorError(ValueError):
    """Raised when a colour (or a colour list) cannot be parsed."""


# The first eleven keep the exact values of the original project.
NAMED_COLORS = {
    "red": (255, 0, 0),
    "yellow": (255, 255, 0),
    "green": (37, 196, 104),
    "lime": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "grey": (186, 191, 188),
    "gray": (186, 191, 188),
    "white": (255, 255, 255),
    "pink": (255, 0, 230),
    "purple": (162, 0, 255),
    "black": (0, 0, 0),
    "orange": (255, 140, 0),
    "magenta": (255, 0, 255),
    "gold": (255, 200, 0),
    "coral": (255, 100, 90),
    "teal": (0, 168, 150),
    "navy": (20, 30, 120),
    "violet": (138, 43, 226),
    "mint": (120, 255, 190),
    "sky": (90, 190, 255),
}

_HEX_RE = re.compile(r"^#([0-9a-f]{3}|[0-9a-f]{6})$")


def _check_channels(values) -> RGB:
    try:
        r, g, b = (int(v) for v in values)
    except (TypeError, ValueError):
        raise ColorError("expected three integers R,G,B") from None
    if not all(0 <= v <= 255 for v in (r, g, b)):
        raise ColorError("RGB values must be between 0 and 255")
    return (r, g, b)


def parse_color(value) -> RGB:
    """Parse a colour name, ``#hex`` string, ``"r,g,b"`` string or an RGB sequence."""
    if isinstance(value, (tuple, list)):
        return _check_channels(value)
    s = str(value).strip().lower()
    if s in NAMED_COLORS:
        return NAMED_COLORS[s]
    m = _HEX_RE.match(s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    parts = [p for p in re.split(r"[,\s]+", s) if p]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return _check_channels(parts)
    raise ColorError(
        f"Invalid colour {value!r} (use a name, #rrggbb, or R,G,B with values 0-255)"
    )


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def parse_color_list(text: str) -> List[RGB]:
    """Parse ``"red, #00ff88, 255,0,128, blue"`` into a list of at least two colours.

    Bare numbers are grouped three by three into R,G,B triplets, so the original
    ``red,0,255,0,blue`` syntax keeps working.
    """
    colors: List[RGB] = []
    numbers: List[str] = []
    for piece in text.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece.isdigit():
            numbers.append(piece)
            if len(numbers) == 3:
                colors.append(_check_channels(numbers))
                numbers = []
            continue
        if numbers:
            raise ColorError("Incomplete RGB colour (expected R,G,B)")
        colors.append(parse_color(piece))
    if numbers:
        raise ColorError("Incomplete RGB colour (expected R,G,B)")
    if len(colors) < 2:
        raise ColorError("At least two colours are required for a gradient")
    return colors
