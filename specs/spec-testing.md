# spec-testing.md — Verification strategy

**Phase:** Mixed — see [LAUNCH.md](./LAUNCH.md).

- **Pre-MVP:** passthrough-only unit tests — `test_proxy` (covers passthrough cases and validation-log behavior), `test_server`, `test_security`. Plus the manual Pre-MVP validation: `export ANTHROPIC_BASE_URL=http://127.0.0.1:47821 && claude "hi"` works through the proxy with requests visibly logged.
- **MVP:** unit tests for the feature layer — `test_transform`, `test_modes`, `test_state`, `test_cli` — plus `test_proxy`'s transform cases. Full manual integration checklist on macOS 14+ (tray + hotkey + end-to-end against `api.anthropic.com` with a real key + credential-leak grep).
- **Dot:** GitHub Actions CI (`.github/workflows/test.yml`) running the unit suite on macOS and Linux for every push and PR; `test_chip` smoke test; `--port` / `--version` CLI tests.

## Purpose

Define the test surface that gives confidence Ephew does what every other spec says it does, without requiring Anthropic API credentials in CI. Unit tests own the pure logic and the proxy wire behavior; manual integration testing covers everything that requires the AppKit runloop, a real Mac, and a real API key.

## Public surface

Directory: `tests/`.

```
tests/
├── conftest.py         # shared fixtures (CurrentMode, sample bodies, MockTransport upstream)
├── test_transform.py   # pure-function golden tests
├── test_modes.py       # tuple shape, cycle order, uniqueness
├── test_state.py       # thread-safety, subscribe/notify
├── test_proxy.py       # FastAPI + MockTransport upstream
├── test_server.py      # uvicorn lifecycle
├── test_security.py    # redaction filter
└── test_cli.py         # argparse and --version / --help
```

Invariants:
- Tests require no network, no real API key, no GUI.
- Running `pytest` in a fresh venv from a clean clone passes on any modern macOS or Linux host (even though Ephew only *runs* on macOS, the test suite is headless and portable — AppKit-touching code is covered manually).
- No test depends on the order of execution.

## Behavior

### Unit tests

Covered in detail in each feature spec; summarized here with the invariant each test is defending.

| File | Invariant under test |
|---|---|
| `test_transform.py` | Directive is appended to the last user message (string or block-list); `none` mode is structural identity; in-prompt override flag at end of last user message swaps mode and is stripped; input dict is not mutated; defensive no-op on malformed inputs |
| `test_modes.py` | `MODES` is an immutable tuple; names unique; cycle wraps; `DEFAULT` is `none`; non-none modes have non-empty directives; `OVERRIDE_FLAGS` covers every mode |
| `test_state.py` | `get`/`set`/`cycle` are thread-safe; subscribers fire after the lock is released; exceptions in a subscriber don't block other subscribers; a subscriber calling `get()` does not deadlock |
| `test_proxy.py` | `/v1/messages` is transformed per mode; every other path passes through; SSE passthrough byte-identical; 502 on connection failure; credential headers forwarded byte-identical; `host` and `content-length` stripped |
| `test_server.py` | `start()` waits for socket bind; `stop()` is idempotent; bind failure raises; server thread is daemon |
| `test_security.py` | Filter redacts `x-api-key` / `authorization` / `proxy-authorization` case-insensitively, in both message strings and header-dict args; no leak of fake credential substring |
| `test_cli.py` | `--version` exits 0 with version; `--help` includes all mode names + directives; unknown flags exit 2 |

### Manual integration test

Runs once per release on macOS 14+ with a real Anthropic API key. Reproducible checklist:

1. Clean install:
   ```
   cd /tmp && rm -rf ephew-test
   git clone <this repo> ephew-test && cd ephew-test
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -e .
   ```
2. Launch the daemon:
   ```
   ephew
   ```
   Confirm on first launch:
   - No macOS Accessibility permission prompt appears for Terminal or Python. (This is the whole point of using Carbon `RegisterEventHotKey` — see [spec-hotkey.md](./spec-hotkey.md).)
   - Menu-bar icon is present.
   - Floating chip is visible in the bottom-right corner, showing `none`.
   - Startup banner on stderr matches [spec-cli.md](./spec-cli.md).
3. Point Claude Code at the proxy in a second terminal:
   ```
   export ANTHROPIC_BASE_URL=http://127.0.0.1:47821
   claude "what is 2+2"
   ```
   Confirm a normal response.
4. Cycle through every mode. For each:
   - Press `⇧⌘E`.
   - Confirm chip + tray checkmark update within ~100 ms.
   - Re-run `claude "what is 2+2"` (or similar question). Confirm response shape matches directive:
     - `none` → unmodified Claude response
     - `concise` → one sentence
     - `verbose` → multi-paragraph with reasoning + edge cases
     - `table` → a markdown table, no surrounding prose
5. Per-request override:
   - Set tray to `none`. Run `claude "explain channels -v"`. Response must be verbose-shaped despite the tray reading `none`.
   - Run `claude "now without override"`. Response must revert to `none`-shaped (passthrough).
   - Confirm the daemon log carries one line with `mode=verbose override=-v` for the first request.
5. Credential-leak check:
   ```
   grep -c "$(echo $ANTHROPIC_API_KEY | cut -c1-12)" ~/Library/Logs/ephew.log 2>/dev/null || echo 0
   # also check stderr capture if running under a log file
   ```
   Must report `0`.
6. Fail-clean check:
   - Kill the daemon (`Cmd-Q` from tray, or `kill` from shell).
   - Re-run `claude "ping"`. Must fail with a connection error, *not* silently succeed by routing directly to `api.anthropic.com`. (This confirms the env var is being honored — a silent fallback would mean some layer is bypassing `ANTHROPIC_BASE_URL`.)
7. Restart the daemon. Confirm the mode resets to `none` (no persistence is a documented v1 choice — see [spec-state.md](./spec-state.md)).

### What we intentionally do not test

- Fuzz testing of the transform (the function is small enough to reason about exhaustively)
- Load testing of the proxy (single-user local tool; performance beyond "doesn't add perceptible latency" is out of scope)
- Real-API calls in CI (would require a secret, which violates the security posture of this project)
- AppKit UI automation (brittle; covered by the manual checklist)

## Dependencies

Third-party test tooling: `pytest`, `httpx` (with `MockTransport`), `pytest-asyncio` for the async proxy tests.

## Out of scope

- Multi-Python-version matrix in CI (sticks to 3.12 in `.github/workflows/test.yml`)
- Coverage targets (aim high but don't gate merges on a number in v1)
- Mutation testing, property-based testing (`hypothesis`), or snapshot testing
- Load / soak / chaos testing

## Verification

This spec is self-verified: every row in the "Unit tests" table above corresponds to at least one concrete test file, and the manual integration checklist is the release-gate procedure. A spec change is considered valid when:

- The file list under "Public surface" matches what exists in `tests/` after implementation.
- Every invariant named in another `spec-*.md` is defended by at least one unit test listed here.
- A fresh clone running `pytest` produces a green suite on macOS and Linux without network access or an API key.
- The manual checklist, executed verbatim on macOS 14+, produces the documented observations at every step.
