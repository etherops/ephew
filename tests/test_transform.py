import copy

from ephew.modes import find_by_name
from ephew.transform import SEPARATOR, apply


def _minimal_body(content="hello"):
    return {
        "model": "claude-3-5-sonnet-latest",
        "messages": [{"role": "user", "content": content}],
    }


# ---------------------------------------------------------------------------
# Directive injection


def test_none_mode_returns_structural_copy():
    body = _minimal_body()
    out, eff, _ovr = apply(body, find_by_name("none"))
    assert out == body
    assert out is not body
    assert eff.name == "none"


def test_concise_appends_directive_to_string_content():
    body = _minimal_body("hello")
    mode = find_by_name("concise")
    out, eff, _ovr = apply(body, mode, include_markers=False)
    assert out["messages"][0]["content"] == f"hello{SEPARATOR}{mode.directive}"
    assert eff is mode


def test_verbose_appends_directive():
    body = _minimal_body("explain go channels")
    mode = find_by_name("verbose")
    out, eff, _ovr = apply(body, mode, include_markers=False)
    assert out["messages"][0]["content"].endswith(mode.directive)
    assert eff is mode


def test_table_appends_directive():
    body = _minimal_body("compare list vs tuple")
    mode = find_by_name("table")
    out, _eff, _ovr = apply(body, mode, include_markers=False)
    assert out["messages"][0]["content"].endswith(mode.directive)


def test_block_list_content_last_text_block_appended():
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "first"},
                    {"type": "image", "source": {}},
                    {"type": "text", "text": "last"},
                ],
            }
        ]
    }
    mode = find_by_name("table")
    out, _eff, _ovr = apply(body, mode, include_markers=False)
    blocks = out["messages"][0]["content"]
    assert blocks[0]["text"] == "first"
    assert blocks[2]["text"] == f"last{SEPARATOR}{mode.directive}"


def test_block_list_with_no_text_block_appends_new_block():
    body = {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "image", "source": {}}],
            }
        ]
    }
    mode = find_by_name("concise")
    out, _eff, _ovr = apply(body, mode, include_markers=False)
    blocks = out["messages"][0]["content"]
    assert len(blocks) == 2
    assert blocks[1] == {"type": "text", "text": mode.directive}


def test_multi_turn_only_modifies_last_user_message():
    body = {
        "messages": [
            {"role": "user", "content": "first user"},
            {"role": "assistant", "content": "first reply"},
            {"role": "user", "content": "second user"},
            {"role": "assistant", "content": "second reply"},
            {"role": "user", "content": "third user"},
        ]
    }
    mode = find_by_name("concise")
    out, _eff, _ovr = apply(body, mode, include_markers=False)
    assert out["messages"][0]["content"] == "first user"
    assert out["messages"][2]["content"] == "second user"
    assert out["messages"][4]["content"].endswith(mode.directive)


def test_empty_messages_returns_body_unchanged():
    body = {"messages": []}
    out, eff, _ovr = apply(body, find_by_name("concise"))
    assert out == body
    assert eff.name == "concise"


def test_missing_messages_key_returns_body_unchanged():
    body = {"model": "x"}
    out, _eff, _ovr = apply(body, find_by_name("concise"))
    assert out == body


def test_no_user_message_returns_body_unchanged():
    body = {
        "messages": [
            {"role": "assistant", "content": "only assistant"},
        ]
    }
    out, _eff, _ovr = apply(body, find_by_name("concise"))
    assert out["messages"][0]["content"] == "only assistant"


def test_does_not_mutate_input():
    body = _minimal_body("hello")
    snapshot = copy.deepcopy(body)
    apply(body, find_by_name("concise"))
    assert body == snapshot


# ---------------------------------------------------------------------------
# Markers


def test_markers_included_by_default():
    body = _minimal_body("hello")
    mode = find_by_name("concise")
    out, _eff, _ovr = apply(body, mode)
    content = out["messages"][0]["content"]
    assert mode.directive in content
    assert "(ephew-c)" in content


def test_markers_can_be_disabled():
    body = _minimal_body("hello")
    mode = find_by_name("concise")
    out, _eff, _ovr = apply(body, mode, include_markers=False)
    content = out["messages"][0]["content"]
    assert mode.directive in content
    assert "(ephew-c)" not in content


def test_marker_text_per_mode():
    cases = {
        "concise": "(ephew-c)",
        "paragraph": "(ephew-p)",
        "verbose": "(ephew-v)",
        "table": "(ephew-t)",
    }
    for mode_name, marker in cases.items():
        body = _minimal_body("hi")
        out, _eff, _ovr = apply(body, find_by_name(mode_name))
        assert marker in out["messages"][0]["content"], f"missing marker for {mode_name}"


def test_none_mode_ignores_markers_flag():
    body = _minimal_body("hi")
    out_with, _e1, _o1 = apply(body, find_by_name("none"), include_markers=True)
    out_without, _eff, _ovr = apply(body, find_by_name("none"), include_markers=False)
    assert out_with == out_without == body


# ---------------------------------------------------------------------------
# In-prompt override


def test_short_flag_swaps_mode_and_strips():
    body = _minimal_body("explain channels -v")
    out, eff, _ovr = apply(body, find_by_name("none"), include_markers=False)
    content = out["messages"][0]["content"]
    assert eff.name == "verbose"
    assert " -v" not in content
    assert content.startswith("explain channels")
    assert content.endswith(eff.directive)


def test_long_flag_swaps_mode_and_strips():
    body = _minimal_body("explain channels --table")
    out, eff, _ovr = apply(body, find_by_name("concise"), include_markers=False)
    assert eff.name == "table"
    assert "--table" not in out["messages"][0]["content"]
    assert out["messages"][0]["content"].endswith(eff.directive)


def test_override_to_none_strips_flag_and_no_directive():
    body = _minimal_body("just chat -x")
    out, eff, _ovr = apply(body, find_by_name("verbose"), include_markers=False)
    assert eff.name == "none"
    assert out["messages"][0]["content"] == "just chat"


def test_override_long_none_strips_flag():
    body = _minimal_body("just chat --none")
    out, eff, _ovr = apply(body, find_by_name("table"))
    assert eff.name == "none"
    assert out["messages"][0]["content"] == "just chat"


def test_every_short_flag():
    cases = {
        "-x": "none",
        "-c": "concise",
        "-p": "paragraph",
        "-v": "verbose",
        "-t": "table",
    }
    for flag, expected in cases.items():
        body = _minimal_body(f"prompt body {flag}")
        _, eff, _ovr = apply(body, find_by_name("none"))
        assert eff.name == expected, f"flag {flag!r} should select {expected}"


def test_every_long_flag():
    cases = {
        "--none": "none",
        "--concise": "concise",
        "--paragraph": "paragraph",
        "--verbose": "verbose",
        "--table": "table",
    }
    for flag, expected in cases.items():
        body = _minimal_body(f"prompt body {flag}")
        _, eff, _ovr = apply(body, find_by_name("none"))
        assert eff.name == expected


def test_trailing_whitespace_after_flag_tolerated():
    body = _minimal_body("hi -c   \n")
    out, eff, _ovr = apply(body, find_by_name("none"), include_markers=False)
    assert eff.name == "concise"
    content = out["messages"][0]["content"]
    assert "-c" not in content.split(eff.directive)[0]


def test_substring_does_not_trigger_override():
    body = _minimal_body("refactor-c")
    _, eff, _ovr = apply(body, find_by_name("none"))
    assert eff.name == "none"


def test_glued_long_form_does_not_trigger():
    body = _minimal_body("foo--verbose-mode")
    _, eff, _ovr = apply(body, find_by_name("none"))
    assert eff.name == "none"


def test_override_on_block_list_text_block():
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "first part"},
                    {"type": "text", "text": "second part -t"},
                ],
            }
        ]
    }
    out, eff, _ovr = apply(body, find_by_name("none"), include_markers=False)
    assert eff.name == "table"
    blocks = out["messages"][0]["content"]
    assert blocks[0]["text"] == "first part"
    assert "-t" not in blocks[1]["text"].split(eff.directive)[0]


def test_override_with_markers_on():
    body = _minimal_body("hi -v")
    out, eff, _ovr = apply(body, find_by_name("none"), include_markers=True)
    assert eff.name == "verbose"
    assert "(ephew-v)" in out["messages"][0]["content"]


def test_override_does_not_mutate_input():
    body = _minimal_body("hi -c")
    snapshot = copy.deepcopy(body)
    apply(body, find_by_name("none"))
    assert body == snapshot
