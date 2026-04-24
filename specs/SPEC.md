# Ephew — SPEC

Ephew is a local proxy and menu-bar daemon for any Anthropic-API client. It exposes an Anthropic-compatible HTTP endpoint on `127.0.0.1`, holds a "verbosity mode" as state, and appends the active mode's directive to the last user message of every outgoing `/v1/messages` request. A global hotkey cycles modes; a status-bar icon and a transparent always-on-top "chip" show the current mode.

## Context

Claude Code (and every other Anthropic-API client) has no fast way to toggle response verbosity mid-conversation. Users retype "one sentence / yes-or-no / as a table" boilerplate over and over, costing tokens and attention. `/output-style` and `--append-system-prompt` exist but are session-level, not a keystroke toggle with a visual indicator. Ephew fills that gap.

Prior-art check: proxies for Claude Code exist (seifghazi/claude-code-proxy, agentgateway, litellm, CCProxy), and Python tray-daemon patterns exist (rumps + pyobjc). Nothing combines them for verbosity toggling.

## Locked decisions

| Decision | Choice | Reason |
|---|---|---|
| Language | Python 3.12+ | Covers every need via pyobjc + rumps + fastapi |
| OS target (v1) | macOS only | Tray + chip + hotkey are native AppKit |
| Global hotkey API | `pyobjc-framework-Carbon` → `RegisterEventHotKey` | No Accessibility permission needed |
| Tray icon | `rumps` (NSStatusItem) | Minimal, standard |
| Floating chip | `pyobjc` → `NSWindow` (floating level, clear bg, `ignoresMouseEvents`) | Native transparent overlay |
| Proxy server | `fastapi` + `uvicorn` + `httpx` (streaming) | SSE passthrough trivial |
| Injection point | Append to last user message | Preserves Anthropic prompt caching |
| Modes | Hard-coded (v1) | Iterate on defaults before opening up |
| Proxy scope | Any Anthropic-API client | Wire protocol identical |
| Distribution | GitHub repo + README | Defer Homebrew/py2app |
| Credential handling | Forward `x-api-key` / `authorization` verbatim; never log values | CLAUDE.md prime imperative |

## System architecture

One Python process. The AppKit runloop owns the main thread (tray icon, floating chip, and Carbon hotkey must all live there). A daemon thread runs uvicorn with the FastAPI proxy. A single `CurrentMode` object, guarded by a `threading.Lock`, bridges the two.

```
 ┌──────────────── main thread (AppKit runloop) ────────────────┐
 │  rumps StatusItem  ◀── menu click ──▶  CurrentMode.set()     │
 │  NSWindow chip     ◀── redraw                                 │
 │  Carbon hotkey     ◀── press   ────▶  CurrentMode.cycle()    │
 │                                              │                │
 └──────────────────────────────────────────────┼────────────────┘
                                                │ read
 ┌──────────── background thread (asyncio + uvicorn) ────────────┐
 │  POST 127.0.0.1:47821/v1/messages                             │
 │    ├─ transform.apply(body, current_mode)                     │
 │    ├─ httpx.AsyncClient().stream() → api.anthropic.com        │
 │    └─ StreamingResponse (SSE passthrough)                     │
 └───────────────────────────────────────────────────────────────┘
```

## Module tree

```
ephew/
├── __init__.py
├── __main__.py        # entry point; wires everything; AppKit runloop        [spec-cli.md]
├── state.py           # CurrentMode + subscribe/notify                        [spec-state.md]
├── modes.py           # MODES tuple + helpers                                 [spec-modes.md]
├── transform.py       # Pure fn: inject directive into last user message     [spec-transform.md]
├── proxy.py           # FastAPI app: /v1/messages transform + passthrough    [spec-proxy.md]
├── server.py          # uvicorn lifecycle on background thread               [spec-server.md]
├── tray.py            # rumps StatusItem menu                                [spec-tray.md]
├── chip.py            # Floating NSWindow overlay                            [spec-chip.md]
├── hotkey.py          # Carbon RegisterEventHotKey wrapper                   [spec-hotkey.md]
└── security.py        # Logging filter that redacts credential headers      [spec-security.md]
tests/                                                                         [spec-testing.md]
```

## Runtime data flow

1. User starts `ephew`. The CLI installs the credential-redaction logging filter, loads modes, creates `CurrentMode(default=normal)`, launches uvicorn on a daemon thread, waits for its `started` event, registers the Carbon hotkey, creates the chip + tray, then enters the AppKit runloop.
2. User exports `ANTHROPIC_BASE_URL=http://127.0.0.1:47821` and runs an Anthropic client (Claude Code, `anthropic` SDK, curl, etc.).
3. User presses `⇧⌘E`. `CurrentMode.cycle()` fires; subscribers (tray, chip) re-render on the main thread.
4. Client makes `POST /v1/messages`. The proxy reads `CurrentMode.get()`, calls `transform.apply(body, mode)`, and forwards to `api.anthropic.com` with the client's credential headers intact.
5. The upstream SSE stream is piped through to the client byte-for-byte.
6. On quit (tray → Quit or Ctrl-C on the CLI), the main thread signals uvicorn to stop, unregisters the hotkey, closes the chip, and exits the runloop.

## Cross-cutting concerns

- **Credential redaction.** See [spec-security.md](./spec-security.md). The daemon never logs, prints, or otherwise surfaces the values of `x-api-key`, `authorization`, or any substring thereof. Enforced by a `logging.Filter` installed on the root logger at startup, before uvicorn binds.
- **Thread safety.** `CurrentMode` is the only shared mutable state. All reads/writes are lock-guarded. Subscribers run *after* the lock is released (see [spec-state.md](./spec-state.md)) and must marshal to the main thread via `PyObjCTools.AppHelper.callAfter` for any AppKit interaction.
- **Startup order.** redaction filter → modes → `CurrentMode` → uvicorn (await `started` event) → hotkey (log warning if taken, don't fail) → chip → tray → AppKit loop.
- **Shutdown order.** Tray quit → set `server.should_exit = True` → unregister hotkey → close chip → join server thread (3 s timeout) → exit process.

## Out of scope for v1

- Linux / Windows support (proxy alone would work headless; tray/chip/hotkey are macOS-specific)
- User-editable modes file
- User-configurable hotkey
- py2app / .app bundle / Homebrew formula / code signing
- Telemetry, analytics, crash reporting, auto-update
- HTTPS listener (binds only to `127.0.0.1`, no TLS)

## Glossary

- **mode** — a named verbosity setting (e.g. `very-concise`, `concise`, `table`) with an associated directive string.
- **directive** — the text appended to the last user message to request the desired response shape.
- **chip** — the transparent always-on-top `NSWindow` showing the current mode in a screen corner.
- **upstream** — `https://api.anthropic.com`, the real Anthropic API endpoint.
- **passthrough** — proxy behavior where a request is forwarded without transformation (for paths other than `/v1/messages`, or when mode is `normal`).

## Release plan

See [LAUNCH.md](./LAUNCH.md) for the three-phase plan: Pre-MVP (headless proxy + core logic), MVP (tray + chip + hotkey + public GitHub release), Dot (`--port` / `--version` / CI / polish). Every feature spec declares its phase in a `**Phase:**` callout near the top.

## Feature specs

- [spec-proxy.md](./spec-proxy.md) — HTTP server and routing
- [spec-transform.md](./spec-transform.md) — request-body directive injection
- [spec-modes.md](./spec-modes.md) — hard-coded modes
- [spec-state.md](./spec-state.md) — shared mode state
- [spec-tray.md](./spec-tray.md) — menu-bar UI
- [spec-chip.md](./spec-chip.md) — floating mode indicator
- [spec-hotkey.md](./spec-hotkey.md) — global shortcut
- [spec-server.md](./spec-server.md) — uvicorn lifecycle
- [spec-cli.md](./spec-cli.md) — entry point
- [spec-security.md](./spec-security.md) — credential-handling guardrail
- [spec-testing.md](./spec-testing.md) — verification strategy
