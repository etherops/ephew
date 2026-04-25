from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from ephew.modes import Mode, next_mode

log = logging.getLogger("ephew.state")

Listener = Callable[[Mode], None]


class CurrentMode:
    def __init__(self, initial: Mode):
        self._mode = initial
        self._listeners: list[Listener] = []
        self._lock = threading.Lock()

    def get(self) -> Mode:
        with self._lock:
            return self._mode

    def set(self, mode: Mode) -> None:
        with self._lock:
            previous = self._mode
            self._mode = mode
            changed = previous is not mode
            listeners = list(self._listeners) if changed else []
        if changed:
            log.info("state mode changed to=%s", mode.name)
            self._notify(listeners, mode)

    def cycle(self) -> Mode:
        with self._lock:
            previous = self._mode
            new = next_mode(previous)
            self._mode = new
            changed = previous is not new
            listeners = list(self._listeners) if changed else []
        if changed:
            log.info("state mode changed to=%s", new.name)
            self._notify(listeners, new)
        return new

    def subscribe(self, callback: Listener) -> None:
        with self._lock:
            self._listeners.append(callback)

    @staticmethod
    def _notify(listeners: list[Listener], mode: Mode) -> None:
        for cb in listeners:
            try:
                cb(mode)
            except Exception:
                log.warning("state subscriber raised", exc_info=True)
