# spec-activity.md — Proxy activity notifier

## Purpose

Give the user immediate visual confirmation that ephew is in the request path. Without this, when you type `claude "..."`, you see Claude's response come back but you have no idea whether it actually flowed through ephew or whether you forgot to set `ANTHROPIC_BASE_URL` and the call went direct. Even worse, if ephew is broken silently, the user can't tell.

The `ActivityNotifier` is a tiny pub/sub primitive that the proxy calls once per request; the tray subscribes and briefly flashes its menu-bar title so the user sees "yes, that just went through me."

## Public surface

Module: `ephew/activity.py`.

```python
from typing import Callable

Listener = Callable[[], None]

class ActivityNotifier:
    def __init__(self) -> None: ...
    def subscribe(self, callback: Listener) -> None:
        """Register a no-arg callback that fires on every pulse()."""
    def pulse(self) -> None:
        """Notify all subscribers. Called once per inbound request by the proxy."""
```

Invariants:
- `pulse()` is non-blocking from the caller's perspective — it iterates subscribers synchronously but exceptions in any subscriber are caught and logged at WARNING; they never propagate back to the proxy.
- Listeners are called on whatever thread invoked `pulse()` (typically the proxy's asyncio thread). UI listeners are responsible for marshalling to the main thread themselves.
- Thread-safe: subscribe/pulse can interleave from multiple threads without corruption.

## Behavior

- `subscribe(cb)` appends the callback under a lock. No deduplication.
- `pulse()` snapshots the listener list under a lock, releases the lock, then invokes each listener in registration order. Exceptions are caught per-listener, logged with `log.warning("activity subscriber raised", exc_info=True)`, and do not stop subsequent listeners.

That's the whole module. No state beyond the listener list, no counters, no time tracking — those concerns belong to the consumer (e.g. the tray manages its own flash timer).

## Dependencies

Upstream: stdlib only.

Downstream:
- [spec-proxy.md](./spec-proxy.md) — `build_app` accepts an optional `activity: ActivityNotifier | None`; if present, calls `activity.pulse()` once at the top of every request.
- [spec-tray.md](./spec-tray.md) — `TrayApp` accepts an optional `activity: ActivityNotifier | None`; if present, subscribes to flash the title on each pulse.

## Out of scope

- Per-request metadata (path, status, mode). The notifier is intentionally argument-free; if the tray needs more it can read from `CurrentMode` directly.
- Counting in-flight requests (could be added later if the tray wants a "still active" indicator instead of a single flash).
- Persistence / replay — pulses are fire-and-forget; missed events are gone.
- Async listeners — listeners are plain callables, run synchronously.

## Verification

Unit tests (`tests/test_activity.py`):
- `subscribe` + `pulse` — registered listener is called exactly once per pulse.
- Multiple subscribers fire in registration order.
- Listener that raises does not block subsequent listeners and does not propagate.
- 100 pulses across 4 threads produce 100 calls per listener (no lost or duplicated pulses).
- `pulse()` with zero subscribers is a no-op (no error).
