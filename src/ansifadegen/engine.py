"""Pure gradient engine: no I/O, no GUI. Everything else renders the :class:`Grid` built here.

Geometry
--------
Cells live on a plane where one terminal column is 1 unit wide and one row is
``aspect`` units tall (a terminal cell is roughly twice as tall as wide, so the
default is 2.0). For a *linear* gradient at angle ``θ`` (degrees, 0 = left→right,
90 = top→bottom) a cell at ``p`` gets

    t = (p·d − min) / (max − min),    d = (cos θ, sin θ),

where min/max are taken over the four corners of the bounding box, so t spans
exactly [0, 1] whatever the angle. A *radial* gradient uses the normalised
distance to the centre of the box.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Iterator, List, NamedTuple, Optional, Sequence, Tuple, Union

from .colors import RGB, parse_color

SPACES = ("srgb", "linear", "oklab")
MODES = ("linear", "radial")

_LUT_SIZE = 1024
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")


# --------------------------------------------------------------------------- colour spaces
def _srgb_to_lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(v: float) -> float:
    v = min(max(v, 0.0), 1.0)
    c = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return c * 255.0


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1 / 3), x)


def _lin_to_oklab(r: float, g: float, b: float) -> Tuple[float, float, float]:
    l_ = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_to_lin(L: float, a: float, b: float) -> Tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    lc, mc, sc = l_**3, m_**3, s_**3
    return (
        4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc,
        -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc,
        -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc,
    )


def _to_space(rgb: RGB, space: str) -> Tuple[float, float, float]:
    if space == "srgb":
        return (float(rgb[0]), float(rgb[1]), float(rgb[2]))
    lin = tuple(_srgb_to_lin(c) for c in rgb)
    return lin if space == "linear" else _lin_to_oklab(*lin)


def _from_space(v: Tuple[float, float, float], space: str) -> RGB:
    if space == "srgb":
        out = v
    else:
        lin = v if space == "linear" else _oklab_to_lin(*v)
        out = tuple(_lin_to_srgb(c) for c in lin)
    return tuple(min(255, max(0, int(round(c)))) for c in out)  # type: ignore[return-value]


# --------------------------------------------------------------------------- gradient
class Gradient:
    """Piecewise-affine colour ramp over [0, 1] with arbitrary stop positions."""

    def __init__(self, stops: Sequence[Tuple[float, Union[RGB, str]]], space: str = "srgb"):
        if space not in SPACES:
            raise ValueError(f"unknown interpolation space {space!r}; choose from {SPACES}")
        if len(stops) < 2:
            raise ValueError("A gradient needs at least two stops")
        self.space = space
        self.stops: List[Tuple[float, RGB]] = sorted(
            ((min(1.0, max(0.0, float(p))), parse_color(c)) for p, c in stops),
            key=lambda s: s[0],
        )
        self._lut: Optional[List[RGB]] = None

    @classmethod
    def from_colors(cls, colors: Sequence[Union[RGB, str]], space: str = "srgb") -> "Gradient":
        n = len(colors)
        if n < 2:
            raise ValueError("A gradient needs at least two colours")
        return cls([(i / (n - 1), c) for i, c in enumerate(colors)], space)

    def reversed(self) -> "Gradient":
        return Gradient([(1.0 - p, c) for p, c in self.stops], self.space)

    def _compute(self, t: float) -> RGB:
        stops = self.stops
        if t <= stops[0][0]:
            return stops[0][1]
        if t >= stops[-1][0]:
            return stops[-1][1]
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                if p1 - p0 < 1e-12:
                    return c1
                u = (t - p0) / (p1 - p0)
                a, b = _to_space(c0, self.space), _to_space(c1, self.space)
                return _from_space(tuple(x + (y - x) * u for x, y in zip(a, b)), self.space)
        return stops[-1][1]  # pragma: no cover

    def at(self, t: float) -> RGB:
        """Colour at ``t`` in [0, 1] (clamped). Backed by a 1025-entry lookup table."""
        if self._lut is None:
            self._lut = [self._compute(i / _LUT_SIZE) for i in range(_LUT_SIZE + 1)]
        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
        return self._lut[int(round(t * _LUT_SIZE))]


# --------------------------------------------------------------------------- text → grid
class Cell(NamedTuple):
    ch: str
    col: int  # first terminal column occupied
    width: int  # 0 (combining), 1 or 2 (East-Asian wide)
    color: Optional[RGB]  # None for blanks: they need no colour of their own


class Grid(NamedTuple):
    rows: List[List[Cell]]
    width: int  # terminal columns of the widest row
    height: int


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def char_width(ch: str) -> int:
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def prepare_lines(text: str, tabsize: int = 4) -> List[str]:
    """Split text into lines: ANSI codes removed, tabs expanded, no trailing newline."""
    return [line.expandtabs(tabsize) for line in strip_ansi(text).splitlines()]


def _t_function(width: int, height: int, angle: float, mode: str, aspect: float):
    xmax = float(max(width - 1, 0))
    ymax = float(max(height - 1, 0)) * aspect
    if mode == "radial":
        cx, cy = xmax / 2, ymax / 2
        rmax = math.hypot(cx, cy)
        if rmax < 1e-9:
            return lambda x, y: 0.0
        return lambda x, y: math.hypot(x - cx, y - cy) / rmax
    th = math.radians(angle)
    dx, dy = math.cos(th), math.sin(th)
    proj = [x * dx + y * dy for x, y in ((0, 0), (xmax, 0), (0, ymax), (xmax, ymax))]
    lo, span = min(proj), max(proj) - min(proj)
    if span < 1e-9:
        return lambda x, y: 0.0
    return lambda x, y: (x * dx + y * dy - lo) / span


def compute_grid(
    lines: Sequence[str],
    gradient: Gradient,
    angle: float = 45.0,
    mode: str = "linear",
    aspect: float = 2.0,
    reverse: bool = False,
) -> Grid:
    """Colour every non-blank cell of ``lines``. This is the single source of truth."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; choose from {MODES}")
    if aspect <= 0:
        raise ValueError("aspect must be positive")

    layout: List[List[Tuple[str, int, int]]] = []
    for line in lines:
        col, row = 0, []
        for ch in line:
            w = char_width(ch)
            row.append((ch, col, w))
            col += w
        layout.append(row)

    width = max((row[-1][1] + row[-1][2] for row in layout if row), default=0)
    height = len(layout)
    t_of = _t_function(width, height, angle, mode, aspect)

    rows: List[List[Cell]] = []
    for y, row in enumerate(layout):
        out: List[Cell] = []
        last: Optional[RGB] = None
        for ch, col, w in row:
            if ch.isspace():
                color = None
            elif w == 0:
                color = last  # combining mark: stay with its base character
            else:
                t = t_of(col + (w - 1) / 2.0, y * aspect)
                if reverse:
                    t = 1.0 - t
                color = gradient.at(t)
            if color is not None:
                last = color
            out.append(Cell(ch, col, w, color))
        rows.append(out)
    return Grid(rows, width, height)


def iter_runs(row: Sequence[Cell]) -> Iterator[Tuple[Optional[RGB], str, int, int]]:
    """Merge a row into runs ``(colour, text, start_col, n_cols)``.

    Blank cells inherit the surrounding colour so they never split a run.
    """
    cur: Optional[RGB] = None
    buf: List[str] = []
    start = ncols = 0
    for cell in row:
        c = cell.color if cell.color is not None else cur
        if buf and c != cur:
            yield cur, "".join(buf), start, ncols
            buf, start, ncols = [], cell.col, 0
        if not buf:
            start = cell.col
        cur = c
        buf.append(cell.ch)
        ncols += cell.width
    if buf:
        yield cur, "".join(buf), start, ncols
