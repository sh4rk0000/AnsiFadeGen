"""GUI smoke tests. Skipped when Tk/CustomTkinter or a display is unavailable.

On a headless machine run:  xvfb-run -a pytest
"""

import time

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("cfg")))
    mp.setenv("APPDATA", str(tmp_path_factory.mktemp("appdata")))
    from ansifadegen.gui.app import App

    try:
        a = App()
    except tk.TclError:
        mp.undo()
        pytest.skip("no display available")
    a.geometry("1220x780")
    a.update()
    a._refresh()
    yield a
    a.destroy()
    mp.undo()


def click(canvas, x, y, name="<ButtonPress-1>"):
    canvas.event_generate(name, x=int(x), y=int(y))
    canvas.update()


def test_initial_render(app):
    assert app._grid is not None and app._grid.height == 5
    shown = app.preview.get("1.0", "end-1c").rstrip("\n").splitlines()
    assert shown == app.input.get("1.0", "end-1c").splitlines()


def test_preview_and_code_match_engine(app):
    from ansifadegen.export import render

    key = app._format_key()
    shown = app.code.get("1.0", "end-1c").replace("\\x1b", "\x1b")
    assert render(app._grid, key, app._bg()) == shown


def test_editor_add_drag_remove_stops(app):
    ed, c = app.editor, app.editor.canvas
    n = len(ed.stops)
    click(c, ed._x(0.25), ed.BAR_TOP + 10)  # click on the bar → new stop
    assert len(ed.stops) == n + 1 and abs(ed.sel[0] - 0.25) < 0.02
    y = ed.HANDLE_Y
    click(c, ed._x(0.25), y)
    click(c, ed._x(0.30), y, "<B1-Motion>")
    click(c, ed._x(0.30), y, "<ButtonRelease-1>")
    assert abs(ed.sel[0] - 0.30) < 0.02
    assert [s[0] for s in ed.stops] == sorted(s[0] for s in ed.stops)
    ed.remove_selected()
    assert len(ed.stops) == n
    while len(ed.stops) > 2:
        ed.remove_selected()
    ed.remove_selected()
    assert len(ed.stops) == 2  # never fewer than two stops


def test_hex_entry_updates_selected_stop(app):
    ed = app.editor
    ed._hex_var.set("#123456")
    assert ed.sel[1] == "#123456"
    ed._hex_var.set("#zzz")  # invalid input is ignored, not applied
    assert ed.sel[1] == "#123456"


def test_preset_applies_and_reversal_works(app):
    from ansifadegen.presets import BUILTIN_PRESETS, preset_stops

    app._apply_preset(preset_stops(BUILTIN_PRESETS["Rainbow"]))
    assert len(app.editor.stops) == 6
    first = app.editor.stops[0][1]
    app.editor.reverse()
    assert app.editor.stops[-1][1] == first


def test_radial_mode_disables_angle_controls(app):
    app._mode_changed("Radial")
    assert app.sld_angle.cget("state") == "disabled"
    app._mode_changed("Linear")
    assert app.sld_angle.cget("state") == "normal"


def test_png_format_disables_copy_but_not_save(app):
    app.var_format.set("PNG image")
    app._format_changed()
    assert app.btn_copy.cget("state") == "disabled" and app.btn_save.cget("state") == "normal"
    app.var_format.set("HTML")
    app._format_changed()
    assert app.btn_copy.cget("state") == "normal"
    assert "<pre>" in app.code.get("1.0", "end-1c")


def test_empty_input_shows_hint_and_disables_actions(app):
    app.input.delete("1.0", "end")
    app._refresh()
    assert app._grid is None and "Type or paste" in app.preview.get("1.0", "end-1c")
    assert app.btn_save.cget("state") == "disabled"
    app._sample()
    app._refresh()
    assert app._grid is not None


def test_large_input_renders_fast(app):
    art = "\n".join("█▀▄ " * 75 for _ in range(80))  # 300 × 80 cells
    app.input.delete("1.0", "end")
    app.input.insert("1.0", art)
    t0 = time.perf_counter()
    app._refresh()
    assert time.perf_counter() - t0 < 4.0


def test_user_presets_roundtrip(app):
    from ansifadegen.presets import format_stop, load_user_presets, preset_stops

    app.user_presets["Mine"] = [format_stop(0.0, "#ff0000"), format_stop(0.3, "#00ff00"),
                                format_stop(1.0, "#0000ff")]  # fmt: skip
    app._persist_presets()
    loaded = load_user_presets()
    assert preset_stops(loaded["Mine"]) == [(0.0, "#ff0000"), (0.3, "#00ff00"), (1.0, "#0000ff")]


def test_simplify_runs_caps_segments_and_keeps_text():
    from ansifadegen.gui.app import _simplify_runs

    row = [((i, 0, 0), "x", i, 1) for i in range(200)]  # 200 distinct colours
    rows, step = _simplify_runs([row], limit=20)
    assert step > 1 and len(rows[0]) <= 20
    assert "".join(r[1] for r in rows[0]) == "x" * 200
    assert sum(r[3] for r in rows[0]) == 200  # column widths preserved
    same, step = _simplify_runs([row], limit=500)
    assert step == 1 and same == [row]  # small inputs are left exact
