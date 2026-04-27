# spec-modes.md — Hard-coded modes

## Purpose

Define the fixed set of verbosity modes available in v1. A mode pairs a stable `name` (used in logs, tray menu, chip display) with a `directive` string that the transform layer appends to the last user message. The tuple's order defines the hotkey cycle order.

## Public surface

Module: `ephew/modes.py`.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Mode:
    name: str               # stable kebab-case identifier
    directive: str | None   # None means passthrough (none mode)
    display: str            # short label shown in menu items
    glyph: str              # short symbol shown after "ephew " in the tray title
    marker_instruction: str = ""  # response-marker instruction the model is asked to follow

MODES: tuple[Mode, ...]  # ordered; cycle wraps
DEFAULT: Mode            # startup mode; always the mode named "none" (MODES[0])

OVERRIDE_FLAGS: dict[str, str]  # maps every short/long flag token to a mode name

def next_mode(current: Mode) -> Mode:
    """Next mode in the cycle; wraps from last back to first."""

def find_by_name(name: str) -> Mode:
    """Lookup by name; raises KeyError if unknown."""

def all_names() -> tuple[str, ...]:
    """Stable list of mode names in cycle order."""
```

Invariants:
- `Mode` is frozen and hashable.
- `MODES` is a `tuple`, not a `list` — immutable at the module level.
- Exactly one mode is named `"none"` and its `directive is None`.
- `DEFAULT` is the `"none"` mode and is `MODES[0]`.
- Every non-`none` mode has a non-empty `directive`.
- Every mode has a unique `name` and a unique `glyph`.
- `OVERRIDE_FLAGS` covers every mode (both short `-x/-c/-v/-t` and long `--none/--concise/--verbose/--table` forms map to the right mode name).

## Behavior

### The modes (cycle order)

| # | `name` | `display` | `glyph` | `directive` | response marker (when enabled) |
|---|---|---|---|---|---|
| 1 | `none` | none | `-x` | *(None — passthrough)* | *(none)* |
| 2 | `concise` | concise | `-c` | `Fewest words possible. Max one sentence.` | suffix `(ephew-c)` |
| 3 | `paragraph` | paragraph | `-p` | `2 paragraphs max, biasing to the least response needed.` | suffix `(ephew-p)` |
| 4 | `verbose` | verbose | `-v` | `Go deep where depth helps: reasoning, tradeoffs, edge cases. Skip padding.` | suffix `(ephew-v)` |
| 5 | `table` | table | `-t` | `Markdown table only, no prose.` | suffix `(ephew-t)` |

Cycle order is a deliberate ramp from no-op to most-shaped: `none` is passthrough, `concise` clamps to one sentence, `paragraph` allows a single dense paragraph, `verbose` opens full depth, `table` constrains format. Cycling from `table` returns to `none`.

The glyphs are intentionally identical to the in-prompt override short flags (`-x`, `-c`, `-v`, `-t`) — the token the user sees in the menu bar is the same token they can type at the end of a prompt to one-shot that mode. There is no symbolic glyph; the dash-letter form is the whole vocabulary.

### In-prompt override

Users can override the active mode for a single request by appending a flag token to the very end of the last user message:

| Short form | Long form | Selects mode |
|---|---|---|
| `-x` | `--none` | `none` |
| `-c` | `--concise` | `concise` |
| `-p` | `--paragraph` | `paragraph` |
| `-v` | `--verbose` | `verbose` |
| `-t` | `--table` | `table` |

The match is **strict** — the flag must be the final token of the message, separated from preceding text by whitespace, with nothing after it (trailing whitespace and newlines do not count as "after"; they are tolerated and stripped along with the flag). When matched:

1. The flag and its leading whitespace are removed from the message before forwarding.
2. The override mode's directive (and marker, when markers are on) is applied instead of the active mode's.
3. The proxy's per-request log line records `mode=<override>` and adds an `override=<flag>` field for traceability (see [spec-proxy.md](./spec-proxy.md)).

The override does **not** mutate `CurrentMode` — it is a per-request swap. The next request reverts to whatever mode the tray / hotkey says.

Detailed pattern semantics live in [spec-transform.md](./spec-transform.md).

### Response markers

Each non-`none` mode carries a **`marker_instruction`** — a short directive that asks the model to end its response with a space and then `(ephew<glyph>)`. The marker text mirrors the menu-bar glyph, so what is at the top of the screen is what shows up at the end of the response. The leading space prevents the marker from running into the response's final punctuation (e.g. `it is. (ephew-c)` rather than `it is.(ephew-c)`).

Concrete marker formats:

- **`concise`** → `(ephew-c)`
- **`paragraph`** → `(ephew-p)`
- **`verbose`** → `(ephew-v)`
- **`table`** → `(ephew-t)`

Why suffix-only? An earlier draft used prefix-and-suffix wraps on the longer modes. Modern Claude refused to comply on thoughtful queries, flagging the prefix as injection-shaped. Suffixes at the end of a response read as a footnote/tag and pass cleanly; structural wrapping at the top reads as prompt-injection and trips refusal.

Caveat: the marker depends on the model following the instruction. ~95% reliable on modern Claude. The deterministic signal that ephew handled the request remains the menu-bar glyph (see [spec-tray.md](./spec-tray.md)).

### Directive phrasing principles

Directives must read as first-person user preference, not as instructions to an eval-harness. Modern Claude training actively resists phrases like `"give an exhaustive explanation"`, `"be comprehensive"`, `"provide a detailed analysis"` — they correlate with padding-bait in the training data, and the model is trained to reject them as sycophancy triggers. Violating this makes the directive counter-productive: Claude will either resist the directive outright (responding tersely and calling out the prompt) or comply in a visibly grudging way.

Rules of thumb for directive copy:
- **Be succinct.** Every token of directive is a token of overhead per request; aim for 2–12 words.
- **Avoid padding-trigger words:** `exhaustive`, `comprehensive`, `detailed`, `elaborate`, `in-depth analysis`, `leave no stone unturned`. These correlate with padding-bait in the training data and trigger anti-sycophancy resistance.
- **For verbose mode, give explicit permission to skip padding** (`"Skip padding."`, `"depth where depth helps"`). This flips the framing from "force length" to "engage depth when warranted."
- **No brackets, no tags, no parens.** The directive is appended after a `\n\n` separator with no surrounding markers (see [spec-transform.md](./spec-transform.md)). `[brackets]`, `<tags>`, or `(parens)` make the directive read like prompt-injection / eval-rig syntax, which *increases* resistance. Bare text after a paragraph break reads as a natural user P.S.

### Cycling

`next_mode(MODES[i])` returns `MODES[(i+1) % len(MODES)]`. Cycling from `table` returns to `none`.

### Defaults

`DEFAULT = MODES[0]` (i.e. `none`). Every process start begins in `none` — see [spec-state.md](./spec-state.md). There is no persistence.

## Dependencies

Upstream: none. Pure stdlib.

Downstream (consumers):
- [spec-state.md](./spec-state.md) — holds a `Mode` instance
- [spec-transform.md](./spec-transform.md) — consumes `mode.directive` and `OVERRIDE_FLAGS`
- [spec-tray.md](./spec-tray.md) — iterates `MODES` to build the menu
- [spec-chip.md](./spec-chip.md) — displays `mode.display`
- [spec-cli.md](./spec-cli.md) — `--help` renders the full table

## Out of scope

- Per-mode color theming or icon glyphs
- User-defined modes or overrides beyond the four built-in flags
- Mode groups or hierarchies
- Localization (all directives are English; `display` fields are not translated)
- Dynamic reload from a config file

## Verification

Unit tests (`tests/test_modes.py`):
- `MODES` is a `tuple` and `DEFAULT is MODES[0]`.
- `MODES[0].name == "none"` and `MODES[0].directive is None`.
- Cycle order: `none` → `concise` → `paragraph` → `verbose` → `table` → `none`.
- Every non-none mode has a non-empty `directive` string.
- Every non-none mode has a non-empty `marker_instruction`.
- All `name` values unique; all `glyph` values unique.
- `next_mode` wraps correctly at the end of the tuple.
- `find_by_name("table") is MODES[-1]`.
- `find_by_name("nonexistent")` raises `KeyError`.
- `all_names()` returns names in cycle order.
- `OVERRIDE_FLAGS` maps `-x`, `--none`, `-c`, `--concise`, `-p`, `--paragraph`, `-v`, `--verbose`, `-t`, `--table` to the right mode names.
