import pytest

from ansifadegen.engine import (
    Gradient,
    char_width,
    compute_grid,
    iter_runs,
    prepare_lines,
    strip_ansi,
)  # fmt: skip

RB = Gradient.from_colors(["red", "blue"])


def test_gradient_endpoints_are_exact_and_rounding_is_correct():
    assert RB.at(0) == (255, 0, 0) and RB.at(1) == (0, 0, 255)
    assert Gradient.from_colors([(0, 0, 0), (255, 255, 255)]).at(0.5) == (128, 128, 128)


def test_clamping_and_multi_stop_positions():
    g = Gradient([(0.0, "red"), (0.25, "lime"), (1.0, "blue")])
    assert g.at(-5) == (255, 0, 0) and g.at(9) == (0, 0, 255)
    assert g.at(0.25) == (0, 255, 0)


def test_unsorted_stops_are_sorted():
    g = Gradient([(1.0, "blue"), (0.0, "red")])
    assert g.at(0) == (255, 0, 0)


@pytest.mark.parametrize("space", ["srgb", "linear", "oklab"])
def test_all_spaces_hit_endpoints_and_stay_in_range(space):
    g = Gradient.from_colors(["yellow", "blue"], space)
    assert g.at(0) == (255, 255, 0) and g.at(1) == (0, 0, 255)
    assert all(0 <= v <= 255 for i in range(101) for v in g.at(i / 100))


def test_oklab_midpoint_differs_from_srgb_and_is_not_muddy():
    srgb = Gradient.from_colors(["yellow", "blue"], "srgb").at(0.5)
    ok = Gradient.from_colors(["yellow", "blue"], "oklab").at(0.5)
    assert srgb == (128, 128, 128) and ok != srgb


def test_needs_two_stops():
    with pytest.raises(ValueError):
        Gradient([(0, "red")])


def test_horizontal_is_monotone_and_hits_both_ends():
    grid = compute_grid(["x" * 20], RB, angle=0)
    reds = [c.color[0] for c in grid.rows[0]]
    assert reds[0] == 255 and reds[-1] == 0
    assert reds == sorted(reds, reverse=True)


def test_vertical_uses_rows():
    grid = compute_grid(["x", "x", "x"], RB, angle=90)
    assert [r[0].color for r in grid.rows] == [(255, 0, 0), (127, 0, 128), (0, 0, 255)] or (
        grid.rows[0][0].color == (255, 0, 0) and grid.rows[2][0].color == (0, 0, 255)
    )


def test_reverse_and_angle_180_agree():
    a = compute_grid(["abcdef"], RB, angle=180)
    b = compute_grid(["abcdef"], RB, angle=0, reverse=True)
    assert [c.color for c in a.rows[0]] == [c.color for c in b.rows[0]]


def test_diagonal_spans_full_range_corner_to_corner():
    grid = compute_grid(["xxxx"] * 4, RB, angle=45)
    assert grid.rows[0][0].color == (255, 0, 0) and grid.rows[3][3].color == (0, 0, 255)


def test_aspect_ratio_changes_diagonal():
    a = compute_grid(["xxxxxx"] * 3, RB, angle=45, aspect=1.0)
    b = compute_grid(["xxxxxx"] * 3, RB, angle=45, aspect=2.0)
    assert a.rows[2][0].color != b.rows[2][0].color


def test_radial_centre_is_start_and_corner_is_end():
    grid = compute_grid(["xxx"] * 3, RB, mode="radial", aspect=1.0)
    assert grid.rows[1][1].color == (255, 0, 0) and grid.rows[0][0].color == (0, 0, 255)


def test_blanks_get_no_colour_and_do_not_split_runs():
    grid = compute_grid(["a  b"], Gradient.from_colors(["red", "red"]))
    assert [c.color is None for c in grid.rows[0]] == [False, True, True, False]
    assert len(list(iter_runs(grid.rows[0]))) == 1


def test_degenerate_inputs_do_not_crash():
    assert compute_grid([], RB).rows == []
    assert compute_grid(["x"], RB, angle=90).rows[0][0].color == (255, 0, 0)
    assert compute_grid(["x"], RB, mode="radial").rows[0][0].color == (255, 0, 0)


def test_strip_ansi_and_input_with_existing_colours():
    src = "\x1b[31mHELLO\x1b[0m"
    assert strip_ansi(src) == "HELLO"
    assert prepare_lines(src) == ["HELLO"]
    assert compute_grid(prepare_lines(src), RB).width == 5


def test_wide_chars_and_combining_marks():
    assert char_width("日") == 2 and char_width("a") == 1 and char_width("́") == 0
    grid = compute_grid(["日本a"], RB, angle=0)
    assert grid.width == 5 and [c.col for c in grid.rows[0]] == [0, 2, 4]
    combined = compute_grid(["éx"], RB, angle=0).rows[0]
    assert combined[1].color == combined[0].color and combined[2].col == 1


def test_tabs_are_expanded():
    assert prepare_lines("a\tb") == ["a   b"]


def test_bad_arguments():
    with pytest.raises(ValueError):
        compute_grid(["x"], RB, mode="spiral")
    with pytest.raises(ValueError):
        compute_grid(["x"], RB, aspect=0)
