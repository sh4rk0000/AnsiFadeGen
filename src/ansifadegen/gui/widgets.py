"""Custom widgets: gradient editor, colour picker dialog and preset gallery."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ..colors import ColorError, parse_color, rgb_to_hex
from ..engine import Gradient
from ..presets import preset_stops
from . import theme

SWATCHES = (
    "#ff0000", "#ff7a00", "#ffd200", "#00e676", "#00e5ff", "#2979ff",
    "#7c5cff", "#ff00cc", "#ffffff", "#9e9e9e", "#424242", "#000000",
)  # fmt: skip


def draw_gradient_bar(canvas: tk.Canvas, gradient: Gradient, x0, y0, x1, y1, step=2, tag="bar"):
    """Paint ``gradient`` left→right as thin vertical strips."""
    span = max(1, x1 - x0)
    x = x0
    while x < x1:
        t = (x - x0) / span
        canvas.create_rectangle(
            x, y0, min(x + step, x1), y1,
            fill=rgb_to_hex(gradient.at(t)), outline="", tags=tag,
        )  # fmt: skip
        x += step


# --------------------------------------------------------------------------- colour picker
class ColorPicker(ctk.CTkToplevel):
    """Small modal colour dialog: RGB sliders, hex entry, swatches, live preview."""

    def __init__(self, parent, initial: str, live: Optional[Callable[[str], None]] = None):
        super().__init__(parent, fg_color=theme.PANEL)
        self.title("Choose a colour")
        self.resizable(False, False)
        self.result: Optional[str] = None
        self._initial, self._live, self._busy = initial, live, False
        self.transient(parent)

        try:
            r, g, b = parse_color(initial)
        except ColorError:
            r, g, b = 255, 255, 255
        self._vars = [tk.IntVar(value=v) for v in (r, g, b)]

        self._swatch = ctk.CTkFrame(self, height=64, corner_radius=12, fg_color=initial)
        self._swatch.pack(fill="x", padx=18, pady=(18, 12))

        for label, var, color in zip("RGB", self._vars, ("#ff5a6e", "#46d68b", "#5a9bff")):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=3)
            ctk.CTkLabel(row, text=label, width=16, text_color=theme.MUTED).pack(side="left")
            ctk.CTkSlider(
                row, from_=0, to=255, number_of_steps=255, variable=var,
                progress_color=color, button_color=color, button_hover_color=color,
                command=lambda _v: self._from_sliders(),
            ).pack(side="left", fill="x", expand=True, padx=8)  # fmt: skip
            ctk.CTkLabel(row, textvariable=var, width=30, text_color=theme.TEXT).pack(side="left")

        hex_row = ctk.CTkFrame(self, fg_color="transparent")
        hex_row.pack(fill="x", padx=18, pady=(10, 6))
        ctk.CTkLabel(hex_row, text="Hex", text_color=theme.MUTED, width=34).pack(side="left")
        self._hex = ctk.CTkEntry(hex_row, width=110, fg_color=theme.CARD, border_color=theme.BORDER)
        self._hex.pack(side="left")
        self._hex.bind("<KeyRelease>", lambda _e: self._from_hex())

        sw_row = ctk.CTkFrame(self, fg_color="transparent")
        sw_row.pack(fill="x", padx=18, pady=8)
        for i, c in enumerate(SWATCHES):
            ctk.CTkButton(
                sw_row, text="", width=22, height=22, corner_radius=11, fg_color=c,
                hover_color=c, border_width=1, border_color=theme.BORDER,
                command=lambda c=c: self._set(parse_color(c)),
            ).grid(row=0, column=i, padx=2)  # fmt: skip

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(8, 18))
        ctk.CTkButton(
            btns, text="Cancel", width=90, fg_color=theme.CARD, hover_color=theme.CARD_HOVER,
            command=self._cancel,
        ).pack(side="left")  # fmt: skip
        ctk.CTkButton(
            btns, text="Apply", width=90, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self._apply,
        ).pack(side="right")  # fmt: skip

        self._set((r, g, b))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Return>", lambda _e: self._apply())
        self.after(80, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def _set(self, rgb, source=None):
        self._busy = True
        hex_ = rgb_to_hex(rgb)
        for var, v in zip(self._vars, rgb):
            var.set(int(v))
        if source != "hex":
            self._hex.delete(0, "end")
            self._hex.insert(0, hex_)
        self._swatch.configure(fg_color=hex_)
        self._busy = False
        if self._live:
            self._live(hex_)

    def _from_sliders(self):
        if not self._busy:
            self._set(tuple(int(v.get()) for v in self._vars))

    def _from_hex(self):
        text = self._hex.get().strip()
        if not text.startswith("#"):
            text = "#" + text
        try:
            self._set(parse_color(text), source="hex")
            self._hex.configure(border_color=theme.BORDER)
        except ColorError:
            self._hex.configure(border_color=theme.DANGER)

    def _apply(self):
        self.result = rgb_to_hex(tuple(int(v.get()) for v in self._vars))
        self.destroy()

    def _cancel(self):
        if self._live:
            self._live(self._initial)
        self.destroy()


def ask_color(parent, initial: str, live: Optional[Callable[[str], None]] = None) -> Optional[str]:
    dlg = ColorPicker(parent, initial, live)
    dlg.wait_window(dlg)
    return dlg.result


# --------------------------------------------------------------------------- gradient editor
class GradientEditor(ctk.CTkFrame):
    """A gradient bar with draggable colour stops.

    Click the bar to add a stop, drag a handle to move it, double-click (or use the
    button) to change its colour, press Delete to remove it.
    """

    PAD, BAR_TOP, BAR_H, HIT = 14, 6, 36, 12
    HANDLE_Y = BAR_TOP + BAR_H + 17

    def __init__(self, master, on_change: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self.on_change = on_change
        self.space = "srgb"
        self.stops: List[list] = [[0.0, "#ff00cc"], [0.5, "#3333ff"], [1.0, "#00ffd5"]]
        self.sel = self.stops[0]
        self._dragging = False
        self._silent = False

        self.canvas = tk.Canvas(
            self, height=self.HANDLE_Y + 22, bg=theme.CARD, highlightthickness=0, bd=0,
        )  # fmt: skip
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.pick_color())
        self.canvas.bind("<Delete>", lambda _e: self.remove_selected())
        self.canvas.bind("<BackSpace>", lambda _e: self.remove_selected())

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(2, 0))
        self._hex_var = tk.StringVar()
        self._chip = ctk.CTkButton(
            row, text="", width=30, height=30, corner_radius=8, border_width=2,
            border_color=theme.BORDER, command=self.pick_color,
        )  # fmt: skip
        self._chip.pack(side="left")
        self._hex = ctk.CTkEntry(
            row, textvariable=self._hex_var, width=92, height=30,
            fg_color=theme.CARD_HOVER, border_color=theme.BORDER,
        )  # fmt: skip
        self._hex.pack(side="left", padx=6)
        self._hex_var.trace_add("write", lambda *_: self._hex_edited())
        ctk.CTkButton(
            row, text="Remove stop", width=96, height=30, fg_color=theme.CARD_HOVER,
            hover_color=theme.BORDER, text_color=theme.TEXT, command=self.remove_selected,
        ).pack(side="right")  # fmt: skip
        self._sync_inputs()

    # ---- public API
    def gradient(self, space: Optional[str] = None) -> Gradient:
        return Gradient([(p, c) for p, c in self.stops], space or self.space)

    def set_space(self, space: str) -> None:
        self.space = space
        self._redraw()

    def set_stops(self, stops) -> None:
        self.stops = [[float(p), c] for p, c in stops]
        self.sel = self.stops[0]
        self._changed()

    def reverse(self) -> None:
        self.stops = sorted(([1.0 - p, c] for p, c in self.stops), key=lambda s: s[0])
        self.sel = self.stops[0]
        self._changed()

    def remove_selected(self) -> None:
        if len(self.stops) <= 2:
            return
        i = self.stops.index(self.sel)
        self.stops.pop(i)
        self.sel = self.stops[min(i, len(self.stops) - 1)]
        self._changed()

    def pick_color(self) -> None:
        stop = self.sel

        def live(hex_):
            stop[1] = hex_
            self._changed()

        ask_color(self.winfo_toplevel(), stop[1], live)

    # ---- geometry
    def _width(self) -> int:
        return max(self.canvas.winfo_width(), 120)

    def _x(self, pos: float) -> float:
        return self.PAD + pos * (self._width() - 2 * self.PAD)

    def _pos(self, x: float) -> float:
        return min(1.0, max(0.0, (x - self.PAD) / (self._width() - 2 * self.PAD)))

    # ---- events
    def _press(self, e):
        self.canvas.focus_set()
        hit = min(self.stops, key=lambda s: abs(self._x(s[0]) - e.x))
        near_handle = abs(self._x(hit[0]) - e.x) <= self.HIT and e.y > self.BAR_TOP + self.BAR_H - 4
        if near_handle or abs(self._x(hit[0]) - e.x) <= 6:
            self.sel = hit
        elif self.BAR_TOP <= e.y <= self.BAR_TOP + self.BAR_H:
            pos = self._pos(e.x)
            new = [pos, rgb_to_hex(self.gradient().at(pos))]
            self.stops.append(new)
            self.stops.sort(key=lambda s: s[0])
            self.sel = new
        else:
            return
        self._dragging = True
        self._changed()

    def _motion(self, e):
        if self._dragging:
            self.sel[0] = self._pos(e.x)
            self.stops.sort(key=lambda s: s[0])
            self._changed()

    def _release(self, _e):
        self._dragging = False

    def _hex_edited(self):
        if self._silent:
            return
        text = self._hex_var.get().strip()
        if not text.startswith("#"):
            text = "#" + text
        try:
            self.sel[1] = rgb_to_hex(parse_color(text))
        except ColorError:
            self._hex.configure(border_color=theme.DANGER)
            return
        self._hex.configure(border_color=theme.BORDER)
        self._changed(sync=False)

    # ---- drawing
    def _changed(self, sync: bool = True) -> None:
        self._redraw()
        if sync:
            self._sync_inputs()
        self.on_change()

    def _sync_inputs(self) -> None:
        self._silent = True
        self._hex_var.set(self.sel[1])
        self._silent = False
        self._hex.configure(border_color=theme.BORDER)
        self._chip.configure(fg_color=self.sel[1], hover_color=self.sel[1])

    def _redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        x0, x1 = self.PAD, self._width() - self.PAD
        y0, y1 = self.BAR_TOP, self.BAR_TOP + self.BAR_H
        draw_gradient_bar(c, self.gradient(), x0, y0, x1, y1)
        c.create_rectangle(x0, y0, x1, y1, outline=theme.BORDER, width=1)
        for stop in self.stops:
            x, selected = self._x(stop[0]), stop is self.sel
            c.create_line(x, y1, x, self.HANDLE_Y - 8, fill="#ffffff" if selected else theme.MUTED)
            r = 9 if selected else 7
            c.create_oval(
                x - r, self.HANDLE_Y - r, x + r, self.HANDLE_Y + r, fill=stop[1],
                outline="#ffffff" if selected else theme.BORDER, width=2,
            )  # fmt: skip


# --------------------------------------------------------------------------- preset gallery
class PresetGrid(ctk.CTkFrame):
    """Three-column gallery of gradient presets. Right-click a user preset to delete it."""

    def __init__(self, master, on_pick: Callable, on_delete: Callable[[str], None], columns=3):
        super().__init__(master, fg_color="transparent")
        self.on_pick, self.on_delete, self.columns = on_pick, on_delete, columns
        for i in range(columns):
            self.grid_columnconfigure(i, weight=1, uniform="presets")

    def set_presets(self, builtin: Dict[str, List[str]], user: Dict[str, List[str]]) -> None:
        for child in self.winfo_children():
            child.destroy()
        items = [(n, e, False) for n, e in builtin.items()]
        items += [(n, e, True) for n, e in user.items()]
        for i, (name, entries, is_user) in enumerate(items):
            self._tile(i, name, entries, is_user)

    def _tile(self, index, name, entries, is_user):
        stops = preset_stops(entries)
        grad = Gradient(stops)
        tile = ctk.CTkFrame(
            self, fg_color=theme.CARD_HOVER, corner_radius=8, border_width=1,
            border_color=theme.CARD_HOVER,
        )  # fmt: skip
        tile.grid(
            row=index // self.columns, column=index % self.columns, padx=2, pady=2, sticky="ew"
        )
        bar = tk.Canvas(tile, height=16, bg=theme.CARD_HOVER, highlightthickness=0, bd=0)
        bar.pack(fill="x", padx=5, pady=(5, 1))
        shown = (name if len(name) <= 11 else name[:10] + "…")
        label = ctk.CTkLabel(
            tile, text=("★ " if is_user else "") + shown, anchor="w", height=16,
            text_color=theme.TEXT, font=ctk.CTkFont(size=10),
        )  # fmt: skip
        label.pack(fill="x", padx=7, pady=(0, 4))

        bar.bind("<Configure>", lambda e, b=bar, g=grad: self._paint(b, g, e.width))
        for w in (tile, bar, label):
            w.bind("<Button-1>", lambda _e, n=name, s=stops: self.on_pick(s, n))
            w.bind("<Enter>", lambda _e, t=tile: t.configure(border_color=theme.ACCENT))
            w.bind("<Leave>", lambda _e, t=tile: t.configure(border_color=theme.CARD_HOVER))
            w.configure(cursor="hand2")
            if is_user:
                w.bind("<Button-3>", lambda _e, n=name: self.on_delete(n))

    @staticmethod
    def _paint(canvas: tk.Canvas, gradient: Gradient, width: int) -> None:
        canvas.delete("all")
        draw_gradient_bar(canvas, gradient, 0, 0, max(width, 2), 16, step=3)
