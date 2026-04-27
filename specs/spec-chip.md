# spec-chip.md — Floating mode indicator

**Phase:** Dot — deferred past MVP. In MVP the tray menu's checkmark already shows the active mode, so the floating chip is additive visual polish rather than a feature gate. Lands in v1.1. See [LAUNCH.md](./LAUNCH.md).

## Purpose

A small always-on-top translucent "chip" window that sits in a screen corner showing the current mode's `display` name. Lets the user tell at a glance what mode they're in without opening the menu. Never intercepts clicks.

## Public surface

Module: `ephew/chip.py`.

```python
class ModeChip:
    def __init__(self, state: CurrentMode): ...
    def show(self) -> None:
        """Create the NSWindow and make it visible. Must be called on main thread."""
    def close(self) -> None:
        """Hide and release the window. Must be called on main thread."""
```

Invariants:
- All NSWindow operations happen on the main thread. Callers from other threads marshal via `PyObjCTools.AppHelper.callAfter`.
- The chip never intercepts mouse events (`setIgnoresMouseEvents_(True)`).
- The chip never steals focus (`canBecomeKeyWindow` returns `False`).
- The chip updates within one AppKit event-loop tick of `state.set()` / `state.cycle()`.

## Behavior

### Window

Borderless `NSWindow`:
- `styleMask = NSWindowStyleMaskBorderless`
- `level = NSStatusWindowLevel` (above normal app windows, below system alerts)
- `backgroundColor = NSColor.clearColor()`
- `opaque = False`
- `hasShadow = True`
- `ignoresMouseEvents = True`
- `collectionBehavior` includes `NSWindowCollectionBehaviorCanJoinAllSpaces` and `NSWindowCollectionBehaviorStationary` so the chip follows the user across Spaces and full-screen apps.

### Content view

An `NSVisualEffectView` (material: `NSVisualEffectMaterialHUDWindow`, state: `NSVisualEffectStateActive`) hosts a single `NSTextField`:
- Label style (non-editable, non-selectable, transparent background)
- Font: `NSFont.systemFontOfSize_weight_(13, NSFontWeightMedium)`
- Text alignment: center
- Initial string: `state.get().display`

Corner radius: 8 pt on the content view's layer.

### Geometry

- Size: 160 × 32 pt
- Position: bottom-right of the `NSScreen.mainScreen().visibleFrame()`, with a 16 pt margin from both edges
- Fixed in v1; not resizable, not draggable

### State subscription

In `show()`, after the window is created:

```python
self._state.subscribe(self._on_mode_change)
self._on_mode_change(self._state.get())  # initial paint
```

The callback:

```python
def _on_mode_change(self, new_mode: Mode) -> None:
    AppHelper.callAfter(self._textfield.setStringValue_, new_mode.display)
```

Runs on the main thread after marshalling; safe to touch the NSTextField directly.

### Visibility

Always visible in v1. No auto-hide timer, no fade animations.

### Close

`close()` calls `window.orderOut_(None)` and drops the reference. The subscription on `state` is not explicitly removed in v1 (state lives process-lifetime; see [spec-state.md](./spec-state.md)).

## Dependencies

Upstream:
- [spec-state.md](./spec-state.md) — `state.subscribe` and `state.get`
- [spec-modes.md](./spec-modes.md) — reads `mode.display`

Downstream:
- [spec-cli.md](./spec-cli.md) — constructs `ModeChip` and calls `show()` / `close()`

Third-party: `pyobjc-framework-Cocoa`.

## Out of scope

- Drag-to-reposition (user-draggable chip)
- Per-mode background colors or icons
- Multi-monitor placement logic (picks main screen only)
- Fade in / fade out animations
- Click-through preferences panel
- Auto-hide after N seconds of no mode change
- High-DPI asset tuning (system font + system blur handle retina naturally)

## Verification

UI unit tests are impractical. Verify via:

- A smoke test that `ModeChip(state)` can be constructed without crashing (no `show()` call in headless CI).
- Manual (per [spec-testing.md](./spec-testing.md)): confirm the chip appears bottom-right at launch, shows `none`, updates within ~100 ms of every mode change (hotkey and menu both), follows the user across Spaces and into full-screen apps, and never intercepts clicks on the app behind it.
