from __future__ import annotations

import copy
import re
from typing import Any

from ephew.modes import OVERRIDE_FLAGS, Mode, find_by_name

SEPARATOR = "\n\n"

_OVERRIDE_PATTERN = re.compile(
    r"\s+(-x|--none|-c|--concise|-p|--paragraph|-v|--verbose|-t|--table)\s*\Z"
)


def apply(
    body: dict[str, Any],
    mode: Mode,
    include_markers: bool = True,
) -> tuple[dict[str, Any], Mode, str | None]:
    new_body = copy.deepcopy(body)
    messages = new_body.get("messages") if isinstance(new_body, dict) else None
    if not isinstance(messages, list) or not messages:
        return new_body, mode, None

    last_user = _find_last_user_message(messages)
    if last_user is None:
        return new_body, mode, None

    text_holder = _text_target(last_user)
    override_flag = _detect_and_strip_override(text_holder) if text_holder else None
    effective = find_by_name(OVERRIDE_FLAGS[override_flag]) if override_flag else mode

    if effective.directive is None:
        return new_body, effective, override_flag

    payload = effective.directive
    if include_markers and effective.marker_instruction:
        payload = payload + SEPARATOR + effective.marker_instruction

    _inject(last_user, payload)
    return new_body, effective, override_flag


def _find_last_user_message(messages: list[Any]) -> dict[str, Any] | None:
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg
    return None


class _TextTarget:
    """Mutable handle to the text we may strip + append to."""

    def __init__(self, get_text: Any, set_text: Any):
        self._get = get_text
        self._set = set_text

    @property
    def text(self) -> str:
        value = self._get()
        return value if isinstance(value, str) else ""

    @text.setter
    def text(self, value: str) -> None:
        self._set(value)


def _text_target(msg: dict[str, Any]) -> _TextTarget | None:
    content = msg.get("content")
    if isinstance(content, str):
        return _TextTarget(lambda: msg["content"], lambda v: msg.__setitem__("content", v))
    if isinstance(content, list):
        for block in reversed(content):
            if isinstance(block, dict) and block.get("type") == "text":
                return _TextTarget(
                    lambda b=block: b.get("text", ""),
                    lambda v, b=block: b.__setitem__("text", v),
                )
    return None


def _detect_and_strip_override(target: _TextTarget) -> str | None:
    text = target.text
    match = _OVERRIDE_PATTERN.search(text)
    if not match:
        return None
    flag = match.group(1)
    target.text = text[: match.start()]
    return flag


def _inject(msg: dict[str, Any], payload: str) -> None:
    content = msg.get("content")
    if isinstance(content, str):
        msg["content"] = (content + SEPARATOR + payload) if content else payload
        return
    if isinstance(content, list):
        for block in reversed(content):
            if isinstance(block, dict) and block.get("type") == "text":
                existing = block.get("text", "")
                block["text"] = (existing + SEPARATOR + payload) if existing else payload
                return
        content.append({"type": "text", "text": payload})
