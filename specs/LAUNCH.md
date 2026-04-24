# Ephew — Launch Plan

Six phases between scratch and a community-tested open-source release. Phases 1–3 are internal milestones; Phases 4–6 take ephew public. Every `spec-*.md` file carries a `**Phase:**` callout near the top showing where its content lands; this document is the index and exit-criteria checklist.

## Versioning

This launch plan does not version each internal phase. The first **public** release — the artifact that lands on GitHub and PyPI at the end of Phase 6 — is **`v0.1.0`**. It bundles all of Phases 1–3. Subsequent feature work follows semver from there: `0.x` while the API/CLI surface is still moving, `1.0` when the surface is committed.

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

## Phase 2 — MVP (bare minimum feature works end-to-end)

**Goal:** the smallest surface that delivers the actual idea. User runs `ephew`, picks a mode, re-runs `claude`, *sees a visibly different response shape*. Everything optional is pushed to Dot.

**Additive scope on top of Pre-MVP:**
- [spec-modes.md](./spec-modes.md) — hard-coded `MODES` tuple, helpers, `DEFAULT`
- [spec-state.md](./spec-state.md) — `CurrentMode` with lock + subscribe/notify
- [spec-transform.md](./spec-transform.md) — pure directive-injection function
- [spec-proxy.md](./spec-proxy.md) — add transform integration on `POST /v1/messages` (reads `state.get()`, calls `transform.apply`, re-serializes, forwards). Passthrough behavior from Pre-MVP is preserved for every other path.
- [spec-tray.md](./spec-tray.md) — rumps `StatusItem`, menu with every mode, checkmark shows active mode, Quit handler. This is the *entire* MVP UI: the menu both *changes* the mode (click) and *shows* the mode (checkmark).
- [spec-hotkey.md](./spec-hotkey.md) — Carbon `RegisterEventHotKey` for `⇧⌘E`; no Accessibility prompt. The headline toggle feature.
- [spec-cli.md](./spec-cli.md) — full wiring: tray + hotkey + AppKit runloop; tray Quit and SIGINT both trigger clean shutdown.
- [spec-testing.md](./spec-testing.md) — unit tests `test_transform`, `test_modes`, `test_state`, `test_cli`; manual integration checklist on macOS 14+

**Explicitly deferred to Dot:** floating chip overlay, `--port`, `--version`, expanded `--help`, CI workflow, error-message polish, SF Symbol icons, tooltips, `launchctl` / Homebrew docs.

**Exit criteria:**
- On a clean macOS 14+ machine: `pip install -e . && ephew` launches with the tray icon visible, hotkey active — **zero** macOS privacy prompts (no Accessibility, no Input Monitoring).
- `⇧⌘E` advances the mode; the tray checkmark updates within ~100 ms. Clicking a mode in the menu also updates it.
- Running `claude` in each of the six modes produces visibly different response shapes (very-concise = yes/no or ≤5 words, concise = one sentence, table = markdown table, etc.).
- Ctrl-C and tray → Quit both shut down cleanly within 3 s.
- `README.md` in the repo root documents install + usage.

## Phase 3 — Polish (post-MVP refinements)

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

## Phase 4 — Launch preparedness

**Goal:** make the repo presentable, audited, and safe for public release. No new feature code; this phase is hygiene, docs, security sweep, and the ongoing-review tooling that keeps the project healthy after launch.

### Docs and metadata

- **License file** — `LICENSE` in repo root (MIT, matching `pyproject.toml`).
- **CHANGELOG.md** — initial entry for `v0.1.0` summarizing Phases 1–3.
- **SECURITY.md** — credential-handling guarantee (point at [spec-security.md](./spec-security.md)) + a vuln-disclosure email or process; explicitly list which classes of report we want (credential leak, header pass-through bug, RCE in proxy, etc.).
- **CONTRIBUTING.md** — spells out the **specs → tests → code** workflow, the per-spec section structure, the linting/type-checking/security commands, and how to file issues/PRs.
- **Issue + PR templates** — `.github/ISSUE_TEMPLATE/bug.md`, `.github/ISSUE_TEMPLATE/feature.md`, `.github/pull_request_template.md`.
- **README cleanup** — replace `<this-repo>` placeholder with the eventual GitHub URL; add badges (CI status, license, version, Python version) once the repo is public; verify modes table matches `MODES`.
- **`pyproject.toml`** — flesh out `authors`, add `urls.Homepage` / `urls.Repository`, add `keywords` and `classifiers`.

### One-time security sweep

- **Dependency CVE scan** — `pip-audit` (or `safety check`) against all runtime + dev deps. Resolve any high/critical advisories before publishing; document any deferred ones in `SECURITY.md`.
- **Static analysis** — `bandit -r ephew/`. Triage every finding; suppress with comment + reason or fix.
- **Manual security checklist** — walk the codebase against a written checklist:
  - Credential headers are never read into Python variables that outlive the request scope (see [spec-security.md](./spec-security.md)).
  - No `eval`, `exec`, or `compile` on untrusted input.
  - No `shell=True` subprocess calls; no `os.system`.
  - No `pickle.loads` (or any deserializer) on untrusted data.
  - Proxy upstream is hard-coded to `api.anthropic.com` — no user-controlled URL → no SSRF surface.
  - Listener binds only to `127.0.0.1` (assert with grep, not just spec).
  - All file paths in code are constants or test-only — no path traversal surface.
  - TLS verification is on by default (httpx default — confirm we don't disable it).
  - No telemetry, no third-party logging destination.
- **Git-history audit** — `git log --all -p | grep -iE 'sk-ant|api[_-]?key|bearer\s|password|secret|BEGIN [A-Z ]+PRIVATE KEY'` returns nothing across the whole repo history.

### Ongoing review readiness (set up before going public)

These pieces stay healthy on every PR, not just at launch:

- **Linting + formatting** — `ruff` configured in `pyproject.toml` (`[tool.ruff]`); covers what flake8 + black + isort used to. Run via `ruff check .` and `ruff format --check .`.
- **Type checking** — `mypy ephew/` on the source tree. Strict on `ephew/`, lenient on `tests/`. Configured in `pyproject.toml` (`[tool.mypy]`).
- **Security linting** — `bandit -r ephew/` integrated as a check in CI.
- **Dependency CVE scanning in CI** — `pip-audit` step runs on every PR; CI fails on high/critical advisories.
- **Automated dep updates** — `.github/dependabot.yml` configured for the `pip` ecosystem (monthly updates, grouped patch versions).
- **Pre-commit hooks** — `.pre-commit-config.yaml` runs `ruff`, `mypy`, and `bandit` locally on every commit. Documented in `CONTRIBUTING.md`.
- **CI workflow expansion** — extend `.github/workflows/test.yml` to run, in this order, on macOS and Linux: `ruff check`, `ruff format --check`, `mypy ephew/`, `bandit -r ephew/ -ll`, `pip-audit`, `pytest`. Any failure fails the run.

### Repository hygiene (the "looks like a real project" set)

- **`CODE_OF_CONDUCT.md`** — Contributor Covenant 2.1, lightly customized with the maintainer contact email.
- **`.editorconfig`** — LF line endings, UTF-8, 4-space indent for Python, 2-space for YAML/Markdown, trim trailing whitespace.
- **`.gitattributes`** — enforce LF line endings on text files; mark binary assets explicitly.
- **`pyproject.toml` classifiers** — full Trove set: `Development Status :: 3 - Alpha`, `License :: OSI Approved :: MIT License`, `Operating System :: MacOS`, `Operating System :: POSIX :: Linux`, `Programming Language :: Python :: 3`, `Programming Language :: Python :: 3.12`, `Topic :: Internet :: Proxy Servers`, `Topic :: Utilities`. Plus `keywords`, `urls.Homepage`, `urls.Repository`, `urls.Issues`, `urls.Changelog`.
- **`pyproject.toml` script aliases** — define `[tool.ephew.scripts]` (or use a `Makefile` / `tasks.py`) so the standard checks have one-word entry points: `make lint` / `make test` / `make check` / `make build`. Documented in `CONTRIBUTING.md`.
- **README badges** — once the repo is public: CI status, license, PyPI version, Python versions supported, code coverage. Pinned to the public URLs from Phase 5/6.
- **Coverage** — `pytest-cov` in dev deps; `[tool.coverage]` in `pyproject.toml`; CI step `pytest --cov=ephew --cov-report=term-missing --cov-fail-under=80`. Optional Codecov.io upload + badge.
- **Public API surface** — `__all__` exported from each module to make the importable surface explicit. `ephew.__init__` exports `__version__`.
- **`CITATION.cff`** — skipped (not academic; not warranted).
- **`.github/FUNDING.yml`** — skipped unless the maintainer wants sponsors.
- **`.github/CODEOWNERS`** — skipped while there is one maintainer; add when the team grows.

### Pre-flight smoke

- **Fresh-clone smoke** — `git clone` into `/tmp`, `python -m venv`, `pip install -e .[dev]`, then run the full check suite (`ruff`, `mypy`, `bandit`, `pip-audit`, `pytest --cov`). All green from zero state.
- **CI dry-run** — push to a private fork (or use `act`) to confirm the expanded `.github/workflows/test.yml` works on macOS and Linux.

### Exit criteria

- Root-level docs all exist and are reasonable: `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `README.md`.
- README contains no placeholder text and no broken links.
- `git log` is free of credential-shaped strings.
- `pip-audit` reports zero unresolved high/critical advisories.
- `bandit -r ephew/` reports zero unsuppressed findings.
- Manual security checklist is signed off (every box ticked or explicitly waived in `SECURITY.md`).
- `ruff check`, `ruff format --check`, `mypy ephew/`, `bandit -r ephew/`, `pip-audit`, and `pytest` all pass on `main` and in CI on both macOS and Linux.
- `.github/dependabot.yml`, `.pre-commit-config.yaml`, `.editorconfig`, `.gitattributes` exist and are functional.
- `pyproject.toml` has full Trove classifiers, keywords, project URLs, and dev-tool config (`[tool.ruff]`, `[tool.mypy]`, `[tool.coverage]`, `[tool.bandit]`).
- Test coverage ≥ 80% (or an explicit waiver in `CHANGELOG.md` for any module excluded).
- Fresh-clone install + full check suite is green.

## Phase 5 — Publish to GitHub

**Goal:** ephew is publicly visible at `github.com/<user>/ephew`, with a v0.1.0 release that external users can clone, star, and file issues against.

**Scope:**
- Create the public GitHub repository (description, topics: `claude`, `anthropic`, `proxy`, `cli`, `macos`, `python`).
- Push `main`; protect `main` (no direct pushes, PRs require CI green).
- Create the `v0.1.0` git tag; cut a GitHub Release using `CHANGELOG.md` content.
- Re-verify CI runs on the public repo (open a no-op PR to trigger).
- Update README install instructions and links from placeholders to the live URL.
- Optionally enable Discussions and pin a "feedback wanted" thread.

**Exit criteria:**
- Repo is public at the agreed URL.
- `v0.1.0` GitHub Release is live with release notes.
- CI green on `main` and on a representative PR.
- A fresh `git clone https://github.com/<user>/ephew && cd ephew && pip install -e . && ephew --version` works for a stranger.
- README links resolve.

## Phase 6 — Publish to easy-install channel

**Goal:** users can install ephew in one command from a package manager — no `git clone` required.

**Scope (primary — PyPI):**
- PyPI account + API token (or set up GitHub Actions trusted publishing).
- `python -m build` produces `dist/ephew-0.1.0.tar.gz` and `dist/ephew-0.1.0-py3-none-any.whl`.
- `twine upload dist/*` (or trusted-publishing workflow) ships to PyPI.
- Smoke test from a clean venv on a different machine: `pip install ephew && ephew --version` returns `ephew 0.1.0`.
- README install section updated to lead with `pip install ephew`.

**Scope (secondary — Homebrew tap, optional):**
- Create a separate public repo `<user>/homebrew-ephew`.
- Author `Formula/ephew.rb` using `Language::Python::Virtualenv`; depend on `python@3.12`.
- `brew tap <user>/ephew && brew install ephew` succeeds on a fresh Mac.
- Document `brew tap`/`brew install` in README as the macOS-friendly path.
- Skip the official `homebrew-cask` route until the project is mature (popularity thresholds, signing requirements).

**Exit criteria:**
- `pip install ephew` succeeds from a clean machine and `ephew --version` prints `0.1.0`.
- (If Homebrew path taken) `brew tap` + `brew install` succeed and `ephew --version` prints `0.1.0`.
- README install section reflects the new one-liner.
- `CHANGELOG.md` has a `[0.1.0] — published <date>` entry.
- The version tag, the PyPI release, and (if applicable) the Homebrew formula all reference the same `0.1.0` artifact.

## How phase annotations appear in the specs

Each `spec-*.md` file declares its phase with a `**Phase:**` callout immediately after the H1. Single-phase specs say so once. Specs that span phases (`spec-proxy.md`, `spec-cli.md`, `spec-testing.md`) break down what ships in each phase with a bullet list in the callout, and mark phase-specific sections in the body with `**[MVP]**` or `**[Dot]**` inline tags. The spec body itself describes the final end-state — what changes phase-over-phase is *which parts of that end-state are already implemented*.

A spec change that moves a feature between phases must update both this file and the affected spec's callout in the same commit.
