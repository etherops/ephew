from __future__ import annotations

import copy
from typing import Any

from ephew.modes import Mode

SEPARATOR = "\n\n"


def apply(body: dict[str, Any], mode: Mode) -> dict[str, Any]:
    if mode.directive is None:
        return copy.deepcopy(body)

    messages = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(messages, list) or not messages:
        return copy.deepcopy(body)

    new_body = copy.deepcopy(body)
    new_messages = new_body["messages"]

    for i in range(len(new_messages) - 1, -1, -1):
        msg = new_messages[i]
        if isinstance(msg, dict) and msg.get("role") == "user":
            _inject(msg, mode.directive)
            break

    return new_body


def _inject(msg: dict[str, Any], directive: str) -> None:
    content = msg.get("content")
    if isinstance(content, str):
        msg["content"] = content + SEPARATOR + directive
        return
    if isinstance(content, list):
        for block in reversed(content):
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = block.get("text", "") + SEPARATOR + directive
                return
        content.append({"type": "text", "text": directive})
