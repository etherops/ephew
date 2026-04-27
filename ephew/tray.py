from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import rumps
from PyObjCTools import AppHelper

from ephew.activity import ActivityNotifier
from ephew.modes import MODES, Mode
from ephew.state import CurrentMode

log = logging.getLogger("ephew.tray")

_BRAND = "ephew"

# Braille spinner: 10 frames at 60 ms each = ~600 ms per pulse. Renders cleanly in
# the menu-bar font (no NSImage / coordinate-space gymnastics) and stays readable
# alongside the brand and mode glyph.
_SPIN_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_SPIN_INTERVAL_SECS = 0.06


def _title_for(mode: Mode) -> str:
    return f"{_BRAND} {mode.glyph}"


def _spin_title(mode: Mode, frame: str) -> str:
    return f"{_BRAND}{frame} {mode.glyph}"


def _menu_label(mode: Mode, verbose: bool) -> str:
    if verbose and mode.directive:
        return f"{mode.display} ({mode.directive})"
    return mode.display


class TrayApp(rumps.App):  # type: ignore[misc]
    def __init__(
        self,
        state: CurrentMode,
        on_quit: Callable[[], None],
        verbose: bool = False,
        activity: ActivityNotifier | None = None,
    ) -> None:
        super().__init__(name="Ephew", title=_title_for(state.get()), quit_button=None)
        self._state = state
        self._on_quit = on_quit
        self._verbose = verbose
        self._items_by_mode: dict[str, rumps.MenuItem] = {}
        self._spin_generation = 0
        self._build_menu()
        state.subscribe(self._on_mode_change)
        if activity is not None:
            activity.subscribe(self._on_activity_pulse)

    def _build_menu(self) -> None:
        for mode in MODES:
            item = rumps.MenuItem(
                _menu_label(mode, self._verbose), callback=self._make_click_handler(mode)
            )
            self._items_by_mode[mode.name] = item
            self.menu.add(item)
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("Quit", callback=self._handle_quit))
        self._refresh_ui(self._state.get())

    def _make_click_handler(self, mode: Mode) -> Callable[[Any], None]:
        def handler(_sender: Any) -> None:
            self._state.set(mode)

        return handler

    def _handle_quit(self, _sender: Any) -> None:
        try:
            self._on_quit()
        except Exception:
            log.exception("on_quit callback raised")
        rumps.quit_application()

    def _on_mode_change(self, mode: Mode) -> None:
        AppHelper.callAfter(self._refresh_ui, mode)

    def _refresh_ui(self, active: Mode) -> None:
        self.title = _title_for(active)
        for name, item in self._items_by_mode.items():
            item.state = 1 if name == active.name else 0

    # ------------------------------------------------------------------ activity spin

    def _on_activity_pulse(self) -> None:
        # Called on whatever thread the proxy used (asyncio thread). Marshal to main.
        AppHelper.callAfter(self._begin_spin)

    def _begin_spin(self) -> None:
        self._spin_generation += 1
        self._tick_spin(self._spin_generation, 0)

    def _tick_spin(self, generation: int, frame_idx: int) -> None:
        if generation != self._spin_generation:
            return  # superseded by a newer pulse
        if frame_idx >= len(_SPIN_FRAMES):
            self._refresh_ui(self._state.get())
            return
        self.title = _spin_title(self._state.get(), _SPIN_FRAMES[frame_idx])
        AppHelper.callLater(_SPIN_INTERVAL_SECS, self._tick_spin, generation, frame_idx + 1)
