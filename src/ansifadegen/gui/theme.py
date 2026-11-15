"""Colour palette and font helpers shared by every GUI module."""

from __future__ import annotations

import tkinter.font as tkfont

BG = "#0f0f15"
PANEL = "#15151d"
CARD = "#1d1d28"
CARD_HOVER = "#262635"
BORDER = "#2e2e42"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#6a49f0"
TEXT = "#ececf4"
MUTED = "#8a8aa3"
DANGER = "#ff6b81"
OK = "#5ad6a0"
PREVIEW_BG = "#050508"

# Block glyphs (█ ▀ ▄) must tile without seams, so fonts that do come first.
_MONO = (
    "Cascadia Mono", "DejaVu Sans Mono", "Menlo", "Consolas", "SF Mono",
    "Liberation Mono", "JetBrains Mono", "Courier New",
)  # fmt: skip


def mono_family() -> str:
    """First installed monospace family from a preference list (needs a Tk root)."""
    available = {f.lower(): f for f in tkfont.families()}
    for name in _MONO:
        if name.lower() in available:
            return available[name.lower()]
    return tkfont.nametofont("TkFixedFont").actual("family")
