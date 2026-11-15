"""Command-line interface: ``ansifadegen [FILE] -c red,blue -a 45``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .colors import ColorError, parse_color, parse_color_list
from .engine import MODES, SPACES, Gradient, compute_grid, prepare_lines
from .export import FORMATS, ExportError, render
from .presets import BUILTIN_PRESETS

DIRECTIONS = {"horizontal": 0.0, "vertical": 90.0, "diagonal": 45.0}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ansifadegen",
        description="Apply a colour gradient to text or ASCII art. Reads FILE or stdin.",
    )
    p.add_argument("file", nargs="?", help="input text file (default: stdin)")
    p.add_argument("-c", "--colors", default="blue,pink",
                   help="comma-separated colours: names, #hex or R,G,B (default: blue,pink)")
    p.add_argument("-p", "--preset", choices=sorted(BUILTIN_PRESETS, key=str.lower),
                   help="use a built-in gradient preset instead of --colors")
    p.add_argument("-a", "--angle", type=float, default=None,
                   help="angle in degrees: 0 = left→right, 90 = top→bottom (default: 45)")
    p.add_argument("-d", "--direction", choices=sorted(DIRECTIONS),
                   help="shortcut for --angle (horizontal=0, vertical=90, diagonal=45)")
    p.add_argument("-m", "--mode", choices=MODES, default="linear")
    p.add_argument("--aspect", type=float, default=2.0,
                   help="cell height / width ratio (default: 2.0)")
    p.add_argument("-r", "--reverse", action="store_true", help="reverse the gradient")
    p.add_argument("--space", choices=SPACES, default="srgb",
                   help="interpolation space (oklab avoids muddy mid-tones)")
    p.add_argument("--bg", help="background colour")
    p.add_argument("-f", "--format", choices=list(FORMATS), default="ansi")
    p.add_argument("-o", "--output", help="write to a file instead of stdout")
    p.add_argument("--gui", action="store_true", help="launch the graphical interface")
    p.add_argument("--version", action="version", version=f"ansifadegen {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)

    if args.gui or (not argv and sys.stdin.isatty()):
        from .gui import main as gui_main

        return gui_main() or 0

    try:
        colors = BUILTIN_PRESETS[args.preset] if args.preset else None
        if colors is None:
            palette = parse_color_list(args.colors)
        else:
            palette = [parse_color(c) for c in colors]
        angle = args.angle if args.angle is not None else DIRECTIONS.get(args.direction, 45.0)
        bg = parse_color(args.bg) if args.bg else None

        if args.file:
            with open(args.file, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        elif sys.stdin.isatty():
            print("ansifadegen: no input (give a FILE or pipe text in)", file=sys.stderr)
            return 2
        else:
            text = sys.stdin.read()

        grid = compute_grid(
            prepare_lines(text), Gradient.from_colors(palette, args.space),
            angle=angle, mode=args.mode, aspect=args.aspect, reverse=args.reverse,
        )  # fmt: skip
        data = render(grid, args.format, bg)
    except (ColorError, ExportError, ValueError, OSError) as exc:
        print(f"ansifadegen: {exc}", file=sys.stderr)
        return 1

    if args.output:
        mode, kw = ("wb", {}) if isinstance(data, bytes) else ("w", {"encoding": "utf-8"})
        with open(args.output, mode, **kw) as fh:
            fh.write(data)
    elif isinstance(data, bytes):
        sys.stdout.buffer.write(data)
    else:
        sys.stdout.buffer.write((data + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
