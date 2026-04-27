# spec-transform.md — Request-body directive injection

## Purpose

Deterministically inject the active mode's directive into the last user message of an Anthropic `/v1/messages` request body, and honor a per-request override flag the user can append to that message. Pure function, no I/O, no global state — trivially unit-testable and cache-friendly. Lives inline with the user turn rather than the system prompt so Anthropic's prefix-based prompt cache is preserved across mode changes.

## Public surface

Module: `ephew/transform.py`.

```python
def apply(
    body: dict,
    mode: Mode,
    include_markers: bool = True,
) -> tuple[dict, Mode, str | None]
```

Returns `(new_body, effective_mode, override_flag)`. `effective_mode` equals the input `mode` unless the last user message ended with an override flag, in which case it is the override mode and the flag has been stripped from the outgoing body. `override_flag` is the exact token the user typed (`-v`, `--verbose`, etc.) when an override fired, otherwise `None` — the proxy uses this verbatim in its log line. The body returned is always a fresh dict — never mutates `body` in place.

For an effective mode whose `directive is None` (i.e. `none`), returns a deep-equal copy of the input (modulo override-flag stripping).

Invariants:
- Pure: no I/O, no clock, no randomness, no global reads beyond `mode` and `OVERRIDE_FLAGS`.
- Deterministic: same `(body, mode, include_markers)` inputs produce byte-identical re-serialized output.
- Idempotent on `none` mode (when no override is present): `apply(body, none)[0] == body` structurally.
- Never raises on malformed input; returns the body unchanged if the structure doesn't match what Anthropic expects.

## Behavior

### Step 1 — In-prompt override detection

Before applying any directive, look at the **last user message**'s text content. If it ends with one of these tokens (after optional trailing whitespace/newlines):

| Short | Long | Mode |
|---|---|---|
| `-x` | `--none` | `none` |
| `-c` | `--concise` | `concise` |
| `-p` | `--paragraph` | `paragraph` |
| `-v` | `--verbose` | `verbose` |
| `-t` | `--table` | `table` |

…then:

1. Strip the flag and its leading whitespace (and any trailing whitespace) from the message text.
2. Set `effective_mode` to the override mode.
3. Continue with directive injection as if the user had set that mode in the tray.

Pattern (regex):

```
\s+(-x|--none|-c|--concise|-p|--paragraph|-v|--verbose|-t|--table)\s*\Z
```

The match is anchored to end-of-string. `\s+` before the flag enforces "separated by whitespace" so substrings like `"refactor-c"` or `"--verbose-mode"` (where the would-be flag is glued to other characters) do **not** trigger.

When the message content is a list of blocks, the override is detected on the **last text block's `text` field** only. Image and tool-result blocks are not inspected.

If no override is present, `effective_mode = mode` and the body's text is unchanged at this step.

### Step 2 — Directive payload

If `effective_mode.directive is None` (i.e. `none`): return `(deep_copy(body), effective_mode)` — no further changes beyond the override-strip from step 1.

Otherwise, build the payload string:

```
payload = effective_mode.directive
if include_markers and effective_mode.marker_instruction:
    payload = payload + "\n\n" + effective_mode.marker_instruction
```

### Step 3 — Inject into last user message

1. Walk `body.get("messages", [])` from the end, looking for the last entry with `role == "user"`.
2. If no such message exists: return `(deep_copy(body), effective_mode)` unchanged (defensive — real Anthropic clients always include at least one user message).
3. Let `content = message["content"]` (after the override-strip from step 1):

   **a. `content` is a `str`:**
   Replace with `content + "\n\n" + payload`.

   **b. `content` is a list of blocks:**
   Walk from the end for the last block where `block.get("type") == "text"`.
   - Found: set `block["text"] = block["text"] + "\n\n" + payload`.
   - Not found: append `{"type": "text", "text": payload}`.

   **c. Any other shape:**
   Return body unchanged (still with override-strip applied if step 1 fired).

4. Return `(new_body, effective_mode)`.

### Separator

Always `"\n\n"` between the user's real text and the directive (and between directive and marker). Two newlines give the model clear paragraph separation without requiring any markdown parsing. **No brackets, tags, or parens wrap the directive** — bare text after a blank line reads to the model as a natural user P.S., whereas `[markers]` / `<tags>` / `(parens)` look like prompt-injection syntax and trigger eval-rig resistance (see [spec-modes.md](./spec-modes.md) directive-phrasing principles).

### Serialization

Transform returns a `dict`. The proxy is responsible for re-serializing (see [spec-proxy.md](./spec-proxy.md)). Transform never calls `json.dumps` itself.

## Dependencies

Upstream (required):
- [spec-modes.md](./spec-modes.md) — takes a `Mode` and consults `OVERRIDE_FLAGS`

Downstream (consumers):
- [spec-proxy.md](./spec-proxy.md) — calls `apply` per `/v1/messages` request and logs the effective mode plus override flag

Third-party: none. Pure stdlib.

## Out of scope

- Modifying the `system` field (would invalidate Anthropic's prompt cache on every mode change)
- Modifying any `assistant` message
- Modifying tool-use or tool-result blocks
- Detecting overrides anywhere other than at the very end of the last text content
- Multi-mode composition (no "concise + table" — modes are mutually exclusive)
- Validating that the body is well-formed Anthropic JSON; defensive-only behavior

## Verification

Unit tests (`tests/test_transform.py`):

Directive injection:
- String content, every non-none mode: assert `"\n\n{directive}"` is appended to the last user message; `effective_mode` equals input mode.
- Marker on / off (`include_markers=True/False`) toggles the marker text.
- Block-list content with text blocks: directive appended to the *last* text block.
- Block-list content with no text block: a new `{"type":"text","text":payload}` block is appended.
- Multiple user messages, interleaved with assistant: only the *last* user message is modified.
- `none` mode: output equals input structurally; `effective_mode` is `none`.
- Empty `messages` list / missing `messages` key: body returned unchanged.
- Input dict is not mutated.

In-prompt override:
- Last user message ending in ` -c`, ` --concise`, ` -p`, ` --paragraph`, ` -v`, ` --verbose`, ` -t`, ` --table`, ` -x`, ` --none` swaps mode accordingly and strips the flag.
- Override fires regardless of the input `mode` (e.g. input `none` + body ending ` -v` → output uses verbose directive; input `verbose` + body ending ` -x` → output is plain passthrough).
- Trailing whitespace / newlines after the flag are tolerated and stripped.
- Substrings without leading whitespace (`"refactor-c"`, `"--verbose-mode"`) do **not** trigger the override.
- Override on a block-list content's last text block works the same way.
- Override fires with markers off and markers on (passthrough override `--none` still strips flag and produces no directive).
