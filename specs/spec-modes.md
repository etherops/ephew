# spec-modes.md — Hard-coded modes

**Phase:** MVP — not used in Pre-MVP (which runs a pure passthrough proxy with no mode concept). The tuple, helpers, and defaults land together when transform + state + tray ship. See [LAUNCH.md](./LAUNCH.md).

## Purpose

Define the fixed set of verbosity modes available in v1. A mode pairs a stable `name` (used in logs, tray menu, chip display) with a `directive` string that the transform layer appends to the last user message. The tuple's order defines the hotkey cycle order.

## Public surface

Module: `ephew/modes.py`.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Mode:
    name: str            # stable kebab-case identifier
    directive: str | None  # None means passthrough (normal mode)
    display: str         # short label shown in menu items
    glyph: str           # short symbol (1–2 chars) shown after "fu " in the tray title

MODES: tuple[Mode, ...]  # ordered; cycle wraps
DEFAULT: Mode            # startup mode; always the mode named "normal" (MODES[2] in current order)

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
- Exactly one mode is named `"normal"` and its `directive is None`.
- `DEFAULT` is the `"normal"` mode.
- Every non-`normal` mode has a non-empty `directive`.
- Every mode has a unique `name` and a unique `glyph`.
- `"normal"` sits in the middle of the cycle (`MODES[2]` in current 6-mode ordering) so the thoroughness dial reads terse → normal → verbose as you press the hotkey.

## Behavior

### The modes (cycle order)

| # | `name` | `display` | `glyph` | `directive` |
|---|---|---|---|---|
| 1 | `very-concise` | very concise | `.` | `Yes or no if possible. Max 5 words otherwise.` |
| 2 | `concise` | concise | `..` | `One sentence.` |
| 3 | `normal` | normal | `-` | *(None — passthrough)* |
| 4 | `thorough` | thorough | `"` | `Include reasoning, tradeoffs, and an example if it helps.` |
| 5 | `very-thorough` | very thorough | `""` | `Go deep where depth helps: reasoning, tradeoffs, edge cases. Skip padding.` |
| 6 | `table` | table | `⊞` | `Markdown table only, no prose.` |

Cycle order is a thoroughness dial: least-verbose at position 1 (`very-concise`, which also handles the yes/no case when the question supports it), increasing through position 2 (`concise`), passing through `normal` at position 3, then climbing to maximum verbosity at position 5 (`very-thorough`). Position 6 (`table`) is the format outlier and sits at the end of the cycle; it wraps back to `very-concise`. Glyphs visually escalate along the dial: `.` → `..` → `-` (neutral midpoint) → `"` → `""` → `⊞`.

There is no longer a dedicated `binary` mode — yes/no responses are folded into `very-concise`, which prefers a one-word answer when the question admits one and falls back to ≤5 words otherwise. This removes a redundant cycle stop and keeps the shortest mode maximally useful.

### Directive phrasing principles

Directives must read as first-person user preference, not as instructions to an eval-harness. Modern Claude training actively resists phrases like `"give an exhaustive explanation"`, `"be comprehensive"`, `"provide a detailed analysis"` — they correlate with padding-bait in the training data, and the model is trained to reject them as sycophancy triggers. Violating this makes the directive counter-productive: Claude will either resist the directive outright (responding tersely and calling out the prompt) or comply in a visibly grudging way.

Rules of thumb for directive copy:
- **Be succinct.** Every token of directive is a token of overhead per request; aim for 2–12 words. The shorter modes (`very-concise`, `concise`, `table`) can be telegraphic without losing effect because the model already prefers brevity.
- **Avoid padding-trigger words:** `exhaustive`, `comprehensive`, `detailed`, `elaborate`, `in-depth analysis`, `leave no stone unturned`. These correlate with padding-bait in the training data and trigger anti-sycophancy resistance.
- **For thorough modes, give explicit permission to skip padding** (`"Skip padding."`, `"depth where depth helps"`). This flips the framing from "force length" to "engage depth when warranted."
- **No brackets, no tags, no parens.** The directive is appended after a `\n\n` separator with no surrounding markers (see [spec-transform.md](./spec-transform.md)). `[brackets]`, `<tags>`, or `(parens)` make the directive read like prompt-injection / eval-rig syntax, which *increases* resistance. Bare text after a paragraph break reads as a natural user P.S.

### Cycling

`next_mode(MODES[i])` returns `MODES[(i+1) % len(MODES)]`. Cycling from `table` returns to `normal`.

### Defaults

`DEFAULT = MODES[0]` (i.e. `normal`). Every process start begins in `normal` — see [spec-state.md](./spec-state.md). There is no persistence.

## Dependencies

Upstream: none. Pure stdlib.

Downstream (consumers):
- [spec-state.md](./spec-state.md) — holds a `Mode` instance
- [spec-transform.md](./spec-transform.md) — consumes `mode.directive`
- [spec-tray.md](./spec-tray.md) — iterates `MODES` to build the menu
- [spec-chip.md](./spec-chip.md) — displays `mode.display`
- [spec-cli.md](./spec-cli.md) — `--help` renders the full table

## Out of scope

- Per-mode color theming or icon glyphs
- User-defined modes or overrides (deferred to v1.x)
- Mode groups or hierarchies
- Localization (all directives are English; `display` fields are not translated)
- Dynamic reload from a config file

## Verification

Unit tests (`tests/test_modes.py`):
- `MODES` is a `tuple` and `DEFAULT is MODES[0]`.
- `MODES[0].name == "normal"` and `MODES[0].directive is None`.
- Every non-normal mode has a non-empty `directive` string.
- All `name` values are unique; all `display` values are non-empty.
- `next_mode` wraps correctly at the end of the tuple.
- `find_by_name("table") is MODES[-1]` (sanity: identity preserved).
- `find_by_name("nonexistent")` raises `KeyError`.
- `all_names()` returns names in the same order as `MODES`.
