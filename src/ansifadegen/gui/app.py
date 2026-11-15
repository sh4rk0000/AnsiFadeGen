"""Main window."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from ..colors import parse_color, rgb_to_hex
from ..engine import MODES, SPACES, Grid, compute_grid, iter_runs, prepare_lines
from ..export import FORMATS, ExportError, render
from ..presets import BUILTIN_PRESETS, format_stop, load_user_presets, save_user_presets
from . import theme
from .widgets import GradientEditor, PresetGrid, ask_color

SAMPLE = """\
███████  █████  ██████  ███████
██      ██   ██ ██   ██ ██
█████   ███████ ██   ██ █████
██      ██   ██ ██   ██ ██
██      ██   ██ ██████  ███████"""

ARROWS = (
    ("→", 0), ("↘", 45), ("↓", 90), ("↙", 135),
    ("←", 180), ("↖", 225), ("↑", 270), ("↗", 315),
)  # fmt: skip
SPACE_LABELS = {"sRGB": "srgb", "Linear": "linear", "OKLab": "oklab"}
FORMAT_LABELS = {f.label: f.key for f in FORMATS.values()}
MAX_PREVIEW_RUNS = 2500  # Tk's Text widget gets very slow beyond a few thousand tagged segments
HINT = "Type or paste some text, or press “Sample”, to see your gradient here."


def _simplify_runs(rows, limit: int = MAX_PREVIEW_RUNS):
    """Merge near-identical colours until the preview has at most ``limit`` runs.

    Only the on-screen preview is simplified (colours snapped to a coarser grid);
    copies and exports always use the exact colours. Returns ``(rows, step)``.
    """
    step = 1
    while sum(len(r) for r in rows) > limit and step < 64:
        step *= 2
        half = step // 2
        merged_rows = []
        for row in rows:
            out = []
            for color, text, col, n in row:
                if color is not None:
                    color = tuple(min(255, (v // step) * step + half) for v in color)
                if out and out[-1][0] == color:
                    pc, ptext, pcol, pn = out[-1]
                    out[-1] = (pc, ptext + text, pcol, pn + n)
                else:
                    out.append((color, text, col, n))
            merged_rows.append(out)
        rows = merged_rows
    return rows, step


def _section(parent, title: str) -> ctk.CTkFrame:
    card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=12)
    card.pack(fill="x", padx=2, pady=(0, 10))
    ctk.CTkLabel(
        card, text=title.upper(), anchor="w", text_color=theme.MUTED,
        font=ctk.CTkFont(size=11, weight="bold"),
    ).pack(fill="x", padx=14, pady=(12, 6))  # fmt: skip
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.pack(fill="x", padx=12, pady=(0, 12))
    return body


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=theme.BG)
        self.title("AnsiFadeGen")
        self.geometry("1220x780")
        self.minsize(1000, 640)

        self.mono = ctk.CTkFont(family=theme.mono_family(), size=14)
        self.user_presets = load_user_presets()
        self._job: Optional[str] = None
        self._grid: Optional[Grid] = None
        self._tags: set = set()
        self._flash_job: Optional[str] = None
        self._simplified = False

        self.var_mode = tk.StringVar(value="linear")
        self.var_angle = tk.DoubleVar(value=45)
        self.var_aspect = tk.DoubleVar(value=2.0)
        self.var_reverse = tk.BooleanVar(value=False)
        self.var_use_bg = tk.BooleanVar(value=False)
        self.var_escaped = tk.BooleanVar(value=True)
        self.bg_hex = "#101018"

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self._bind_shortcuts()

        self.input.insert("1.0", SAMPLE)  # the editor already starts on the "Neon" stops
        self._schedule()

    # ------------------------------------------------------------------ sidebar
    def _build_sidebar(self) -> None:
        side = ctk.CTkScrollableFrame(
            self, width=330, fg_color=theme.PANEL, corner_radius=0,
            scrollbar_button_color=theme.BORDER, scrollbar_button_hover_color=theme.MUTED,
        )  # fmt: skip
        side.grid(row=0, column=0, sticky="nsew")

        head = ctk.CTkFrame(side, fg_color="transparent")
        head.pack(fill="x", pady=(6, 14))
        ctk.CTkLabel(
            head, text="◐ AnsiFadeGen", anchor="w", text_color=theme.TEXT,
            font=ctk.CTkFont(size=21, weight="bold"),
        ).pack(fill="x", padx=4)  # fmt: skip
        ctk.CTkLabel(
            head, text="Colour gradients for text & ASCII art", anchor="w",
            text_color=theme.MUTED, font=ctk.CTkFont(size=12),
        ).pack(fill="x", padx=4)  # fmt: skip

        # Gradient
        body = _section(side, "Gradient")
        self.editor = GradientEditor(body, on_change=self._schedule)
        self.editor.pack(fill="x")
        ctk.CTkLabel(
            body, text="Click the bar to add a stop · drag to move · double-click to recolour",
            anchor="w", text_color=theme.MUTED, font=ctk.CTkFont(size=10), wraplength=290,
            justify="left",
        ).pack(fill="x", pady=(4, 0))  # fmt: skip

        # Presets
        body = _section(side, "Presets")
        self.presets = PresetGrid(body, self._apply_preset, self._delete_preset)
        self.presets.pack(fill="x")
        ctk.CTkButton(
            body, text="＋  Save current as preset", height=30, fg_color="transparent",
            border_width=1, border_color=theme.BORDER, hover_color=theme.CARD_HOVER,
            text_color=theme.TEXT, command=self._save_preset,
        ).pack(fill="x", padx=3, pady=(8, 0))  # fmt: skip
        self._refresh_presets()

        # Direction
        body = _section(side, "Direction")
        self.seg_mode = ctk.CTkSegmentedButton(
            body, values=["Linear", "Radial"], command=self._mode_changed,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.CARD_HOVER, unselected_hover_color=theme.BORDER,
            fg_color=theme.CARD_HOVER,
        )  # fmt: skip
        self.seg_mode.set("Linear")
        self.seg_mode.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="Angle", text_color=theme.TEXT).pack(side="left")
        self.lbl_angle = ctk.CTkLabel(row, text="45°", text_color=theme.ACCENT)
        self.lbl_angle.pack(side="right")
        self.sld_angle = ctk.CTkSlider(
            body, from_=0, to=360, number_of_steps=360, variable=self.var_angle,
            progress_color=theme.ACCENT, button_color=theme.TEXT,
            button_hover_color=theme.TEXT, command=lambda _v: self._angle_changed(),
        )  # fmt: skip
        self.sld_angle.pack(fill="x", pady=(4, 8))

        pad = ctk.CTkFrame(body, fg_color="transparent")
        pad.pack(fill="x")
        self.arrow_btns = []
        for i, (glyph, deg) in enumerate(ARROWS):
            pad.grid_columnconfigure(i, weight=1)
            b = ctk.CTkButton(
                pad, text=glyph, width=30, height=30, corner_radius=8,
                fg_color=theme.CARD_HOVER, hover_color=theme.BORDER,
                command=lambda d=deg: self._set_angle(d),
            )  # fmt: skip
            b.grid(row=0, column=i, padx=1)
            self.arrow_btns.append(b)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(12, 0))
        ctk.CTkSwitch(
            row, text="Reverse", variable=self.var_reverse, progress_color=theme.ACCENT,
            command=self._schedule,
        ).pack(side="left")  # fmt: skip

        # Quality
        body = _section(side, "Colour blending")
        self.seg_space = ctk.CTkSegmentedButton(
            body, values=list(SPACE_LABELS), command=self._space_changed,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.CARD_HOVER, unselected_hover_color=theme.BORDER,
            fg_color=theme.CARD_HOVER,
        )  # fmt: skip
        self.seg_space.set("sRGB")
        self.seg_space.pack(fill="x")
        ctk.CTkLabel(
            body, text="OKLab gives smoother, perceptually even transitions.", anchor="w",
            text_color=theme.MUTED, font=ctk.CTkFont(size=10), wraplength=290, justify="left",
        ).pack(fill="x", pady=(4, 10))  # fmt: skip

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="Cell ratio (height / width)", text_color=theme.TEXT).pack(
            side="left"
        )
        self.lbl_aspect = ctk.CTkLabel(row, text="2.0", text_color=theme.ACCENT)
        self.lbl_aspect.pack(side="right")
        ctk.CTkSlider(
            body, from_=1.0, to=3.0, number_of_steps=20, variable=self.var_aspect,
            progress_color=theme.ACCENT, button_color=theme.TEXT, button_hover_color=theme.TEXT,
            command=lambda v: (self.lbl_aspect.configure(text=f"{float(v):.1f}"), self._schedule()),
        ).pack(fill="x", pady=(4, 0))  # fmt: skip

        # Background
        body = _section(side, "Background")
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkSwitch(
            row, text="Solid background", variable=self.var_use_bg,
            progress_color=theme.ACCENT, command=self._schedule,
        ).pack(side="left")  # fmt: skip
        self.btn_bg = ctk.CTkButton(
            row, text="", width=34, height=26, corner_radius=8, border_width=2,
            border_color=theme.BORDER, fg_color=self.bg_hex, hover_color=self.bg_hex,
            command=self._pick_bg,
        )  # fmt: skip
        self.btn_bg.pack(side="right")

    # ------------------------------------------------------------------ main area
    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=18, pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            bar, text="TEXT", text_color=theme.MUTED, font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left")  # fmt: skip
        buttons = (("Clear", self._clear), ("Sample", self._sample), ("Open…", self.open_file))
        for text, cmd in buttons:
            ctk.CTkButton(
                bar, text=text, width=70, height=28, fg_color=theme.CARD,
                hover_color=theme.CARD_HOVER, command=cmd,
            ).pack(side="right", padx=(6, 0))  # fmt: skip

        self.input = ctk.CTkTextbox(
            main, height=150, font=self.mono, fg_color=theme.CARD, text_color=theme.TEXT,
            corner_radius=10, wrap="none", border_width=1, border_color=theme.BORDER,
        )  # fmt: skip
        self.input.grid(row=1, column=0, sticky="ew", pady=(6, 14))
        self.input._textbox.bind("<<Modified>>", self._on_modified)

        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(
            bar, text="OUTPUT", text_color=theme.MUTED, font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left")  # fmt: skip
        self.sld_zoom = ctk.CTkSlider(
            bar, from_=8, to=28, number_of_steps=20, width=110, progress_color=theme.BORDER,
            button_color=theme.MUTED, button_hover_color=theme.TEXT,
            command=lambda v: self.mono.configure(size=int(v)),
        )  # fmt: skip
        self.sld_zoom.set(14)
        self.sld_zoom.pack(side="right")
        ctk.CTkLabel(bar, text="Zoom", text_color=theme.MUTED, font=ctk.CTkFont(size=11)).pack(
            side="right", padx=8
        )

        self.tabs = ctk.CTkTabview(
            main, fg_color=theme.CARD, corner_radius=12,
            segmented_button_fg_color=theme.CARD_HOVER,
            segmented_button_selected_color=theme.ACCENT,
            segmented_button_selected_hover_color=theme.ACCENT_HOVER,
            segmented_button_unselected_color=theme.CARD_HOVER,
            segmented_button_unselected_hover_color=theme.BORDER,
        )  # fmt: skip
        self.tabs.grid(row=3, column=0, sticky="nsew", pady=(2, 12))
        tab_prev, tab_code = self.tabs.add("Preview"), self.tabs.add("Code")

        self.preview = ctk.CTkTextbox(
            tab_prev, font=self.mono, fg_color=theme.PREVIEW_BG, text_color=theme.TEXT,
            corner_radius=8, wrap="none", activate_scrollbars=True,
        )  # fmt: skip
        self.preview.pack(fill="both", expand=True)
        self.preview.tag_config("hint", foreground=theme.MUTED)

        top = ctk.CTkFrame(tab_code, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        self.sw_escaped = ctk.CTkSwitch(
            top, text="Show escape codes as \\x1b", variable=self.var_escaped,
            progress_color=theme.ACCENT, command=self._render_code,
        )  # fmt: skip
        self.sw_escaped.pack(side="left")
        self.code = ctk.CTkTextbox(
            tab_code, font=self.mono, fg_color=theme.PREVIEW_BG, text_color="#cfcfe0",
            corner_radius=8, wrap="char",
        )  # fmt: skip
        self.code.pack(fill="both", expand=True)

        foot = ctk.CTkFrame(main, fg_color="transparent")
        foot.grid(row=4, column=0, sticky="ew")
        self.var_format = tk.StringVar(value=FORMATS["ansi"].label)
        ctk.CTkOptionMenu(
            foot, values=list(FORMAT_LABELS), variable=self.var_format, width=190, height=34,
            fg_color=theme.CARD, button_color=theme.CARD_HOVER, button_hover_color=theme.BORDER,
            dropdown_fg_color=theme.CARD, dropdown_hover_color=theme.CARD_HOVER,
            command=lambda _v: self._format_changed(),
        ).pack(side="left")  # fmt: skip
        self.lbl_status = ctk.CTkLabel(
            foot, text="", text_color=theme.MUTED, font=ctk.CTkFont(size=12)
        )
        self.lbl_status.pack(side="left", padx=14)
        self.btn_save = ctk.CTkButton(
            foot, text="Save…", width=96, height=34, fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, command=self.save_file,
        )  # fmt: skip
        self.btn_save.pack(side="right")
        self.btn_copy = ctk.CTkButton(
            foot, text="Copy", width=96, height=34, fg_color=theme.CARD,
            hover_color=theme.CARD_HOVER, command=self.copy_output,
        )  # fmt: skip
        self.btn_copy.pack(side="right", padx=8)

    def _bind_shortcuts(self) -> None:
        for seq, fn in (
            ("<Control-o>", self.open_file),
            ("<Control-s>", self.save_file),
            ("<Control-Shift-C>", self.copy_output),
        ):
            for widget in (self, self.input._textbox):
                widget.bind(seq, lambda _e, f=fn: (f(), "break")[1])

    # ------------------------------------------------------------------ state changes
    def _schedule(self, *_args) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(30, self._refresh)

    def _on_modified(self, _e=None) -> None:
        if self.input._textbox.edit_modified():
            self.input._textbox.edit_modified(False)
            self._schedule()

    def _mode_changed(self, value: str) -> None:
        self.var_mode.set(value.lower())
        radial = value == "Radial"
        self.sld_angle.configure(
            state="disabled" if radial else "normal",
            progress_color=theme.BORDER if radial else theme.ACCENT,
            button_color=theme.MUTED if radial else theme.TEXT,
        )
        self.lbl_angle.configure(text_color=theme.MUTED if radial else theme.ACCENT)
        for b in self.arrow_btns:
            b.configure(state="disabled" if value == "Radial" else "normal")
        self._schedule()

    def _angle_changed(self) -> None:
        self.lbl_angle.configure(text=f"{int(self.var_angle.get())}°")
        self._schedule()

    def _set_angle(self, deg: float) -> None:
        self.var_angle.set(deg)
        self._angle_changed()

    def _space_changed(self, label: str) -> None:
        self.editor.set_space(SPACE_LABELS[label])
        self._schedule()

    def _format_changed(self) -> None:
        self._update_export_buttons()
        self._render_code()

    def _pick_bg(self) -> None:
        def live(hex_):
            self.bg_hex = hex_
            self.btn_bg.configure(fg_color=hex_, hover_color=hex_)
            self.var_use_bg.set(True)
            self._schedule()

        ask_color(self, self.bg_hex, live)

    # ------------------------------------------------------------------ presets
    def _refresh_presets(self) -> None:
        self.presets.set_presets(BUILTIN_PRESETS, self.user_presets)

    def _apply_preset(self, stops, _name=None) -> None:
        self.editor.set_stops(stops)

    def _save_preset(self) -> None:
        name = ctk.CTkInputDialog(text="Name for this preset:", title="Save preset").get_input()
        name = (name or "").strip()
        if not name:
            return
        if name in BUILTIN_PRESETS:
            messagebox.showwarning("Preset", f"“{name}” is a built-in preset; pick another name.")
            return
        self.user_presets[name] = [format_stop(p, c) for p, c in self.editor.stops]
        self._persist_presets()
        self._flash(f"Preset “{name}” saved")

    def _delete_preset(self, name: str) -> None:
        if messagebox.askyesno("Delete preset", f"Delete the preset “{name}”?"):
            self.user_presets.pop(name, None)
            self._persist_presets()

    def _persist_presets(self) -> None:
        try:
            save_user_presets(self.user_presets)
        except OSError as exc:
            messagebox.showerror("Preset", f"Could not save presets: {exc}")
        self._refresh_presets()

    # ------------------------------------------------------------------ rendering
    def _gradient_options(self):
        return dict(
            angle=self.var_angle.get(), mode=self.var_mode.get(),
            aspect=self.var_aspect.get(), reverse=self.var_reverse.get(),
        )  # fmt: skip

    def _bg(self):
        return parse_color(self.bg_hex) if self.var_use_bg.get() else None

    def _refresh(self) -> None:
        self._job = None
        lines = prepare_lines(self.input.get("1.0", "end-1c"))
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        bg = self._bg()
        self.preview.configure(fg_color=rgb_to_hex(bg) if bg else theme.PREVIEW_BG)

        if not any(line.strip() for line in lines):
            self._grid = None
            self.preview.insert("end", HINT, "hint")
            self.preview.configure(state="disabled")
            self._render_code()
            self._set_status("")
            return

        grid = compute_grid(lines, self.editor.gradient(), **self._gradient_options())
        self._grid = grid
        runs, step = _simplify_runs([list(iter_runs(row)) for row in grid.rows])
        raw = self.preview._textbox
        raw.insert("end", "\n".join("".join(r[1] for r in row) for row in runs) + "\n")
        for y, row in enumerate(runs, start=1):
            offset = 0  # Tk indexes count characters, not terminal columns
            for color, text, _col, _n in row:
                if color is not None:
                    tag = "c" + rgb_to_hex(color)
                    if tag not in self._tags:
                        raw.tag_configure(tag, foreground=rgb_to_hex(color))
                        self._tags.add(tag)
                    raw.tag_add(tag, f"{y}.{offset}", f"{y}.{offset + len(text)}")
                offset += len(text)
        self._simplified = step > 1
        self.preview.configure(state="disabled")
        self._render_code()

    def _format_key(self) -> str:
        return FORMAT_LABELS[self.var_format.get()]

    def _render_code(self) -> None:
        self._update_export_buttons()
        self.code.configure(state="normal")
        self.code.delete("1.0", "end")
        key = self._format_key()
        if self._grid is None:
            self.code.configure(state="disabled")
            return
        if not FORMATS[key].text:
            self.code.insert("end", "PNG is a binary image: use “Save…” to write it to disk.")
            self.code.configure(state="disabled")
            self._set_status(f"{self._grid.width} × {self._grid.height} cells")
            return
        data = render(self._grid, key, self._bg())
        shown = data.replace("\x1b", "\\x1b") if self.var_escaped.get() else data
        self.code.insert("end", shown)
        self.code.configure(state="disabled")
        note = " · preview simplified (exports are exact)" if self._simplified else ""
        self._set_status(
            f"{self._grid.width} × {self._grid.height} cells · {len(data):,} characters{note}"
        )

    def _update_export_buttons(self) -> None:
        is_text = FORMATS[self._format_key()].text
        self.btn_copy.configure(state="normal" if is_text and self._grid else "disabled")
        self.btn_save.configure(state="normal" if self._grid else "disabled")
        escapable = self._format_key().startswith(("ansi", "disc"))
        self.sw_escaped.configure(state="normal" if escapable else "disabled")

    def _set_status(self, text: str, color: str = theme.MUTED) -> None:
        self.lbl_status.configure(text=text, text_color=color)

    def _flash(self, text: str) -> None:
        self._set_status(text, theme.OK)
        if self._flash_job:
            self.after_cancel(self._flash_job)
        self._flash_job = self.after(2200, self._render_code)

    # ------------------------------------------------------------------ actions
    def _clear(self) -> None:
        self.input.delete("1.0", "end")
        self._schedule()

    def _sample(self) -> None:
        self.input.delete("1.0", "end")
        self.input.insert("1.0", SAMPLE)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open a text file",
            filetypes=[("Text files", "*.txt *.asc *.ans *.nfo"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            messagebox.showerror("Open", f"Could not read the file: {exc}")
            return
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)

    def copy_output(self) -> None:
        if self._grid is None or not FORMATS[self._format_key()].text:
            return
        data = render(self._grid, self._format_key(), self._bg())
        self.clipboard_clear()
        self.clipboard_append(data)
        self._flash("Copied to clipboard")

    def save_file(self) -> None:
        if self._grid is None:
            return
        fmt = FORMATS[self._format_key()]
        path = filedialog.asksaveasfilename(
            title="Save", defaultextension=fmt.ext,
            filetypes=[(fmt.label, f"*{fmt.ext}"), ("All files", "*.*")],
        )  # fmt: skip
        if not path:
            return
        try:
            data = render(self._grid, fmt.key, self._bg())
            if isinstance(data, bytes):
                with open(path, "wb") as fh:
                    fh.write(data)
            else:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(data)
        except (ExportError, OSError) as exc:
            messagebox.showerror("Save", str(exc))
            return
        self._flash(f"Saved {path}")


def run() -> int:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    App().mainloop()
    return 0


__all__ = ["App", "run", "MODES", "SPACES"]
