import pytest

from ephew.modes import (
    DEFAULT,
    MODES,
    OVERRIDE_FLAGS,
    all_names,
    find_by_name,
    next_mode,
)


def test_modes_is_tuple():
    assert isinstance(MODES, tuple)


def test_default_is_none_at_index_zero():
    assert DEFAULT.name == "none"
    assert DEFAULT.directive is None
    assert DEFAULT is MODES[0]


def test_cycle_order():
    assert tuple(m.name for m in MODES) == (
        "none",
        "concise",
        "paragraph",
        "verbose",
        "table",
    )


def test_all_names_unique():
    names = [m.name for m in MODES]
    assert len(set(names)) == len(names)


def test_non_none_modes_have_directives():
    for m in MODES:
        if m.name == "none":
            continue
        assert m.directive, f"mode {m.name!r} has empty directive"


def test_non_none_modes_have_marker_instruction():
    for m in MODES:
        if m.name == "none":
            continue
        assert m.marker_instruction, f"mode {m.name!r} has empty marker_instruction"


def test_none_mode_has_no_directive_or_marker():
    none = find_by_name("none")
    assert none.directive is None
    assert none.marker_instruction == ""


def test_all_modes_have_display_and_glyph():
    for m in MODES:
        assert m.display, f"mode {m.name!r} has empty display"
        assert m.glyph, f"mode {m.name!r} has empty glyph"


def test_glyphs_are_unique():
    glyphs = [m.glyph for m in MODES]
    assert len(set(glyphs)) == len(glyphs)


def test_glyph_values():
    by_name = {m.name: m.glyph for m in MODES}
    assert by_name == {
        "none": "-x",
        "concise": "-c",
        "paragraph": "-p",
        "verbose": "-v",
        "table": "-t",
    }


def test_marker_payloads():
    by_name = {m.name: m.marker_instruction for m in MODES if m.marker_instruction}
    assert "(ephew-c)" in by_name["concise"]
    assert "(ephew-p)" in by_name["paragraph"]
    assert "(ephew-v)" in by_name["verbose"]
    assert "(ephew-t)" in by_name["table"]


def test_next_mode_cycles_in_order():
    for i in range(len(MODES) - 1):
        assert next_mode(MODES[i]) is MODES[i + 1]


def test_next_mode_wraps_table_to_none():
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


def test_override_flags_short_and_long():
    assert OVERRIDE_FLAGS["-x"] == "none"
    assert OVERRIDE_FLAGS["--none"] == "none"
    assert OVERRIDE_FLAGS["-c"] == "concise"
    assert OVERRIDE_FLAGS["--concise"] == "concise"
    assert OVERRIDE_FLAGS["-p"] == "paragraph"
    assert OVERRIDE_FLAGS["--paragraph"] == "paragraph"
    assert OVERRIDE_FLAGS["-v"] == "verbose"
    assert OVERRIDE_FLAGS["--verbose"] == "verbose"
    assert OVERRIDE_FLAGS["-t"] == "table"
    assert OVERRIDE_FLAGS["--table"] == "table"


def test_override_flags_cover_every_mode():
    targets = set(OVERRIDE_FLAGS.values())
    assert targets == {m.name for m in MODES}
