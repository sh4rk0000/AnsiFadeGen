"""Export a :class:`~ansifadegen.engine.Grid` to ANSI, Discord, HTML, SVG or PNG."""

from __future__ import annotations

import io
from html import escape
from typing import Dict, NamedTuple, Optional, Union

from .ansi import render_ansi
from .colors import RGB, rgb_to_hex
from .engine import Grid, iter_runs


class ExportError(RuntimeError):
    pass


class Format(NamedTuple):
    key: str
    label: str
    ext: str
    text: bool  # False → binary payload, cannot be shown or copied as text


FORMATS: Dict[str, Format] = {
    f.key: f
    for f in (
        Format("ansi", "ANSI truecolor", ".txt", True),
        Format("ansi256", "ANSI 256 colours", ".txt", True),
        Format("ansi16", "ANSI 16 colours", ".txt", True),
        Format("discord", "Discord (```ansi)", ".txt", True),
        Format("html", "HTML", ".html", True),
        Format("svg", "SVG", ".svg", True),
        Format("png", "PNG image", ".png", False),
    )
}
DEFAULT_BG_HTML = "#0d0d12"


def to_html(grid: Grid, bg: Optional[RGB] = None, title: str = "AnsiFadeGen") -> str:
    bg_hex = rgb_to_hex(bg) if bg else DEFAULT_BG_HTML
    lines = []
    for row in grid.rows:
        spans = []
        for color, text, _col, _n in iter_runs(row):
            body = escape(text)
            if color:
                body = f'<span style="color:{rgb_to_hex(color)}">{body}</span>'
            spans.append(body)
        lines.append("".join(spans))
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>{escape(title)}</title>\n"
        f"<style>body{{margin:0;background:{bg_hex}}}"
        "pre{margin:0;padding:24px;font:16px/1.15 'JetBrains Mono','Cascadia Mono',"
        "Consolas,'DejaVu Sans Mono',monospace}</style></head>\n"
        "<body><pre>" + "\n".join(lines) + "</pre></body></html>\n"
    )


def to_svg(grid: Grid, bg: Optional[RGB] = None, cell_w: int = 10, cell_h: int = 20) -> str:
    pad = 16
    w, h = grid.width * cell_w + 2 * pad, grid.height * cell_h + 2 * pad
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    ]
    if bg:
        out.append(f'<rect width="100%" height="100%" fill="{rgb_to_hex(bg)}"/>')
    out.append(
        '<g font-family="\'JetBrains Mono\',\'Cascadia Mono\',Consolas,\'DejaVu Sans Mono\','
        f'monospace" font-size="{int(cell_h * 0.8)}" xml:space="preserve">'
    )
    for y, row in enumerate(grid.rows):
        for color, text, col, ncols in iter_runs(row):
            if color is None or not text.strip():
                continue
            out.append(
                f'<text x="{pad + col * cell_w}" y="{pad + y * cell_h + int(cell_h * 0.78)}" '
                f'fill="{rgb_to_hex(color)}" textLength="{ncols * cell_w}" '
                f'lengthAdjust="spacingAndGlyphs">{escape(text)}</text>'
            )
    out.append("</g></svg>\n")
    return "\n".join(out)


_FONT_CANDIDATES = (
    "JetBrainsMono-Regular.ttf", "DejaVuSansMono.ttf", "consola.ttf", "Menlo.ttc",
    "LiberationMono-Regular.ttf", "cour.ttf",
)  # fmt: skip
# Block glyphs drawn as rectangles (x0, y0, x1, y1 as fractions of the cell): pixel-perfect
# whatever the font.
_BLOCKS = {
    "█": (0, 0, 1, 1), "▀": (0, 0, 1, 0.5), "▄": (0, 0.5, 1, 1),
    "▌": (0, 0, 0.5, 1), "▐": (0.5, 0, 1, 1),
}  # fmt: skip


def to_png(grid: Grid, bg: Optional[RGB] = None, scale: int = 2) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ExportError("PNG export needs Pillow:  pip install pillow") from None

    size = 16 * scale
    font = None
    for name in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(name, size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    cw = max(1, int(round(font.getlength("M"))))
    ascent, descent = font.getmetrics() if hasattr(font, "getmetrics") else (size, 0)
    ch_h = ascent + descent
    pad = 12 * scale
    img = Image.new(
        "RGBA",
        (grid.width * cw + 2 * pad, grid.height * ch_h + 2 * pad),
        (*bg, 255) if bg else (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(img)
    for y, row in enumerate(grid.rows):
        for cell in row:
            if cell.color is None or cell.width == 0:
                continue
            x0, y0 = pad + cell.col * cw, pad + y * ch_h
            if cell.ch in _BLOCKS:
                fx0, fy0, fx1, fy1 = _BLOCKS[cell.ch]
                draw.rectangle(
                    (x0 + fx0 * cw, y0 + fy0 * ch_h, x0 + fx1 * cw * cell.width - 1,
                     y0 + fy1 * ch_h - 1),
                    fill=cell.color,
                )  # fmt: skip
            else:
                draw.text((x0, y0), cell.ch, font=font, fill=cell.color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def render(grid: Grid, fmt: str, bg: Optional[RGB] = None) -> Union[str, bytes]:
    """Render ``grid`` in format ``fmt`` (a key of :data:`FORMATS`)."""
    if fmt not in FORMATS:
        raise ExportError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}")
    if fmt == "ansi":
        return render_ansi(grid, "truecolor", bg)
    if fmt == "ansi256":
        return render_ansi(grid, "256", bg)
    if fmt == "ansi16":
        return render_ansi(grid, "16", bg)
    if fmt == "discord":
        return "```ansi\n" + render_ansi(grid, "8", bg) + "\n```"
    if fmt == "html":
        return to_html(grid, bg)
    if fmt == "svg":
        return to_svg(grid, bg)
    return to_png(grid, bg)
