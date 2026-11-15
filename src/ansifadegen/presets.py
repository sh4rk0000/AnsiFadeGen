"""Built-in gradient presets and a small JSON store for the user's own."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .colors import parse_color

BUILTIN_PRESETS: Dict[str, List[str]] = {
    "Neon": ["#ff00cc", "#3333ff", "#00ffd5"],
    "Sunset": ["#f9d423", "#ff4e50", "#7b2ff7"],
    "Ocean": ["#00c6ff", "#0072ff", "#1a2a6c"],
    "Fire": ["#ffe259", "#ff8c00", "#e01010", "#5c0000"],
    "Aurora": ["#00ff87", "#60efff", "#9d50bb"],
    "Vaporwave": ["#ff71ce", "#b967ff", "#01cdfe"],
    "Candy": ["#ff9a9e", "#fad0c4", "#a18cd1"],
    "Rainbow": ["#ff0000", "#ffa500", "#ffff00", "#00c853", "#0066ff", "#8a2be2"],
    "Matrix": ["#003b00", "#00ff41"],
    "Forest": ["#134e5e", "#71b280"],
    "Gold": ["#f7971e", "#ffd200"],
    "Ice": ["#e0f7ff", "#4facfe", "#00f2fe"],
    "Blue → Pink": ["#0000ff", "#ff00e6"],
    "Mono": ["#ffffff", "#555555"],
}


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ansifadegen"


def _store_path() -> Path:
    return config_dir() / "presets.json"


def load_user_presets() -> Dict[str, List[str]]:
    """User presets; a missing or corrupt file simply yields no presets."""
    try:
        data = json.loads(_store_path().read_text(encoding="utf-8"))
        return {
            str(k): [str(c) for c in v]
            for k, v in data.items()
            if isinstance(v, list) and len(v) >= 2 and all(_valid(c) for c in v)
        }
    except (OSError, ValueError, AttributeError):
        return {}


def split_stop(entry: str) -> Tuple[Optional[float], str]:
    """``"#ff0000@0.35"`` → ``(0.35, "#ff0000")``; a bare colour has no position."""
    colour, _, pos = str(entry).partition("@")
    return (float(pos) if pos else None), colour


def preset_stops(entries: List[str]) -> List[Tuple[float, str]]:
    """Turn preset entries into ``(position, colour)`` pairs, spacing bare colours evenly."""
    parsed = [split_stop(e) for e in entries]
    n = len(parsed)
    return [(p if p is not None else i / (n - 1), c) for i, (p, c) in enumerate(parsed)]


def format_stop(pos: float, colour: str) -> str:
    return f"{colour}@{pos:.3f}"


def _valid(entry) -> bool:
    try:
        _, colour = split_stop(entry)
        parse_color(colour)
        return True
    except ValueError:
        return False


def save_user_presets(presets: Dict[str, List[str]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")
