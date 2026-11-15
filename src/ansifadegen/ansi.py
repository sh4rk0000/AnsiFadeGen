"""ANSI escape rendering with truecolor, 256-colour, 16-colour and Discord output."""

from __future__ import annotations

from typing import List, Optional, Sequence

from .colors import RGB
from .engine import Grid

ESC = "\x1b"
RESET = f"{ESC}[0m"

DEPTHS = ("truecolor", "256", "16", "8")

# xterm default palette for the 16 basic colours (index 0-7 normal, 8-15 bright).
_BASIC16: Sequence[RGB] = (
    (0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0),
    (0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229),
    (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (92, 92, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
)  # fmt: skip
_CUBE = (0, 95, 135, 175, 215, 255)


def _dist(a: RGB, b: RGB) -> float:
    # "Redmean" weighting: a cheap approximation of perceived colour distance.
    rm = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db


def nearest_basic(rgb: RGB, count: int = 16) -> int:
    """Index of the closest basic colour among the first ``count`` (8 or 16)."""
    return min(range(count), key=lambda i: _dist(rgb, _BASIC16[i]))


def to_xterm256(rgb: RGB) -> int:
    ci = [min(range(6), key=lambda i: abs(_CUBE[i] - v)) for v in rgb]
    cube = (_CUBE[ci[0]], _CUBE[ci[1]], _CUBE[ci[2]])
    best, best_d = 16 + 36 * ci[0] + 6 * ci[1] + ci[2], _dist(rgb, cube)
    for k in range(24):  # greyscale ramp 232-255
        g = 8 + 10 * k
        d = _dist(rgb, (g, g, g))
        if d < best_d:
            best, best_d = 232 + k, d
    return best


def fg_code(rgb: RGB, depth: str = "truecolor") -> str:
    if depth == "truecolor":
        return f"{ESC}[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    if depth == "256":
        return f"{ESC}[38;5;{to_xterm256(rgb)}m"
    i = nearest_basic(rgb, 8 if depth == "8" else 16)
    return f"{ESC}[{30 + i if i < 8 else 90 + i - 8}m"


def bg_code(rgb: RGB, depth: str = "truecolor") -> str:
    if depth == "truecolor":
        return f"{ESC}[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    if depth == "256":
        return f"{ESC}[48;5;{to_xterm256(rgb)}m"
    i = nearest_basic(rgb, 8 if depth == "8" else 16)
    return f"{ESC}[{40 + i if i < 8 else 100 + i - 8}m"


def render_ansi(grid: Grid, depth: str = "truecolor", bg: Optional[RGB] = None) -> str:
    """Render the grid. A colour code is only emitted when it actually changes.

    Blank cells never get a colour code of their own. With ``bg`` set, every line
    starts with the background code and is padded so the background is a rectangle.
    """
    if depth not in DEPTHS:
        raise ValueError(f"unknown colour depth {depth!r}; choose from {DEPTHS}")
    bg_prefix = bg_code(bg, depth) if bg is not None else ""
    out: List[str] = []
    for row in grid.rows:
        parts: List[str] = [bg_prefix]
        current = None
        for cell in row:
            if cell.color is not None:
                code = fg_code(cell.color, depth)
                if code != current:
                    parts.append(code)
                    current = code
            parts.append(cell.ch)
        if bg is not None:
            used = row[-1].col + row[-1].width if row else 0
            parts.append(" " * (grid.width - used))
        parts.append(RESET)
        out.append("".join(parts))
    return "\n".join(out)
