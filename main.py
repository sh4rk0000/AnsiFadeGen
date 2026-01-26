import sys
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from gradient import PRESETS, parse_color, lerp

# === Force UTF-8 everywhere ===
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


class GradientGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ANSI Gradient Generator (Live Colors)")
        self.geometry("850x700")
        self.configure(bg="#1e1e1e")
        self._update_job = None
        self._last_ansi_text = ""

        # === Input section ===
        frm_input = tk.Frame(self, bg="#1e1e1e")
        frm_input.pack(padx=10, pady=10, fill="x")
        frm_input.columnconfigure(0, weight=1)
        frm_input.columnconfigure(1, weight=1)
        frm_input.columnconfigure(2, weight=1)

        tk.Label(frm_input, text="Text:", fg="white", bg="#1e1e1e").grid(row=0, column=0, sticky="w")
        self.txt_input = ScrolledText(
            frm_input, height=5, wrap="word",
            bg="#252526", fg="white", insertbackground="white",
            font=("Consolas", 11)
        )
        self.txt_input.grid(row=1, column=0, columnspan=7, sticky="nsew", pady=5)

        # === Colors ===
        tk.Label(frm_input, text="Colors (e.g. red,0,255,0,blue):", fg="white", bg="#1e1e1e").grid(row=2, column=0, sticky="w")
        self.ent_colors = tk.Entry(frm_input, bg="#252526", fg="white", insertbackground="white", font=("Consolas", 10))
        self.ent_colors.insert(0, "red,blue")
        self.ent_colors.grid(row=3, column=0, columnspan=3, sticky="we", pady=5)

        # === Direction ===
        tk.Label(frm_input, text="Direction:", fg="white", bg="#1e1e1e").grid(row=2, column=3, sticky="w")
        self.cmb_direction = ttk.Combobox(frm_input, values=["horizontal", "vertical", "diagonal"], state="readonly")
        self.cmb_direction.current(2)
        self.cmb_direction.grid(row=3, column=3, sticky="we", padx=5)

        # === Buttons ===
        btn_generate = ttk.Button(frm_input, text="Generate", command=self.generate)
        btn_generate.grid(row=3, column=4, padx=5, sticky="e")

        btn_export = ttk.Button(frm_input, text="Export ANSI", command=self.export)
        btn_export.grid(row=3, column=5, padx=5, sticky="e")

        btn_copy = ttk.Button(frm_input, text="Copy ANSI", command=self.copy_ansi)
        btn_copy.grid(row=3, column=6, padx=5, sticky="e")

        # === Output section ===
        tk.Label(self, text="Result (colored preview):", fg="white", bg="#1e1e1e").pack(anchor="w", padx=10)
        self.txt_output = ScrolledText(
            self, height=20, bg="#000", fg="white",
            insertbackground="white", font=("Consolas", 11)
        )
        self.txt_output.pack(padx=10, pady=5, fill="both", expand=True)

        frm_ansi_header = tk.Frame(self, bg="#1e1e1e")
        frm_ansi_header.pack(fill="x", padx=10)
        tk.Label(frm_ansi_header, text="ANSI output (copyable):", fg="white", bg="#1e1e1e").pack(side="left")
        self.var_show_escaped = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frm_ansi_header,
            text="Show escaped",
            variable=self.var_show_escaped,
            command=self._render_last_ansi,
        ).pack(side="right")

        self.txt_ansi = ScrolledText(
            self, height=8, bg="#111", fg="#ddd",
            insertbackground="white", font=("Consolas", 10)
        )
        self.txt_ansi.pack(padx=10, pady=5, fill="x", expand=False)

        # === Status + footer ===
        self.lbl_status = tk.Label(self, text="", fg="#bbb", bg="#1e1e1e", font=("Consolas", 9))
        self.lbl_status.pack(anchor="w", padx=10)

        # === Footer hint ===
        tk.Label(
            self,
            text=f"Available colors: {', '.join(PRESETS.keys())} - or use R,G,B values",
            fg="#888", bg="#1e1e1e", font=("Consolas", 9)
        ).pack(anchor="w", padx=10, pady=(0, 5))

        # Live updates
        self.txt_input.bind("<<Modified>>", self._on_text_modified)
        self.ent_colors.bind("<KeyRelease>", lambda _e: self._schedule_update())
        self.cmb_direction.bind("<<ComboboxSelected>>", lambda _e: self._schedule_update())

    # === Gradient generation and display ===
    def generate(self):
        self._update_outputs(show_errors=True)

    # === Parse color list (names + RGB) ===
    def _tokenize_colors(self):
        color_tokens = []
        temp_nums = []
        for part in self.ent_colors.get().split(","):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                temp_nums.append(part)
                if len(temp_nums) == 3:
                    color_tokens.append(",".join(temp_nums))
                    temp_nums = []
            else:
                if temp_nums:
                    return None, "Incomplete RGB color (expected R,G,B)."
                color_tokens.append(part)

        if temp_nums:
            return None, "Incomplete RGB color (expected R,G,B)."
        if len(color_tokens) < 2:
            return None, "At least two colors required for gradient."
        return color_tokens, None

    def _parse_colors(self, tokens):
        try:
            return [parse_color(c) for c in tokens], None
        except Exception as e:
            return None, str(e)

    def _set_status(self, text, color="#bbb"):
        self.lbl_status.configure(text=text, fg=color)

    def _clear_outputs(self):
        self.txt_output.delete("1.0", "end")
        self.txt_ansi.delete("1.0", "end")
        self._last_ansi_text = ""

    def _render_preview(self, lines, colors, direction):
        h = len(lines)
        w = max((len(l) for l in lines), default=0)
        self.txt_output.delete("1.0", "end")

        # Draw text line by line with colored tags
        for y, line in enumerate(lines):
            for x, ch in enumerate(line):
                if direction == "horizontal":
                    t = x / max(1, w - 1)
                elif direction == "vertical":
                    t = y / max(1, h - 1)
                else:
                    t = ((x / max(1, w - 1)) + (y / max(1, h - 1))) / 2

                seg = int(t * (len(colors) - 1))
                seg = min(seg, len(colors) - 2)
                local_t = (t * (len(colors) - 1)) - seg

                c1, c2 = colors[seg], colors[seg + 1]
                r = lerp(c1[0], c2[0], local_t)
                g = lerp(c1[1], c2[1], local_t)
                b = lerp(c1[2], c2[2], local_t)
                color_hex = f"#{r:02x}{g:02x}{b:02x}"

                tag_name = f"c_{r}_{g}_{b}"
                if tag_name not in self.txt_output.tag_names():
                    self.txt_output.tag_configure(tag_name, foreground=color_hex)
                self.txt_output.insert("end", ch, tag_name)

            self.txt_output.insert("end", "\n")

    def _render_ansi(self, ansi_text):
        self.txt_ansi.delete("1.0", "end")
        if self.var_show_escaped.get():
            visible = ansi_text.replace("\033", "\\x1b")
            self.txt_ansi.insert("end", visible)
        else:
            self.txt_ansi.insert("end", ansi_text)

    def _render_last_ansi(self):
        if self._last_ansi_text:
            self._render_ansi(self._last_ansi_text)

    def _update_outputs(self, show_errors=False):
        from gradient import generate_gradient_text
        self._update_job = None

        raw_text = self.txt_input.get("1.0", "end").rstrip("\n")
        if not raw_text.strip():
            self._clear_outputs()
            self._set_status("")
            return

        tokens, err = self._tokenize_colors()
        if err:
            self._clear_outputs()
            if show_errors:
                messagebox.showerror("Error", err)
            self._set_status(err, color="#f28b82")
            return

        colors, err = self._parse_colors(tokens)
        if err:
            self._clear_outputs()
            if show_errors:
                messagebox.showerror("Error", err)
            self._set_status(err, color="#f28b82")
            return

        direction = self.cmb_direction.get()
        lines = raw_text.splitlines()
        self._render_preview(lines, colors, direction)

        try:
            ansi_text = generate_gradient_text(lines, tokens, direction)
        except Exception as e:
            self._clear_outputs()
            if show_errors:
                messagebox.showerror("Error", str(e))
            self._set_status(str(e), color="#f28b82")
            return

        self._last_ansi_text = ansi_text
        self._render_ansi(ansi_text)
        self._set_status("OK", color="#8bc34a")

    def _schedule_update(self):
        if self._update_job is not None:
            self.after_cancel(self._update_job)
        self._update_job = self.after(200, self._update_outputs)

    def _on_text_modified(self, _event):
        if self.txt_input.edit_modified():
            self._schedule_update()
            self.txt_input.edit_modified(False)

    # === Export ANSI text ===
    def export(self):
        from gradient import generate_gradient_text
        raw_text = self.txt_input.get("1.0", "end").rstrip("\n")
        if not raw_text.strip():
            messagebox.showwarning("Warning", "Text is empty.")
            return

        direction = self.cmb_direction.get()

        try:
            lines = raw_text.splitlines()
            tokens, err = self._tokenize_colors()
            if err:
                messagebox.showerror("Error", err)
                return
            ansi_text = generate_gradient_text(lines, tokens, direction)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export ANSI text"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(ansi_text)
            messagebox.showinfo("Success", f"Exported successfully to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file: {e}")

    def copy_ansi(self):
        if not self._last_ansi_text:
            messagebox.showwarning("Warning", "Nothing to copy yet. Generate a gradient first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._last_ansi_text)
        self._set_status("ANSI copied to clipboard.", color="#8bc34a")


if __name__ == "__main__":
    app = GradientGUI()
    app.mainloop()
