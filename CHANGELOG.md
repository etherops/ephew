# Changelog

All notable changes to this project will be documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — initial public release

First public release. Bundles all of the internal Phases 1–3 work into one shipped artifact.

### Added

- **Passthrough proxy** for the Anthropic API on `127.0.0.1:47821`. Set `ANTHROPIC_BASE_URL` to point any Claude client (Claude Code, the `anthropic` SDK, `curl`) at the proxy.
- **Six verbosity modes** with hard-coded directives, cycled by global hotkey `⇧⌘E`: very-concise, concise, normal, thorough, very-thorough, table.
- **Menu-bar tray** showing `fu <glyph>` for the active mode. Click any mode to set it directly.
- **Directive injection** appends a short user-preference string to the last user message of every `POST /v1/messages` request, with no markers / brackets / tags so the model reads it as a natural P.S.
- **Streaming SSE passthrough** — responses flow byte-identically back to the client.
- **`--verbose` / `-v` flag** — extends per-request log lines with the active directive, and annotates each tray menu item with its directive in parens.
- **Credential redaction** — a logging filter strips `x-api-key`, `authorization`, and `proxy-authorization` from any log record.
- **Per-request validation log** — one INFO line per request: `proxy method=POST path=/v1/messages upstream_status=200 bytes=12345 mode=concise`.
- **Mode-change log** — one INFO line per actual mode toggle on the `ephew.state` logger.
- **`--port`, `--version`, `--help`** with auto-generated modes table built from `ephew.modes.MODES`.
- **Structured startup failure** — typed `PortInUseError` produces a clean one-line stderr message; no stack traces in the normal failure path.
- **No macOS Accessibility permission required** — global hotkey uses Carbon `RegisterEventHotKey` rather than `pynput` or `NSEvent.addGlobalMonitor`, so the user sees zero privacy prompts on first launch.

### Repository / OSS hygiene

- MIT license.
- 67-test suite covering proxy, transform, modes, state, server, security, CLI.
- Spec-driven workflow: every feature has a `specs/spec-<name>.md`. The launch plan is `specs/LAUNCH.md`.
- GitHub Actions CI runs on macOS and Linux.

[Unreleased]: https://github.com/etherops/ephew/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/etherops/ephew/releases/tag/v0.1.0
