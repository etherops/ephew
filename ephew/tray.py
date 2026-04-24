from __future__ import annotations

import logging
from typing import Callable

import rumps
from PyObjCTools import AppHelper

from ephew.modes import MODES, Mode
from ephew.state import CurrentMode

log = logging.getLogger("ephew.tray")

_TOP_LINE = "fu"


def _title_for(mode: Mode) -> str:
    return f"{_TOP_LINE} {mode.glyph}"


def _menu_label(mode: Mode, verbose: bool) -> str:
    if verbose and mode.directive:
        return f"{mode.display} ({mode.directive})"
    return mode.display


class TrayApp(rumps.App):
    def __init__(
        self,
        state: CurrentMode,
        on_quit: Callable[[], None],
        verbose: bool = False,
    ):
        super().__init__(name="Ephew", title=_title_for(state.get()), quit_button=None)
        self._state = state
        self._on_quit = on_quit
        self._verbose = verbose
        self._items_by_mode: dict[str, rumps.MenuItem] = {}
        self._build_menu()
        state.subscribe(self._on_mode_change)

    def _build_menu(self) -> None:
        for mode in MODES:
            item = rumps.MenuItem(_menu_label(mode, self._verbose), callback=self._make_click_handler(mode))
            self._items_by_mode[mode.name] = item
            self.menu.add(item)
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("Quit", callback=self._handle_quit))
        self._refresh_ui(self._state.get())

    def _make_click_handler(self, mode: Mode):
        def handler(_sender):
            self._state.set(mode)
        return handler

    def _handle_quit(self, _sender):
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
