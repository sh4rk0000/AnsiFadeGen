"""Graphical interface (needs the optional ``customtkinter`` dependency)."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from .app import run
    except ImportError as exc:  # customtkinter or tkinter missing
        print(
            f"ansifadegen: the GUI needs customtkinter and tkinter ({exc}).\n"
            "Install with:  pip install 'ansifadegen[gui]'",
            file=sys.stderr,
        )
        return 1
    return run()
