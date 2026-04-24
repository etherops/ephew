# spec-security.md — Credential-handling guardrail

**Phase:** Pre-MVP — installed from the first commit and active in every phase. See [LAUNCH.md](./LAUNCH.md).

## Purpose

Ephew sits on the wire between the user's Anthropic-API client and `api.anthropic.com`. Every request carries a credential (`x-api-key` or `authorization`). The daemon's job is to forward those credentials byte-for-byte to upstream and *never* to surface their value anywhere observable — not in stdout, not in stderr, not in log files, not in exception messages, not in crash dumps. This rule is the prime imperative from the user's global CLAUDE.md: an agent-adjacent tool must never cause a credential value to be read into a context where it can be logged, cached, or retrieved. If this guardrail fails, the tool has leaked the user's key.

## Public surface

Module: `ephew/security.py`.

```python
REDACT_HEADER_NAMES: frozenset[str]  # {"x-api-key", "authorization", "proxy-authorization"}
REDACTION_PLACEHOLDER: str  # "<redacted>"

class CredentialRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool: ...

def install_redaction() -> None:
    """Attach CredentialRedactionFilter to the root logger. Idempotent."""
```

Invariants:
- `install_redaction()` is safe to call multiple times; only attaches the filter once.
- `REDACT_HEADER_NAMES` is a compile-time constant, not user-configurable.
- The filter matches header names case-insensitively.
- No module in Ephew is permitted to log a header dict without going through this filter.

## Behavior

### What gets redacted

The filter inspects `record.msg` and every item in `record.args`. If any of them:
- contains a header dict (any `dict` with any case-insensitive key in `REDACT_HEADER_NAMES`), or
- is a string containing a case-insensitive header name followed by `:` or `=` and then non-whitespace,

the matching value is replaced with `REDACTION_PLACEHOLDER` before the record is emitted.

The filter is intentionally conservative: when in doubt, redact. False positives (log lines that mention `x-api-key` in prose) produce `<redacted>` in the output, which is acceptable.

### What Ephew must never do

The following are *forbidden by construction* and enforced by code review plus the unit test below:
- Logging request or response bodies in any form.
- Logging full header dicts without passing them through `CredentialRedactionFilter` or manually dropping the redact set first.
- Copying `x-api-key` / `authorization` header values into variables named anything other than their direct pass-through target in the httpx call.
- Including upstream exception messages verbatim in 502 error bodies (see [spec-proxy.md](./spec-proxy.md)); only the exception class name is allowed.
- Any telemetry, crash reporting, or third-party logging destination.

### What the proxy does

Forwards headers byte-identically to upstream (see [spec-proxy.md](./spec-proxy.md)). The proxy module *never* logs header values and *never* inspects them beyond checking membership in the drop-list (`host`, `content-length`).

### Installation order

`install_redaction()` is the first thing `ephew/__main__.py` calls — before imports of fastapi, before the CurrentMode is constructed, before any logger has emitted a single record. This ensures uvicorn's own loggers inherit the filter when they're configured in [spec-server.md](./spec-server.md).

## Dependencies

Upstream: stdlib `logging` only.

Downstream:
- [spec-cli.md](./spec-cli.md) — calls `install_redaction()` at startup
- [spec-proxy.md](./spec-proxy.md) — relies on the filter being installed
- [spec-server.md](./spec-server.md) — relies on the filter being installed

Third-party: none.

## Out of scope

- Key rotation, vault integration, per-request encryption
- Redacting Anthropic *responses* — responses don't carry credential headers, and redacting response bodies would break the streaming contract
- Telemetry or audit trails (no usage data leaves the machine)
- Crash-reporting integrations (explicitly forbidden — a crash traceback could contain captured headers)
- User-configurable redact list (compile-time only)

## Verification

Unit tests (`tests/test_security.py`):
- Log a `logging.INFO` record with a fake `x-api-key: sk-ant-fake-DO-NOT-LOG`. Assert the captured output contains `<redacted>` and does **not** contain `sk-ant-fake`.
- Same for `authorization: Bearer sk-ant-fake-DO-NOT-LOG`.
- Case-insensitive match: log with `X-API-KEY`, `Authorization`, `AUTHORIZATION`. Same assertion.
- Header-dict redaction: log a record whose `record.args` includes `{"x-api-key": "sk-ant-fake"}`. Assert the rendered message does not contain `sk-ant-fake`.
- Idempotency: `install_redaction()` called twice installs only one filter instance.
- The filter does not corrupt records that contain no credentials (log `"hello world"`; assert output is unchanged).

Integration (manual, per [spec-testing.md](./spec-testing.md)): run `ephew` with a real `ANTHROPIC_API_KEY` exported, issue a request via `claude`, `tail ~/Library/Logs/ephew.log` (or stderr capture), `grep` for any substring of the API key. Must find zero matches.
