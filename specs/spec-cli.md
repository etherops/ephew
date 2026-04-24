# spec-cli.md — Entry point

**Phase:** Mixed — see [LAUNCH.md](./LAUNCH.md).

- **Pre-MVP:** minimal. Installs the redaction filter, constructs the `httpx` client, builds the passthrough FastAPI app, starts the proxy server, prints a basic banner, blocks on SIGINT. No state, no modes, no transform. No tray, no chip, no hotkey, no AppKit runloop.
- **MVP:** imports modes/state/transform, wires the transform into the proxy, installs the Carbon hotkey, creates the tray, blocks on the AppKit runloop. Tray Quit and SIGINT both trigger the clean-shutdown sequence. Banner gains the hotkey line. No chip yet (deferred to Dot).
- **Dot:** `--port N`, `--version`, expanded `--help` rendering the full modes table, structured startup-failure exits, and the `ModeChip.show()` / `close()` wiring (see [spec-chip.md](./spec-chip.md)).

The spec body below describes the MVP end-state. Items marked **[Dot]** inline are deferred past MVP.

## Purpose

The `ephew` CLI is the single process entry point. It wires every module together in the correct startup order, prints a banner telling the user how to point their Anthropic client at the proxy, blocks on the AppKit runloop, and tears everything down cleanly on quit.

## Public surface

Module: `ephew/__main__.py`.

```python
def main(argv: list[str] | None = None) -> int: ...
```

Returns a POSIX exit code (0 = clean, 1 = startup failure, 2 = CLI misuse). Registered in `pyproject.toml` as:

```toml
[project.scripts]
ephew = "ephew.__main__:main"
```

Invariants:
- Single foreground process. No daemonization, no `fork()`, no PID files in v1.
- Startup and shutdown are deterministic (order documented below).
- Exits 0 on user-initiated quit (tray Quit, Ctrl-C).
- Never prints the value of `ANTHROPIC_API_KEY` or any other credential to stdout/stderr.

## Behavior

### CLI flags

- `--verbose` / `-v` — two effects: (1) extend the per-request validation log line with the full directive text that was appended (see [spec-proxy.md](./spec-proxy.md)); (2) annotate each non-`normal` tray menu item with its directive in parentheses (see [spec-tray.md](./spec-tray.md)). Off by default. **Scope:** raises only the `ephew.*` logger namespace to DEBUG. Third-party libraries (`httpx`, `httpcore`, `uvicorn`, `asyncio`, etc.) stay at WARNING regardless of `--verbose` — `--verbose` is for *our* output, not for stack-tracing the dependencies.
- `--port N` — override the default proxy port (`47821`). Resolution order: `--port` flag > `EPHEW_PORT` env var > default `47821`.
- `--version` — print version from `ephew.__version__` to stdout and exit 0.
- `--help` — print help to stdout and exit 0. The help includes a modes table rendered from `ephew.modes.MODES` (glyph, display name, directive).

Parsed with `argparse`. Unknown flags exit 2.

### Startup order

1. Install the credential-redaction logging filter on the root logger ([spec-security.md](./spec-security.md)). This happens before any other subsystem can emit a log record.
2. Import `modes.MODES` and `modes.DEFAULT`.
3. Construct `CurrentMode(initial=DEFAULT)`.
4. Construct the `httpx.AsyncClient` with Anthropic base URL and timeouts.
5. Build the FastAPI app with `proxy.build_app(state, upstream_client)`.
6. Construct `ProxyServer(app, port=resolved_port)` and call `start()`. If startup fails, log the error and return 1.
7. Construct and `install()` the `HotkeyRegistration`. If it returns `False`, log WARNING that menu-only operation is active; do not fail.
8. Construct `ModeChip(state)` and call `show()`. **[Dot]** — the chip is deferred past MVP; in MVP this step is skipped entirely.
9. Construct `TrayApp(state, on_quit=self._shutdown)`.
10. Print the startup banner (below) to **stderr** so it doesn't pollute stdout pipes.
11. Call `tray.run()` — blocks on the AppKit runloop until quit.
12. On quit (via `on_quit` callback): call `chip.close()` **[Dot]** (skipped in MVP), `hotkey.uninstall()`, `server.stop(timeout=3.0)`. Return 0.

### Startup banner

Printed once to stderr after the server is confirmed bound:

```
ephew 1.1.0 running on http://127.0.0.1:47821
point your Anthropic client at this proxy:
  export ANTHROPIC_BASE_URL=http://127.0.0.1:47821
hotkey: ⇧⌘E to cycle modes
```

If the port was overridden, the URL reflects the override. If hotkey registration failed (collision with another app), an extra line is printed in place of the `hotkey:` line:

```
hotkey unavailable (conflict with another app); use the menu-bar icon to change modes
```

### Structured startup failures

On any failure to start the proxy (e.g. port-in-use), the CLI prints a single line to stderr and exits with code 1:

```
ephew: failed to start — port 47821 is already in use on 127.0.0.1
```

The message names the concrete cause (no bare "RuntimeError" or stacktrace). Known failure classes:

- `PortInUseError` → `port N is already in use on HOST`
- any other `Exception` → `failed to start — <exception message>`

Stacktraces do not appear on stderr in the normal failure path; they are available only at `--verbose` DEBUG logging level.

### `--help` output

Standard argparse help, followed by a modes section (as the argparse `epilog`, rendered with `RawDescriptionHelpFormatter` to preserve line breaks):

```
modes (cycle in order; hotkey ⇧⌘E):
  .     very concise    Yes or no if possible. Max 5 words otherwise.
  ..    concise         One sentence.
  -     normal          passthrough — no directive appended
  "     thorough        Include reasoning, tradeoffs, and an example if it helps.
  ""    very thorough   Go deep where depth helps: reasoning, tradeoffs, edge cases. Skip padding.
  ⊞     table           Markdown table only, no prose.
```

Built dynamically from `ephew.modes.MODES` so the help never drifts from the runtime modes.

### Signal handling

`SIGINT` (Ctrl-C) triggers the same shutdown sequence as the tray Quit. Install a handler that calls `self._shutdown()` and then raises `KeyboardInterrupt` so the AppKit runloop exits.

## Dependencies

Upstream (required):
- Every other spec in this suite. `__main__.py` is the wiring layer.

Third-party: `argparse` (stdlib), plus everything the submodules bring.

## Out of scope

- Daemonization (`--detach`, `nohup`-style backgrounding)
- PID files
- Log-file flag (stderr only; users can `2> ephew.log` if they want)
- Configuration file (no `~/.config/ephew/config.toml` in v1)
- Auto-update checks
- Custom banner or quiet mode

## Verification

Unit tests (`tests/test_cli.py`):
- `main(["--version"])` prints the version to stdout and returns 0.
- `main(["--help"])` includes every mode name and directive in the output.
- `main(["--port", "1"])` (privileged port) logs a startup failure and returns 1.
- Argparse rejects unknown flags with exit code 2.

Manual: covered by [spec-testing.md](./spec-testing.md) — the full end-to-end smoke test lives there.
