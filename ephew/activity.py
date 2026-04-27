from __future__ import annotations

import logging
import threading
from collections.abc import Callable

log = logging.getLogger("ephew.activity")

Listener = Callable[[], None]


class ActivityNotifier:
    """Tiny pub/sub primitive: proxy calls pulse(); tray (and others) flash on it.

    See specs/spec-activity.md for the full contract.
    """

    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Listener) -> None:
        with self._lock:
            self._listeners.append(callback)

    def pulse(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb()
            except Exception:
                log.warning("activity subscriber raised", exc_info=True)
