from __future__ import annotations

import logging
import re

REDACT_HEADER_NAMES: frozenset[str] = frozenset({
    "x-api-key",
    "authorization",
    "proxy-authorization",
})
REDACTION_PLACEHOLDER = "<redacted>"

_HEADER_NAMES_ALT = "|".join(re.escape(name) for name in REDACT_HEADER_NAMES)
_HEADER_RE = re.compile(rf"(?i)\b({_HEADER_NAMES_ALT})\s*[:=]\s*[^\r\n]+")


class CredentialRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_any(record.msg)
        if record.args:
            args = record.args if isinstance(record.args, tuple) else (record.args,)
            record.args = tuple(_redact_any(a) for a in args)
        return True


def _redact_any(value):
    if isinstance(value, str):
        return _HEADER_RE.sub(lambda m: f"{m.group(1)}: {REDACTION_PLACEHOLDER}", value)
    if isinstance(value, dict):
        return {
            k: (REDACTION_PLACEHOLDER if isinstance(k, str) and k.lower() in REDACT_HEADER_NAMES
                else _redact_any(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_any(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_any(item) for item in value)
    return value


_installed = False


def install_redaction() -> None:
    global _installed
    if _installed:
        return
    filt = CredentialRedactionFilter()
    root = logging.getLogger()
    root.addFilter(filt)
    for handler in root.handlers:
        handler.addFilter(filt)
    _installed = True
