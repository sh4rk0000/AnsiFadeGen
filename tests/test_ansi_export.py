import pytest

from ansifadegen import apply_gradient
from ansifadegen.ansi import render_ansi, to_xterm256
from ansifadegen.engine import Gradient, compute_grid, strip_ansi
from ansifadegen.export import FORMATS, ExportError, render

G = Gradient.from_colors(["red", "blue"])


def grid(lines=("██  ██",), **kw):
    return compute_grid(list(lines), G, **kw)


def test_ansi_roundtrips_to_original_text():
    g = grid(("hello world", "  ██ x"))
    assert strip_ansi(render_ansi(g)) == "hello world\n  ██ x"


def test_blanks_are_not_coloured_and_output_is_compact():
    art = ("█████   █████",) * 10
    legacy = sum(len(line) for line in art) * 20  # one ~20-byte escape per character
    horizontal = render_ansi(grid(art, angle=0))
    assert len(horizontal) < legacy * 0.85  # only blanks can be saved when every column differs
    assert "m   " not in horizontal.replace("\x1b[38;2;", "")  # sanity: blanks follow a run
    # With a vertical gradient whole rows share one colour, so runs collapse massively.
    vertical = render_ansi(grid(art, angle=90))
    assert len(vertical) < legacy / 5


def test_same_colour_emits_one_code():
    g = compute_grid(["aaaa"], Gradient.from_colors(["red", "red"]))
    assert render_ansi(g).count("38;2;") == 1


def test_every_line_resets():
    out = render_ansi(grid(("a", "b")))
    assert all(line.endswith("\x1b[0m") for line in out.split("\n"))


def test_background_pads_to_rectangle():
    g = grid(("abc", "a"))
    lines = render_ansi(g, bg=(1, 2, 3)).split("\n")
    assert all(line.startswith("\x1b[48;2;1;2;3m") for line in lines)
    assert all(len(strip_ansi(line)) == 3 for line in lines)


def test_depths_use_expected_escape_families():
    g = grid(("abcdef",), angle=0)
    assert "38;5;" in render_ansi(g, "256")
    out16 = render_ansi(g, "16")
    assert "38;2;" not in out16 and "38;5;" not in out16


def test_xterm256_known_values():
    assert to_xterm256((255, 0, 0)) == 196
    assert to_xterm256((0, 0, 0)) == 16
    assert to_xterm256((255, 255, 255)) == 231
    assert 232 <= to_xterm256((128, 128, 128)) <= 255


def test_unknown_depth():
    with pytest.raises(ValueError):
        render_ansi(grid(), "4k")


def test_discord_block():
    out = render(grid(), "discord")
    assert out.startswith("```ansi\n") and out.endswith("\n```")
    assert "38;2;" not in out


def test_html_escapes_and_wraps():
    out = render(compute_grid(["<&>"], G), "html")
    assert "&lt;" in out and "&amp;" in out and "<pre>" in out


def test_svg_is_wellformed_xml():
    import xml.etree.ElementTree as ET

    root = ET.fromstring(render(compute_grid(["a<b & c"], G), "svg", (0, 0, 0)))
    assert root.tag.endswith("svg")


def test_png_signature():
    pytest.importorskip("PIL")
    data = render(grid(("█▀▄ A",)), "png", (10, 10, 10))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_unknown_format():
    with pytest.raises(ExportError):
        render(grid(), "gif")


def test_every_declared_format_renders():
    pytest.importorskip("PIL")
    for key in FORMATS:
        assert render(grid(), key)


def test_apply_gradient_helper():
    assert strip_ansi(apply_gradient("hi", ["red", "blue"])) == "hi"
