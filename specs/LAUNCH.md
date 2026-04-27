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

## Phase 5 — Make the GitHub repo public

**Goal:** ephew is publicly visible at `github.com/etherops/ephew`, with a `v0.1.0` release that external users can clone, star, and file issues against. This phase is the **hard prerequisite** for Phase 6 — Homebrew taps require a public source repo.

**Scope:**
- Flip `etherops/ephew` from private → public. Add description and topics: `claude`, `anthropic`, `proxy`, `cli`, `macos`, `python`, `verbosity`.
- Protect `main`: no direct pushes; PRs require CI green; require linear history.
- Create the `v0.1.0` git tag; cut a GitHub Release using the `[0.1.0]` section of `CHANGELOG.md` as release notes.
- Re-verify CI runs on the public repo (open a no-op PR to trigger).
- Update README install instructions and links — though the brew install path lands in Phase 6, so the v0.1.0 README can have placeholder text saying "brew install via tap, see CHANGELOG" until Phase 6 wraps up.
- Optionally enable Discussions and pin a "feedback wanted" thread.

**Exit criteria:**
- `https://github.com/etherops/ephew` is publicly accessible.
- Tag `v0.1.0` exists and is pushed; GitHub Release `v0.1.0` is published with release notes.
- CI green on `main` and on a representative PR.
- A stranger can `git clone https://github.com/etherops/ephew && cd ephew && pip install -e . && ephew --version` and have it work.
- All README links resolve (or are explicitly marked "coming in Phase 6").

## Phase 6 — Publish to PyPI and Homebrew

**Goal:** users install ephew in one command from either Homebrew (macOS) or pip (any platform). Both channels ship at the same `v0.1.0` tag and reference the same source artifact.

**Hard prerequisite:** Phase 5 must complete first. Homebrew taps require a *public* GitHub repository. `brew tap` clones the formula repo over plain HTTPS; private repos break the install for everyone but you.

### Scope

**1. Create the tap repository.**

A second public repo, separate from `etherops/ephew`:

- Name: `etherops/homebrew-funstuff` (the `homebrew-` prefix is mandatory; brew strips it when computing the tap name).
- Visibility: public.
- Contents: a single directory `Formula/` with a single file `ephew.rb`. Plus a small `README.md` explaining how to tap.
- License: MIT (same as the main repo).

**2. Author `Formula/ephew.rb`.**

The formula uses a **custom install method** rather than the standard `Language::Python::Virtualenv` mixin. The mixin would force `pip install --no-binary :all:` for every transitive dep, which makes pip compile `pyobjc-core` and `pyobjc-framework-Cocoa` from source. That compile fails on any Mac where the Xcode SDK and Command Line Tools SDK don't perfectly align (a common situation — e.g. Xcode 26.2 vs CLT 26.3). The custom approach lets pip use prebuilt wheels for pyobjc, which sidesteps the compile entirely.

```ruby
class Ephew < Formula
  desc "Local verbosity-toggle proxy for the Anthropic API"
  homepage "https://github.com/etherops/ephew"
  url "https://github.com/etherops/ephew/archive/refs/tags/v0.1.1.tar.gz"
  sha256 "FILL_IN_AFTER_TAGGING"
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = libexec
    system Formula["python@3.12"].opt_bin/"python3.12", "-m", "venv", venv
    system venv/"bin/pip", "install", "--upgrade", "pip"
    system venv/"bin/pip", "install", "--prefer-binary", buildpath
    bin.install_symlink venv/"bin/ephew"
  end

  test do
    assert_match "ephew #{version}", shell_output("#{bin}/ephew --version")
  end
end
```

**3. Why no `resource` blocks.**

We deliberately omit `resource` blocks — pip resolves and installs all deps fresh from PyPI at install time. This is non-idiomatic for `homebrew/core` (which requires reproducible source-only builds), but acceptable for a third-party tap because:

- Reproducibility is bounded by `pyproject.toml`'s version constraints.
- The compile-from-source policy is what was breaking installs on macs with mismatched SDKs in the first place.
- `--prefer-binary` lets pip use wheels where they exist (pyobjc) and source-build pure-Python deps where they don't matter.
- Install time drops from ~10–20 minutes to **~8 seconds** for a fresh install.

If we ever need full reproducibility back, the path is: pin every dep with `==` in `pyproject.toml`, optionally re-add `resource` blocks generated from the lockfile.

Pin all resources to source distributions (`.tar.gz`), not wheels — formulas need source so brew can verify checksums and build from a known-clean state.

**4. Test the formula locally.**

```bash
brew tap etherops/funstuff
brew install --build-from-source ephew
ephew --version          # → ephew 0.1.0
ephew                    # tray icon appears, hotkey registers
brew test ephew          # runs the formula's `test do` block
brew uninstall ephew
brew untap etherops/funstuff
```

The `--build-from-source` flag forces brew to actually exercise the formula's install steps rather than pulling a pre-built bottle (which doesn't exist for a tap formula anyway).

**5. Cut the release.**

Order matters because the formula's `url` line points at a tagged GitHub tarball:

1. In `etherops/ephew`: tag `v0.1.0` and push the tag (see Phase 5 exit criteria).
2. Compute the tarball SHA256: `curl -sL https://github.com/etherops/ephew/archive/refs/tags/v0.1.0.tar.gz | shasum -a 256`.
3. In `etherops/homebrew-funstuff`: paste the SHA256 into `Formula/ephew.rb`.
4. Test (step 4 above).
5. Push to the tap repo. Done.

**6. Document the install path.**

In `etherops/ephew/README.md`, replace the current `git clone … && pip install -e .` block with:

```bash
brew tap etherops/funstuff
brew install ephew
ephew                  # starts the daemon
```

Keep the `git clone` instructions in `CONTRIBUTING.md` for developers; the README leads with brew.

### PyPI publish

- **Trusted publishing via GitHub Actions** — no long-lived API token in the repo. PyPI verifies an OIDC claim from the publish workflow.
- Workflow file: `.github/workflows/publish.yml`. Triggers on a pushed `v*` tag.
- Workflow steps: `python -m build` → `pypa/gh-action-pypi-publish` → upload `dist/*.tar.gz` and `dist/*.whl`.
- **One-time PyPI setup (manual, by maintainer):** at <https://pypi.org/manage/account/publishing/>, register a pending publisher for the project name `ephew` pointing at `etherops/ephew`, workflow `publish.yml`, environment `pypi`. After the first publish lands, the project becomes a normal published project.
- Local dry-run before tagging: `python -m build` produces both sdist and wheel; `twine check dist/*` validates the metadata; install into a fresh venv to confirm.
- Smoke test post-publish: `pipx install ephew --pip-args='--no-cache-dir'` on a fresh shell, then `ephew --version` returns `0.1.0`.

### Documenting the install paths

In `etherops/ephew/README.md`, the install section after Phase 6 reads:

```
## Install

### macOS (recommended)
brew tap etherops/funstuff
brew install ephew

### Other platforms
pipx install ephew      # or: pip install ephew
```

Keep the `git clone … && pip install -e .` block in `CONTRIBUTING.md` for developers; the README leads with the user-facing channels.

### Exit criteria

- `etherops/homebrew-funstuff` repo exists (public, MIT) with `Formula/ephew.rb` and a small README.
- `brew tap etherops/funstuff && brew install ephew` succeeds on a fresh Mac (or a clean test account on the dev Mac).
- `pipx install ephew` (or `pip install ephew` into a fresh venv) succeeds and `ephew --version` prints `0.1.0`.
- `brew test ephew` is green.
- `etherops/ephew/README.md` install section documents both channels with brew first.
- `CHANGELOG.md` has a `[0.1.0] — published <date>` entry referencing the GitHub Release, the PyPI release, and the brew tap.
- `https://pypi.org/project/ephew/0.1.0/` resolves and shows the same description as the GitHub repo.

## How phase annotations appear in the specs

Each `spec-*.md` file declares its phase with a `**Phase:**` callout immediately after the H1. Single-phase specs say so once. Specs that span phases (`spec-proxy.md`, `spec-cli.md`, `spec-testing.md`) break down what ships in each phase with a bullet list in the callout, and mark phase-specific sections in the body with `**[MVP]**` or `**[Dot]**` inline tags. The spec body itself describes the final end-state — what changes phase-over-phase is *which parts of that end-state are already implemented*.

A spec change that moves a feature between phases must update both this file and the affected spec's callout in the same commit.
