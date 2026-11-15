import pytest

from ansifadegen.colors import ColorError, parse_color, parse_color_list, rgb_to_hex


def test_names_hex_and_triplets():
    assert parse_color("red") == (255, 0, 0)
    assert parse_color(" Blue ") == (0, 0, 255)
    assert parse_color("#ff8000") == (255, 128, 0)
    assert parse_color("#f80") == (255, 136, 0)
    assert parse_color("12, 34, 56") == (12, 34, 56)
    assert parse_color((1, 2, 3)) == (1, 2, 3)


@pytest.mark.parametrize("bad", ["", "nope", "#12", "#gggggg", "256,0,0", "1,2", "-1,0,0"])
def test_invalid_colors(bad):
    with pytest.raises(ColorError):
        parse_color(bad)


def test_color_list_keeps_legacy_syntax():
    assert parse_color_list("red,0,255,0,blue") == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    assert parse_color_list("#fff, black") == [(255, 255, 255), (0, 0, 0)]


@pytest.mark.parametrize("bad", ["red", "red,0,1", "red,0,1,blue", ""])
def test_color_list_errors(bad):
    with pytest.raises(ColorError):
        parse_color_list(bad)


def test_hex_roundtrip():
    assert rgb_to_hex((255, 0, 128)) == "#ff0080"
