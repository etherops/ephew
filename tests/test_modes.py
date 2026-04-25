import pytest

from ephew.modes import (
    DEFAULT,
    MODES,
    all_names,
    find_by_name,
    next_mode,
)


def test_modes_is_tuple():
    assert isinstance(MODES, tuple)


def test_default_is_normal():
    assert DEFAULT.name == "normal"
    assert DEFAULT.directive is None
    assert DEFAULT in MODES


def test_normal_sits_in_middle_of_cycle():
    # Normal is the midpoint of the thoroughness dial — not at the beginning.
    assert MODES.index(DEFAULT) == 2
    assert MODES[0].name == "very-concise"
    assert MODES[-1].name == "table"


def test_binary_mode_removed():
    # 'binary' was folded into 'very-concise'; it should no longer exist.
    assert "binary" not in [m.name for m in MODES]
    assert len(MODES) == 6


def test_all_names_unique():
    names = [m.name for m in MODES]
    assert len(set(names)) == len(names)


def test_non_normal_modes_have_directives():
    for m in MODES:
        if m.name == "normal":
            continue
        assert m.directive, f"mode {m.name!r} has empty directive"


def test_all_modes_have_display():
    for m in MODES:
        assert m.display, f"mode {m.name!r} has empty display"


def test_all_modes_have_glyph():
    for m in MODES:
        assert m.glyph, f"mode {m.name!r} has empty glyph"
        assert 1 <= len(m.glyph) <= 3, f"mode {m.name!r} glyph must be 1-3 characters"


def test_glyphs_are_unique():
    glyphs = [m.glyph for m in MODES]
    assert len(set(glyphs)) == len(glyphs)


def test_next_mode_cycles():
    cycled = next_mode(MODES[0])
    assert cycled is MODES[1]


def test_next_mode_wraps():
    assert next_mode(MODES[-1]) is MODES[0]


def test_find_by_name_roundtrip():
    for m in MODES:
        assert find_by_name(m.name) is m


def test_find_by_name_missing_raises():
    with pytest.raises(KeyError):
        find_by_name("not-a-real-mode")


def test_all_names_in_cycle_order():
    assert all_names() == tuple(m.name for m in MODES)


def test_mode_is_frozen():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        MODES[0].name = "hacked"  # type: ignore[misc]
