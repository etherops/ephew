# spec-hotkey.md — Global shortcut

**Phase:** MVP — the headline toggle feature; not present in Pre-MVP (which is a plain passthrough proxy with no mode concept). Dot release improves the collision-detection log line and surfaces the menu-only fallback in the banner. See [LAUNCH.md](./LAUNCH.md).

## Purpose

Register a system-wide keyboard shortcut that cycles the mode without the user needing to focus any window. Critically, use the Carbon `RegisterEventHotKey` API — not `pynput` or `NSEvent.addGlobalMonitor` — so Ephew does **not** require macOS Accessibility permission. This is the reason a user can run `python -m ephew` from a fresh Terminal and never be asked to grant Terminal any broad privacy permissions.

## Public surface

Module: `ephew/hotkey.py`.

```python
class HotkeyRegistration:
    def __init__(self, state: CurrentMode): ...
    def install(self) -> bool:
        """Attempt to register the default hotkey. Return True on success, False if the shortcut
        is already claimed by another process or registration otherwise fails."""
    def uninstall(self) -> None:
        """Unregister the hotkey. Safe to call if install() failed or wasn't called."""
```

Invariants:
- `install()` must be called on the main thread (Carbon hotkey callbacks dispatch via the AppKit runloop).
- `install()` never raises on "already taken"; it logs a WARNING and returns `False`. The caller (CLI) keeps the daemon running with menu-only access in this case.
- The callback runs on the main thread.

## Behavior

### Default shortcut

`⇧⌘E` — Shift + Command + E.

Rationale: one-handed left-side reach (left pinky on Shift/Cmd, left middle finger on E). No default macOS system binding, no collision with common browser / editor bindings. "E" is a small mnemonic nod to "ephew". Hard-coded in v1; not user-configurable (see [spec-cli.md](./spec-cli.md) out-of-scope).

### Registration

Use `pyobjc-framework-Carbon`. Pseudocode:

```python
from Carbon import Events
from Carbon.CarbonEvents import RegisterEventHotKey, InstallEventHandler, ...

# Virtual keycode for E is 14 on US layout
key_code = 14
modifiers = cmdKey | shiftKey

hotkey_id = EventHotKeyID(signature=fourCharCode(b"EFEW"), id=1)
status, hotkey_ref = RegisterEventHotKey(
    key_code, modifiers, hotkey_id, GetApplicationEventTarget(), 0
)
if status != noErr:
    log.warning("hotkey unavailable (status=%d); menu-only operation", status)
    return False

# Install the handler that dispatches kEventHotKeyPressed to our callback.
InstallEventHandler(
    GetApplicationEventTarget(),
    event_handler_upp,
    [{"eventClass": kEventClassKeyboard, "eventKind": kEventHotKeyPressed}],
    user_data=self,
    out_ref=...,
)
```

### Callback

On each press, the event handler calls `state.cycle()` on the main thread. The handler returns `noErr` to consume the event so other apps don't also see it.

### Unregistration

`uninstall()` calls `UnregisterEventHotKey(hotkey_ref)` and removes the event handler. Idempotent; safe to call twice.

### Accessibility permission

Intentionally **not** used. The whole design choice of Carbon `RegisterEventHotKey` is to avoid ever prompting the user for Accessibility, because the privacy prompt on macOS attaches to the *parent process* (e.g. Terminal.app) and would grant that process broad permissions the user did not ask for. Registered hotkeys are a narrow API — the system delivers only this one shortcut to this one process — so no accessibility-level privilege is needed.

## Dependencies

Upstream:
- [spec-state.md](./spec-state.md) — calls `state.cycle()` on press

Downstream:
- [spec-cli.md](./spec-cli.md) — constructs and installs; uninstalls on quit

Third-party: `pyobjc-framework-Carbon`, `pyobjc-framework-Cocoa` (for the event-target helper).

## Out of scope

- User-configurable shortcut (v1 is hard-coded)
- Multi-shortcut support (e.g. one binding per mode — would require 7 shortcuts)
- Modifier-only triggers (e.g. "double-tap Option")
- Per-app scoping (the binding is system-wide)
- Rebinding at runtime without restart
- Fallback to `NSEvent.addGlobalMonitor` when Carbon registration fails (would require Accessibility; deliberately not offered)

## Verification

Hotkey behavior can't be unit-tested without a running event loop. Verify via:

- A smoke test that `HotkeyRegistration(state).install()` returns a bool and doesn't raise on a machine where the shortcut is already taken (simulate by registering twice; second call returns `False`).
- A test that `install()` followed by `uninstall()` is clean — no leaked event handlers.
- Manual (per [spec-testing.md](./spec-testing.md)): after `ephew` is running, press `⇧⌘E`; observe the chip and tray menu advance one step. Repeat 7 times to confirm wrap-around from `table` back to `normal`. Confirm no macOS privacy prompt appears on first launch.
