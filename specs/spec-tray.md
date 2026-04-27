# spec-tray.md — Menu-bar UI

**Phase:** MVP — not present in Pre-MVP (passthrough proxy has no modes to display). The tray menu is the *entire* MVP UI: its checkmark shows the active mode, and clicking a mode item sets it directly — so the floating chip can be deferred to Dot. Dot release may swap the text glyph for an SF Symbol and expose the current mode in the tooltip. See [LAUNCH.md](./LAUNCH.md).

## Purpose

Render Ephew's presence in the macOS menu bar. The user sees a small icon; clicking opens a menu listing every mode (with the active one checkmarked), a separator, and a Quit item. Clicking a mode item sets that mode directly — a random-access alternative to the hotkey cycle.

## Public surface

Module: `ephew/tray.py`.

```python
import rumps

class TrayApp(rumps.App):
    def __init__(self, state: CurrentMode, on_quit: Callable[[], None]): ...
    def run(self) -> None: ...  # blocks on AppKit runloop
```

Invariants:
- `TrayApp.run()` blocks the calling thread (must be main thread) on the AppKit runloop.
- Menu items for modes are built exactly once, at construction, from `MODES` — mode list is static in v1.
- The active mode's menu item has a checkmark; all others do not. Exactly one is checked at any time.
- Clicking the Quit item invokes `on_quit()` (passed in at construction) and then calls `rumps.quit_application()` — the caller's `on_quit` is responsible for server shutdown (see [spec-cli.md](./spec-cli.md)).

## Behavior

### Icon

The menu-bar title is a single-line string of the form `"ephew {glyph}"`, set via rumps' standard `self.title` assignment. No custom image rendering.

Examples:

```
ephew -x        (none — passthrough)
ephew -c        (concise)
ephew -p        (paragraph)
ephew -v        (verbose)
ephew -t        (table)
```

The dash-letter glyphs are identical to the in-prompt override short flags (see [spec-modes.md](./spec-modes.md)) — the token the user sees in the menu bar is the token they can type at the end of a prompt to one-shot that mode.

### Activity spin

When the proxy handles a request, it calls `activity.pulse()` (see [spec-activity.md](./spec-activity.md)). The tray subscribes; on each pulse a small braille spinner character is briefly inserted between the brand and the mode glyph, walking through 10 frames at 60 ms each (~600 ms total). This is the user's at-a-glance confirmation that a Claude call actually flowed through ephew (vs. silently bypassing it because `ANTHROPIC_BASE_URL` wasn't set).

Title shape during a spin tick `f`:

```
ephew⠋ -c        (frame 0)
ephew⠙ -c        (frame 1)
... etc through ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏ ...
ephew -c         (restored after the last frame)
```

Implementation notes:

- Title swaps via `self.title = ...` only — no `NSImage` rendering, no AppKit canvas geometry. Renders cleanly in the menu-bar font alongside the brand and glyph.
- The pulse handler runs on the proxy's asyncio thread; the tray marshals onto the main thread via `AppHelper.callAfter`. Subsequent ticks are scheduled via `AppHelper.callLater(interval, …)`.
- **Concurrency.** Every pulse increments a `_spin_generation` counter and starts a fresh tick chain. Each tick checks its generation against the current; stale chains exit without touching the title. This gives clean restart-from-frame-0 semantics if pulses arrive during an in-progress spin.
- **Mode change during spin.** Each tick re-reads `state.get().glyph`, so a hotkey or menu click mid-spin shows the new glyph immediately on the next frame; the restore step also reads fresh state.

Rationale: the single-line form renders cleanly in the menu bar with the system's native font, weight, and vertical metrics. The two-line stacked form required manual `NSImage` rendering and fought with descenders, baseline alignment, and menu-bar row height. One line is visually consistent across all modes and trivially maintained.

The title updates in real time on every state change — hotkey press, menu click, programmatic `state.set()` — via the existing subscription + `AppHelper.callAfter` pathway.

Tooltip (if rumps exposes it) reflects the current mode's `display`.

### Menu layout

Default layout (no `--verbose`):

```
── Ephew ──
  ● none
  ○ concise
  ○ paragraph
  ○ verbose
  ○ table
  ─────────
  Quit
```

Under `--verbose` (see [spec-cli.md](./spec-cli.md)), each non-`none` mode's menu item is annotated with its directive text in parentheses:

```
── Ephew ──
  ● none
  ○ concise (Fewest words possible. Max one sentence.)
  ○ paragraph (2 paragraphs max, biasing to the least response needed.)
  ○ verbose (Go deep where depth helps: reasoning, tradeoffs, edge cases. Skip padding.)
  ○ table (Markdown table only, no prose.)
  ─────────
  Quit
```

Built by iterating `MODES`. Each mode's menu item label is `mode.display`, optionally suffixed with ` ({directive})` when `--verbose` is set and the mode has a directive. The `TrayApp` constructor takes a `verbose: bool = False` flag to control this at build time. The active mode's item has `state=1` (rumps' checkmark); others have `state=0`.

### Mode-click handler

Decorated with `@rumps.clicked(mode.display)` (or programmatic equivalent — rumps supports dynamic menu construction via `self.menu = [...]`). Handler calls `state.set(mode)`. The refresh comes back through the subscription below — do not toggle the checkmark inline in the click handler.

### Subscription refresh

In `__init__`, `state.subscribe(self._on_mode_change)`. The callback runs on whatever thread mutated the state; it must marshal to the main thread:

```python
def _on_mode_change(self, new_mode: Mode) -> None:
    AppHelper.callAfter(self._refresh_ui, new_mode)
```

`_refresh_ui` assigns `self.title = f"ephew {mode.glyph}"` and sets `state=1` on the new mode's menu item and `state=0` on all others. Runs on the main thread, so direct AppKit mutation is safe.

### Quit

The Quit menu item, when clicked, calls `self._on_quit()` (the callback passed in at construction) and then `rumps.quit_application()`. The `on_quit` callback is where the CLI tears down the uvicorn server and hotkey (see [spec-server.md](./spec-server.md), [spec-hotkey.md](./spec-hotkey.md)).

## Dependencies

Upstream:
- [spec-state.md](./spec-state.md) — reads and writes via `state.set` / `state.subscribe`
- [spec-modes.md](./spec-modes.md) — iterates `MODES` to build the menu

Downstream:
- [spec-cli.md](./spec-cli.md) — constructs `TrayApp` and provides `on_quit`

Third-party: `rumps`.

## Out of scope

- Icon animation, pulsing, per-mode colors
- Menu submenus or nested groups
- Custom menu-item accelerators (the cycle hotkey is in [spec-hotkey.md](./spec-hotkey.md))
- Dynamic mode list (would require menu rebuild on state change; v1 list is static)
- Preferences / settings window
- About dialog

## Verification

Unit tests are limited because `rumps` wraps AppKit and is awkward to mock. Verify via:

- A smoke test that constructs `TrayApp(state, on_quit=lambda: None)` without crashing (import-only; don't call `.run()`).
- Manual (per [spec-testing.md](./spec-testing.md)): confirm on launch the menu-bar title reads `ephew -x` (none glyph), the menu lists all 5 modes in cycle order (`none` → `concise` → `paragraph` → `verbose` → `table`) with `none` checked, clicking `concise` updates both the checkmark and the title (to `ephew -c`), pressing the hotkey also updates both, Quit exits cleanly. When launched with `--verbose`, menu items for non-`none` modes are annotated with their directive in parentheses.
