from __future__ import annotations

import ctypes
import ctypes.util
import logging
from collections.abc import Callable
from ctypes import CFUNCTYPE, POINTER, Structure, byref, c_int32, c_uint32, c_void_p
from typing import Any

log = logging.getLogger("ephew.hotkey")

_CARBON_PATH = "/System/Library/Frameworks/Carbon.framework/Carbon"

kEventClassKeyboard = 0x6B657962  # 'keyb'
kEventHotKeyPressed = 5

cmdKey = 0x0100
shiftKey = 0x0200
optionKey = 0x0800
controlKey = 0x1000

kVK_ANSI_E = 0x0E

noErr = 0


class _EventTypeSpec(Structure):
    _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]


class _EventHotKeyID(Structure):
    _fields_ = [("signature", c_uint32), ("id", c_uint32)]


_EventHandlerProc = CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)


def _load_carbon() -> ctypes.CDLL | None:
    try:
        lib = ctypes.CDLL(_CARBON_PATH)
    except OSError:
        alt = ctypes.util.find_library("Carbon")
        if not alt:
            return None
        lib = ctypes.CDLL(alt)

    lib.GetApplicationEventTarget.restype = c_void_p
    lib.GetApplicationEventTarget.argtypes = []

    lib.RegisterEventHotKey.restype = c_int32
    lib.RegisterEventHotKey.argtypes = [
        c_uint32,
        c_uint32,
        _EventHotKeyID,
        c_void_p,
        c_uint32,
        POINTER(c_void_p),
    ]
    lib.UnregisterEventHotKey.restype = c_int32
    lib.UnregisterEventHotKey.argtypes = [c_void_p]

    lib.InstallEventHandler.restype = c_int32
    lib.InstallEventHandler.argtypes = [
        c_void_p,
        c_void_p,
        c_uint32,
        POINTER(_EventTypeSpec),
        c_void_p,
        POINTER(c_void_p),
    ]
    lib.RemoveEventHandler.restype = c_int32
    lib.RemoveEventHandler.argtypes = [c_void_p]
    return lib


class HotkeyRegistration:
    def __init__(self, on_press: Callable[[], object]) -> None:
        # on_press's return value is ignored; using `object` lets callers pass functions
        # that return values (e.g. state.cycle returns Mode) without a type-error wrapper.
        self._on_press = on_press
        self._carbon: ctypes.CDLL | None = None
        self._hotkey_ref = c_void_p()
        self._handler_ref = c_void_p()
        # CFUNCTYPE objects don't have a clean static type; treat as Any.
        self._upp: Any = None

    def install(self) -> bool:
        self._carbon = _load_carbon()
        if self._carbon is None:
            log.warning("Carbon framework unavailable; hotkey disabled (menu-only operation)")
            return False

        target = self._carbon.GetApplicationEventTarget()
        if not target:
            log.warning("no application event target; hotkey disabled")
            return False

        hotkey_id = _EventHotKeyID(signature=0x45465557, id=1)  # 'EFUW'
        modifiers = cmdKey | shiftKey
        key_code = kVK_ANSI_E

        status = self._carbon.RegisterEventHotKey(
            key_code, modifiers, hotkey_id, target, 0, byref(self._hotkey_ref)
        )
        if status != noErr:
            log.warning(
                "hotkey unavailable (RegisterEventHotKey status=%d); menu-only operation", status
            )
            self._hotkey_ref = c_void_p()
            return False

        def _handler(_next_handler: Any, _event: Any, _user_data: Any) -> int:
            try:
                self._on_press()
            except Exception:
                log.exception("hotkey callback raised")
            return noErr

        self._upp = _EventHandlerProc(_handler)
        event_type = _EventTypeSpec(eventClass=kEventClassKeyboard, eventKind=kEventHotKeyPressed)
        status = self._carbon.InstallEventHandler(
            target,
            ctypes.cast(self._upp, c_void_p),
            1,
            byref(event_type),
            None,
            byref(self._handler_ref),
        )
        if status != noErr:
            log.warning("failed to install hotkey event handler (status=%d)", status)
            self._carbon.UnregisterEventHotKey(self._hotkey_ref)
            self._hotkey_ref = c_void_p()
            self._upp = None
            return False

        log.info("hotkey registered: Shift+Cmd+E")
        return True

    def uninstall(self) -> None:
        if self._carbon is None:
            return
        if self._handler_ref:
            self._carbon.RemoveEventHandler(self._handler_ref)
            self._handler_ref = c_void_p()
        if self._hotkey_ref:
            self._carbon.UnregisterEventHotKey(self._hotkey_ref)
            self._hotkey_ref = c_void_p()
        self._upp = None
