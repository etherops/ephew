import copy

from ephew.modes import MODES, find_by_name
from ephew.transform import SEPARATOR, apply


def _minimal_body(content="hello"):
    return {
        "model": "claude-3-5-sonnet-latest",
        "messages": [{"role": "user", "content": content}],
    }


def test_normal_mode_returns_structural_copy():
    body = _minimal_body()
    out = apply(body, find_by_name("normal"))
    assert out == body
    assert out is not body


def test_concise_appends_directive_to_string_content():
    body = _minimal_body("hello")
    mode = find_by_name("concise")
    out = apply(body, mode)
    assert out["messages"][0]["content"] == f"hello{SEPARATOR}{mode.directive}"


def test_very_concise_handles_yes_no_case():
    body = _minimal_body("is python interpreted?")
    mode = find_by_name("very-concise")
    out = apply(body, mode)
    assert out["messages"][0]["content"].endswith(mode.directive)
    # Very-concise now carries the yes/no affordance that used to be a separate mode.
    assert "yes" in mode.directive.lower() or "no" in mode.directive.lower()


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
    out = apply(body, mode)
    blocks = out["messages"][0]["content"]
    assert blocks[0]["text"] == "first"  # untouched
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
    out = apply(body, mode)
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
    out = apply(body, mode)
    assert out["messages"][0]["content"] == "first user"
    assert out["messages"][2]["content"] == "second user"
    assert out["messages"][4]["content"].endswith(mode.directive)


def test_empty_messages_returns_body_unchanged():
    body = {"messages": []}
    out = apply(body, find_by_name("concise"))
    assert out == body


def test_missing_messages_key_returns_body_unchanged():
    body = {"model": "x"}
    out = apply(body, find_by_name("concise"))
    assert out == body


def test_no_user_message_returns_body_unchanged():
    body = {
        "messages": [
            {"role": "assistant", "content": "only assistant"},
        ]
    }
    mode = find_by_name("concise")
    out = apply(body, mode)
    # No user message to modify; original content preserved.
    assert out["messages"][0]["content"] == "only assistant"


def test_does_not_mutate_input():
    body = _minimal_body("hello")
    snapshot = copy.deepcopy(body)
    apply(body, find_by_name("concise"))
    assert body == snapshot
