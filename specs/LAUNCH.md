# Ephew — Launch Plan

Three phases between the current spec-complete state and a community-tested open-source release. Every `spec-*.md` file carries a `**Phase:**` callout near the top showing where its content lands; this document is the index and exit-criteria checklist.

## Phase 1 — Pre-MVP (passthrough proxy, validated)

**Goal:** prove the proxy is actually sitting in the middle of Anthropic-API traffic. No transformation, no modes, no UI — just a transparent passthrough that you can point Claude Code at, watch requests flow through, and confirm the plumbing works end-to-end.

**In-scope specs:**
- [spec-security.md](./spec-security.md) — credential-redaction filter (non-negotiable from day 1)
- [spec-proxy.md](./spec-proxy.md) — **passthrough only**: catch-all route, upstream forwarding, SSE streaming, per-request validation log line (method + path + upstream status + response byte count; no headers, no body). The `/v1/messages` path gets the same passthrough treatment as every other path.
- [spec-server.md](./spec-server.md) — uvicorn on a background thread; clean start/stop
- [spec-cli.md](./spec-cli.md) — minimal entry point: installs the redaction filter, starts the proxy, prints a banner, blocks on SIGINT. No tray, no chip, no hotkey, no `--mode` flag, no state module.
- [spec-testing.md](./spec-testing.md) — unit tests: `test_proxy` (passthrough cases only), `test_server`, `test_security`

**Explicitly deferred:** modes, state, transform, tray, chip, hotkey, any response modification.

**Exit criteria:**
- `ephew` starts, binds `127.0.0.1:47821`, prints the banner to stderr.
- `export ANTHROPIC_BASE_URL=http://127.0.0.1:47821 && claude "what is 2+2"` returns a normal Claude response — the proxy is transparently forwarding.
- Proxy logs one line per request (method, path, upstream status, bytes) so interception is visibly verifiable.
- `pytest` is green on macOS and Linux from a clean clone, without an API key or network access.
- `grep` for any fake-key substring used in tests returns zero hits in every log destination.

## Phase 2 — MVP (bare minimum feature — launch it and it works)

**Goal:** the smallest surface that delivers the actual idea. User runs `ephew`, picks a mode, re-runs `claude`, *sees a visibly different response shape*. Everything optional is pushed to Dot.

**Additive scope on top of Pre-MVP:**
- [spec-modes.md](./spec-modes.md) — hard-coded `MODES` tuple, helpers, `DEFAULT`
- [spec-state.md](./spec-state.md) — `CurrentMode` with lock + subscribe/notify
- [spec-transform.md](./spec-transform.md) — pure directive-injection function
- [spec-proxy.md](./spec-proxy.md) — add transform integration on `POST /v1/messages` (reads `state.get()`, calls `transform.apply`, re-serializes, forwards). Passthrough behavior from Pre-MVP is preserved for every other path.
- [spec-tray.md](./spec-tray.md) — rumps `StatusItem`, menu with every mode, checkmark shows active mode, Quit handler. This is the *entire* MVP UI: the menu both *changes* the mode (click) and *shows* the mode (checkmark).
- [spec-hotkey.md](./spec-hotkey.md) — Carbon `RegisterEventHotKey` for `⌃⌥⌘V`; no Accessibility prompt. The headline toggle feature.
- [spec-cli.md](./spec-cli.md) — full wiring: tray + hotkey + AppKit runloop; tray Quit and SIGINT both trigger clean shutdown.
- [spec-testing.md](./spec-testing.md) — unit tests `test_transform`, `test_modes`, `test_state`, `test_cli`; manual integration checklist on macOS 14+

**Explicitly deferred to Dot:** floating chip overlay, `--port`, `--version`, expanded `--help`, CI workflow, error-message polish, SF Symbol icons, tooltips, `launchctl` / Homebrew docs.

**Exit criteria:**
- On a clean macOS 14+ machine: `pip install -e . && ephew` launches with the tray icon visible, hotkey active — **zero** macOS privacy prompts (no Accessibility, no Input Monitoring).
- `⌃⌥⌘V` advances the mode; the tray checkmark updates within ~100 ms. Clicking a mode in the menu also updates it.
- Running `claude` in each of the seven modes produces visibly different response shapes (binary = "yes"/"no", concise = one sentence, table = markdown table, etc.).
- Ctrl-C and tray → Quit both shut down cleanly within 3 s.
- `README.md` in the repo root documents install + usage.

## Phase 3 — Dot release (v1.1)

**Goal:** the deferred nice-to-haves. Everything past "bare minimum works" belongs here.

**Additive scope on top of MVP:**
- [spec-chip.md](./spec-chip.md) — the floating `NSWindow` overlay showing the current mode in a screen corner. Deferred from MVP because the tray checkmark already communicates mode; the chip is additive visual polish.
- [spec-cli.md](./spec-cli.md) — `--port N`, `--version`, expanded `--help` rendering the full modes table, structured startup-failure exits (exit 1 with a clear one-line reason)
- [spec-proxy.md](./spec-proxy.md) — tightened upstream-failure error messages; hardened header handling for edge cases surfaced during MVP use
- [spec-hotkey.md](./spec-hotkey.md) — improved collision-detection log line; menu-only fallback mentioned in the banner
- [spec-tray.md](./spec-tray.md) — SF Symbol icon if the asset pipeline is feasible; tooltip reflects current mode
- [spec-server.md](./spec-server.md) — clearer error surface on port-in-use
- [spec-testing.md](./spec-testing.md) — GitHub Actions CI running the unit suite on every PR; `test_chip` smoke test; `--port`/`--version` CLI tests
- Docs: `launchctl` login-item recipe, optional Homebrew-tap install instructions if popularity warrants

**Exit criteria:**
- At least one bug report or feature request from outside the author is closed in this release.
- CI is green on main.
- `CHANGELOG.md` describes what changed since v1.0.

## How phase annotations appear in the specs

Each `spec-*.md` file declares its phase with a `**Phase:**` callout immediately after the H1. Single-phase specs say so once. Specs that span phases (`spec-proxy.md`, `spec-cli.md`, `spec-testing.md`) break down what ships in each phase with a bullet list in the callout, and mark phase-specific sections in the body with `**[MVP]**` or `**[Dot]**` inline tags. The spec body itself describes the final end-state — what changes phase-over-phase is *which parts of that end-state are already implemented*.

A spec change that moves a feature between phases must update both this file and the affected spec's callout in the same commit.
