# spec-state.md — Shared mode state

**Phase:** MVP — not used in Pre-MVP (no state exists in the passthrough proxy). See [LAUNCH.md](./LAUNCH.md).

## Purpose

Hold the currently active `Mode` as the single source of truth shared across the proxy thread and the UI (tray, chip, hotkey). Thread-safe reads and writes; a subscribe/notify pattern lets UI listeners update when the mode changes from anywhere.

## Public surface

Module: `ephew/state.py`.

```python
from typing import Callable

class CurrentMode:
    def __init__(self, initial: Mode): ...
    def get(self) -> Mode: ...
    def set(self, mode: Mode) -> None: ...
    def cycle(self) -> Mode:
        """Advance to next_mode(current) and notify; returns the new mode."""
    def subscribe(self, callback: Callable[[Mode], None]) -> None:
        """Register a listener. Called on every set()/cycle() that changes the mode."""
```

Invariants:
- `get()` never blocks for more than the time to acquire an uncontended lock.
- `set()` / `cycle()` only invoke listeners if the mode actually changed.
- Listeners are invoked **after** the internal lock is released — no listener can deadlock by re-entering state methods.
- Listener order is registration order; listeners are invoked sequentially on the thread that called `set()` or `cycle()`.
- Exceptions raised by a listener are caught, logged at WARNING, and do not prevent subsequent listeners from running.

## Behavior

### Construction

`CurrentMode(initial=MODES[0])` stores `initial` and initializes an empty listener list and a `threading.Lock`.

### `get()`

Acquire lock → read `_mode` → release lock → return. Never calls listeners.

### `set(mode)`

```
acquire lock
  previous = self._mode
  self._mode = mode
  changed = (previous is not mode)
  listeners_snapshot = list(self._listeners)  # copy under lock
release lock
if changed:
    for cb in listeners_snapshot:
        try: cb(mode)
        except Exception: log.warning(...)
```

Comparison is by identity (`is`) — modes are singletons from `MODES`.

### `cycle()`

Equivalent to `self.set(next_mode(self.get()))`, but with the read + write + listener snapshot inside a single lock acquisition to avoid races when two threads cycle simultaneously. Returns the new mode.

### `subscribe(callback)`

Append under lock. No deduplication — callers are expected to register exactly once.

## Dependencies

Upstream:
- [spec-modes.md](./spec-modes.md) — uses `Mode`, `next_mode`

Downstream:
- [spec-proxy.md](./spec-proxy.md) — calls `get()` per request
- [spec-tray.md](./spec-tray.md) — `subscribe`s to refresh the menu
- [spec-chip.md](./spec-chip.md) — `subscribe`s to redraw
- [spec-hotkey.md](./spec-hotkey.md) — calls `cycle()` on key press

Third-party: none.

## Out of scope

- Persistence: every process start resets to `DEFAULT` (see [spec-modes.md](./spec-modes.md))
- Per-listener unsubscription (no `unsubscribe` in v1 — listeners are all process-lifetime)
- Async listener support (`asyncio` tasks) — listeners are plain callables run synchronously
- Cross-process state sharing (single-process daemon)

## Verification

Unit tests (`tests/test_state.py`):
- `get()` returns the initial mode immediately after construction.
- `set()` to a different mode triggers subscribers; `set()` to the same mode does not.
- `cycle()` advances through `MODES` and wraps at the end.
- A subscriber that raises an exception does not prevent later subscribers from running, and the exception does not propagate out of `set()`/`cycle()`.
- Two threads calling `cycle()` 1000 times each end with the mode having been advanced exactly 2000 steps (no lost updates).
- A subscriber that calls `get()` inside its callback does not deadlock.
