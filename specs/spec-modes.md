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
    display: str         # short label shown in chip/tray

MODES: tuple[Mode, ...]  # ordered; cycle wraps
DEFAULT: Mode            # startup mode; == MODES[0]

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
- `MODES[0].name == "normal"` and `MODES[0].directive is None`.
- Every other mode has a non-empty `directive`.
- Every mode has a unique `name`.

## Behavior

### The modes (cycle order)

| # | `name` | `display` | `directive` |
|---|---|---|---|
| 1 | `normal` | normal | *(None — passthrough)* |
| 2 | `binary` | binary | `Respond with only "yes" or "no". No explanation, no punctuation beyond the word.` |
| 3 | `very-concise` | very concise | `Respond in 1 to 5 words.` |
| 4 | `concise` | concise | `Respond in 1 sentence.` |
| 5 | `thorough` | thorough | `Give a complete, detailed explanation with reasoning and examples.` |
| 6 | `very-thorough` | very thorough | `Give an exhaustive explanation: context, reasoning, edge cases, caveats, and examples.` |
| 7 | `table` | table | `Respond as a single GitHub-flavored markdown table. No prose outside the table.` |

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
