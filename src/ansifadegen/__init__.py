"""AnsiFadeGen: multi-stop colour gradients for text and ASCII art."""

from .ansi import render_ansi
from .colors import ColorError, parse_color, parse_color_list
from .engine import Gradient, compute_grid, prepare_lines, strip_ansi
from .export import FORMATS, ExportError, render

__version__ = "1.0.0"

__all__ = [
    "ColorError", "ExportError", "FORMATS", "Gradient", "compute_grid", "parse_color",
    "parse_color_list", "prepare_lines", "render", "render_ansi", "strip_ansi",
]  # fmt: skip


def apply_gradient(text, colors, angle=45.0, fmt="ansi", **kwargs):
    """One-call helper: ``apply_gradient("hello", ["red", "blue"])`` → ANSI string."""
    gradient = Gradient.from_colors(
        [parse_color(c) for c in colors], kwargs.pop("space", "srgb")
    )
    bg = kwargs.pop("bg", None)
    grid = compute_grid(prepare_lines(text), gradient, angle=angle, **kwargs)
    return render(grid, fmt, parse_color(bg) if bg else None)
