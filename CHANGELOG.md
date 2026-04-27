# Changelog

All notable changes to this project will be documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — initial release

### Proxy

- **Local proxy** for the Anthropic API on `127.0.0.1:47821`. Set `ANTHROPIC_BASE_URL` to point any Claude client (Claude Code, the `anthropic` SDK, `curl`) at the proxy.
- **Bare Starlette** under the hood — pure-Python dep tree, no Rust toolchain required for source installs.
- **Streaming SSE passthrough** — responses flow byte-identically back to the client.
- **Credential redaction** — a logging filter strips `x-api-key`, `authorization`, and `proxy-authorization` from any log record. The daemon never reads credential header values into its own memory.
- **Per-request validation log** — one INFO line per request: `proxy method=POST path=/v1/messages upstream_status=200 bytes=12345 mode=concise`. Adds `override=<flag>` when a per-request override fired (see Modes).
- **Structured startup failure** — typed `PortInUseError` produces a clean one-line stderr message; no stack traces in the normal failure path.

### Modes

- **Five modes** with hard-coded directives, cycled by global hotkey `⇧⌘E`: `none`, `concise`, `paragraph`, `verbose`, `table`.
- **Glyphs match the in-prompt override flags** — the menu-bar title reads `ephew -x` / `-c` / `-p` / `-v` / `-t`, and the same tokens work as one-shot suffixes on individual prompts (`claude "explain channels -v"`).
- **Per-request override** — append `-x`/`-c`/`-p`/`-v`/`-t` (or the long forms `--none`/`--concise`/`--paragraph`/`--verbose`/`--table`) to the very end of any prompt to one-shot a specific mode without touching the tray. Stripped before forwarding; logged with `override=<flag>`.
- **Response markers** — non-`none` modes ask the model to end its response with `(ephew-c)` / `(ephew-p)` / `(ephew-v)` / `(ephew-t)` (preceded by a space) so the user can see at a glance which mode handled the response. Default-on; disable globally with `--no-markers`.
- **Directive injection** appends a short user-preference string to the last user message of every `POST /v1/messages` request, after `\n\n`, with no markers / brackets / tags so the model reads it as a natural P.S.
- **Mode-change log** — one INFO line per actual mode toggle on the `ephew.state` logger.

### Menu bar

- **Tray icon** showing `ephew <glyph>` for the active mode. Click any mode to set it directly; checkmark moves to the active item.
- **Activity spinner** — a small braille spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) briefly walks between the brand and the glyph on every proxied request, so the user sees at a glance that ephew is in the path (vs. a misconfigured `ANTHROPIC_BASE_URL` letting the call go direct).
- **No macOS Accessibility permission required** — global hotkey uses Carbon `RegisterEventHotKey` rather than `pynput` or `NSEvent.addGlobalMonitor`, so the user sees zero privacy prompts on first launch.

### CLI

- **`ephew`** — start the daemon (proxy + tray + hotkey).
- **`ephew setup`** — first-run helper that emits the `ANTHROPIC_BASE_URL` export. Three forms:
  - `ephew setup` — friendly multi-line message describing both apply paths.
  - `ephew setup --print` — single line suitable for `eval "$(ephew setup --print)"`.
  - `ephew setup --append-rc` — idempotently appends the export to the user's detected shell rc (`~/.zshrc`, `~/.bashrc`, `~/.profile`, or `~/.config/fish/config.fish` with `set -gx` syntax). Marked with a trailing `# ephew` comment so re-runs no-op.
- **`--port N`** — override the default proxy port (`47821`); also honors `EPHEW_PORT` env var.
- **`--verbose` / `-v`** — extends per-request log lines with the active directive, and annotates each tray menu item with its directive in parens.
- **`--version`, `--help`** — `--help` renders the modes table dynamically from `ephew.modes.MODES` plus the override-flag legend.

### Distribution

- **Homebrew tap** at `etherops/funstuff`. Formula uses a custom install method with `pip install --prefer-binary` so pip uses prebuilt wheels for `pyobjc-core` / `pyobjc-framework-Cocoa` and skips the C compile that fails on Macs with mismatched Xcode/CLT SDKs. Brew install completes in ~8 seconds.
- **PyPI** publish workflow scaffolded (`.github/workflows/publish.yml`); trusted publisher registration is the one remaining manual step.

### Repository / OSS hygiene

- MIT license; SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md.
- 100-test suite covering proxy, transform, modes, state, server, security, CLI.
- Spec-driven workflow: every feature has a `specs/spec-<name>.md`. The launch plan is `specs/LAUNCH.md`.
- GitHub Actions CI runs ruff + mypy + bandit + pip-audit + pytest on macOS and Linux for every push and PR.

[Unreleased]: https://github.com/etherops/ephew/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/etherops/ephew/releases/tag/v0.1.0
