# spec-transform.md — Request-body directive injection

**Phase:** MVP — not used in Pre-MVP (the proxy is passthrough-only in Pre-MVP; every path, including `/v1/messages`, forwards verbatim). Lands in MVP wired into [spec-proxy.md](./spec-proxy.md) via `state.get()`. See [LAUNCH.md](./LAUNCH.md).

## Purpose

Deterministically inject the active mode's directive into the last user message of an Anthropic `/v1/messages` request body. Pure function, no I/O, no global state — trivially unit-testable and cache-friendly. Lives inline with the user turn rather than the system prompt so Anthropic's prefix-based prompt cache is preserved across mode changes.

## Public surface

Module: `ephew/transform.py`.

```python
def apply(body: dict, mode: Mode) -> dict
```

Returns a new dict (never mutates `body` in place). For `mode.name == "normal"` (or any mode with `directive is None`), returns a deep-equal copy of the input. Safe to call with any JSON-shaped dict.

Invariants:
- Pure: no I/O, no clock, no randomness, no global reads beyond `mode`.
- Deterministic: same `(body, mode)` inputs produce byte-identical re-serialized output.
- Idempotent on `normal` mode: `apply(body, normal) == body` structurally.
- Never raises on malformed input; returns the body unchanged if the structure doesn't match what Anthropic expects.

## Behavior

### `normal` mode (directive is `None`)

Return the body unchanged (a deep copy, to preserve the pure-function contract).

### Non-normal modes

1. Walk `body.get("messages", [])` from the end, looking for the last entry with `role == "user"`.
2. If no such message exists: return body unchanged (defensive — real Anthropic clients always include at least one user message).
3. Let `content = message["content"]`:

   **a. `content` is a `str`:**
   Replace with `content + "\n\n" + mode.directive`.

   **b. `content` is a list of blocks:**
   Walk the list from the end, looking for the last block where `block.get("type") == "text"`.
   - If found: set `block["text"] = block["text"] + "\n\n" + mode.directive`.
   - If not found (e.g. image-only or tool-result-only turn): append a new block `{"type": "text", "text": mode.directive}` to the end of the list.

   **c. `content` is any other shape:**
   Return body unchanged.

4. Return the new body.

### Separator

Always `"\n\n"` between the user's real text and the directive. Two newlines give the model clear paragraph separation without requiring any markdown parsing. **No brackets, tags, or parens wrap the directive** — bare text after a blank line reads to the model as a natural user P.S., whereas `[markers]` / `<tags>` / `(parens)` look like prompt-injection syntax and trigger eval-rig resistance (see [spec-modes.md](./spec-modes.md) directive-phrasing principles).

### Serialization

Transform returns a `dict`. The proxy is responsible for re-serializing (see [spec-proxy.md](./spec-proxy.md)). Transform never calls `json.dumps` itself.

## Dependencies

Upstream (required):
- [spec-modes.md](./spec-modes.md) — takes a `Mode` instance

Downstream (consumers):
- [spec-proxy.md](./spec-proxy.md) — calls `apply` per `/v1/messages` request

Third-party: none. Pure stdlib.

## Out of scope

- Modifying the `system` field (would invalidate Anthropic's prompt cache on every mode change)
- Modifying any `assistant` message
- Modifying tool-use or tool-result blocks
- Ensuring the directive survives mid-conversation compaction (caller's responsibility)
- Multi-mode composition (no "concise + table" — modes are mutually exclusive)
- Validating that the body is well-formed Anthropic JSON; defensive-only behavior

## Verification

Unit tests (`tests/test_transform.py`). Golden-file style: build expected output per case, assert structural equality.

- String content, every non-normal mode: assert `"\n\n{directive}"` is appended to the last user message.
- Block-list content with text blocks: assert directive appended to the *last* text block (not the first, not a new one).
- Block-list content without any text block (image-only user turn): assert a new `{"type":"text","text":directive}` block is appended.
- Multiple user messages, interleaved with assistant: assert only the *last* user message is modified.
- `normal` mode on all above fixtures: assert output equals input structurally.
- Empty `messages` list: assert body returned unchanged.
- Missing `messages` key: assert body returned unchanged.
- Assert the input `body` dict is not mutated (pass the same dict twice; second call produces same result).
