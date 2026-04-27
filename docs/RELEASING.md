# Releasing ephew

How a new version of ephew makes its way to GitHub, PyPI, and Homebrew. Read this if you're cutting a release; skip otherwise.

## The shape of a release

Every release is the same artifact in three places:

1. A `vX.Y.Z` git tag in `etherops/ephew`.
2. A GitHub Release at `https://github.com/etherops/ephew/releases/tag/vX.Y.Z` with notes from `CHANGELOG.md`.
3. A `pip`-installable package on PyPI at `https://pypi.org/project/ephew/X.Y.Z/`.
4. A Homebrew formula update in `etherops/homebrew-funstuff` referencing the new tag.

Steps 1 and 2 are manual (you tag and create the release). Step 3 happens automatically when the tag is pushed, *if* PyPI trusted publishing is set up (see below). Step 4 is semi-automatic — you bump `Formula/ephew.rb` and push.

## One-time setup: PyPI trusted publishing

This is the **only** manual PyPI step you ever do. It replaces the old "generate an API token, paste it as a GitHub secret" pattern with a more secure flow where PyPI verifies an OIDC claim from GitHub Actions.

> **Status as of v0.1.1:** publishing to PyPI is **not yet wired up**. The workflow file `.github/workflows/publish.yml` is currently **manual-trigger only** (`workflow_dispatch`) so tag pushes don't generate failure emails. Complete the registration steps below, then re-enable the tag-push trigger by uncommenting the `push.tags` block at the top of `publish.yml`.

### What trusted publishing is

When `.github/workflows/publish.yml` runs on a tag push, it requests a short-lived OIDC token from GitHub. PyPI receives that token along with the upload, verifies it came from the exact repo + workflow + environment you registered, and accepts the upload — no long-lived secret stored anywhere.

Benefits:

- No PyPI API token in the repo or in GitHub secrets.
- Tokens are scoped to a single workflow run; stolen tokens expire in minutes.
- If the workflow file moves or is renamed, PyPI rejects the upload until you re-register.

### One-time registration steps

Do these once, ever:

1. **Sign in to PyPI** at <https://pypi.org/account/login/>. If you don't have an account, register one — use a strong unique password and turn on 2FA.

2. **Open the publishing settings page:** <https://pypi.org/manage/account/publishing/>.

3. Scroll to **"Add a new pending publisher"** (the project name `ephew` doesn't exist on PyPI yet, so it's *pending* until the first upload lands; after that, it becomes a normal published project).

4. **Fill in the form exactly as below:**

   | Field | Value |
   |---|---|
   | PyPI Project Name | `ephew` |
   | Owner | `etherops` |
   | Repository name | `ephew` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The "Environment name" must match the `environment.name` field in `.github/workflows/publish.yml` (which is `pypi`). PyPI uses this to scope which workflow runs are allowed to upload.

5. Click **"Add"**. You should see the new pending publisher listed.

That's it. PyPI now trusts uploads from `etherops/ephew`'s `publish.yml` workflow when it runs in the `pypi` environment.

### Confirming the GitHub Environment exists

The workflow references `environment: name: pypi`. GitHub creates the environment lazily on first workflow run, but you can also create it ahead of time:

1. <https://github.com/etherops/ephew/settings/environments>
2. **"New environment"** → name it `pypi` → save.
3. (Optional but recommended) Add deployment protection rules — e.g. only allow tags matching `v*` to deploy. This is belt-and-suspenders on top of PyPI's verification.

## Cutting a release (every time, after the one-time setup)

1. **Make sure `main` is green.** All checks (ruff, mypy, bandit, pip-audit, pytest+cov) pass on the latest commit.

2. **Update `CHANGELOG.md`.** Move items from `[Unreleased]` into a new `[X.Y.Z] — YYYY-MM-DD` section. Commit on `main` (or via PR if you're being strict).

3. **Bump the version** in two places:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `ephew/__init__.py` → `__version__ = "X.Y.Z"`

   Commit these together: `git commit -am "release: vX.Y.Z"`.

4. **Tag and push:**
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin main
   git push origin vX.Y.Z
   ```

   The tag push triggers `.github/workflows/publish.yml`. Watch it at <https://github.com/etherops/ephew/actions>.

5. **Verify PyPI publish.** Within a few minutes:
   ```bash
   pipx install --force ephew==X.Y.Z
   ephew --version    # → ephew X.Y.Z
   ```
   Or visit <https://pypi.org/project/ephew/X.Y.Z/> directly.

6. **Cut the GitHub Release:**
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag
   # or paste the CHANGELOG section as --notes
   ```

7. **Update the Homebrew formula** in `etherops/homebrew-funstuff`:
   - Compute the new tarball SHA256:
     ```bash
     curl -sL https://github.com/etherops/ephew/archive/refs/tags/vX.Y.Z.tar.gz \
       | shasum -a 256
     ```
   - Edit `Formula/ephew.rb`: bump `url` to the new tag, paste the new `sha256`. **That's it** — no resource blocks to maintain (see below).
   - Commit and push the tap repo.

8. **Smoke-test the brew install:**
   ```bash
   brew update
   brew upgrade ephew
   ephew --version    # → ephew X.Y.Z
   ```

## Why the formula has no `resource` blocks

The standard `Language::Python::Virtualenv` mixin requires a `resource` block per transitive Python dep, with pinned URL + SHA256, and forces `pip install --no-binary :all:`. We deliberately don't use it.

Two reasons:

1. **It broke installs on Macs with mismatched SDKs.** `--no-binary :all:` made pip compile `pyobjc-core` and `pyobjc-framework-Cocoa` from source. On Macs where Xcode SDK and Command Line Tools SDK are at different macOS versions (very common — e.g. Xcode 26.2 alongside CLT 26.3), that compile fails with `superenv`-injected SDK mismatches.
2. **Per-release maintenance burden.** Every release would mean regenerating ~13 resource blocks, fetching new URLs and SHA256s, diffing them carefully.

Instead, the formula uses a small custom `def install` that runs `pip install --prefer-binary buildpath`. pip resolves and installs deps fresh from PyPI at install time, using prebuilt wheels for pyobjc (skipping the compile) and source for pure-Python deps (where it's instant anyway).

Tradeoff: less reproducible — pip picks dep versions at install time based on `pyproject.toml`'s constraints, not pinned. For a small daemon this is fine. If reproducibility ever matters more than install-success, the path is: pin every runtime dep with `==` in `pyproject.toml`.

## Yanking a bad release

If you ship a broken version:

1. **Don't delete the tag** — that breaks anyone who's already installed it.
2. **Yank from PyPI:** `pip-yank` or via the PyPI web UI ("Manage" → version → "Yank release"). Yanked versions stay installable for people who pinned to them but won't be selected by `pip install ephew`.
3. **Update the brew formula** to point at the previous good tag.
4. **Cut a fixed `X.Y.Z+1`** and follow the normal release process.

## Versioning policy

This project follows [SemVer](https://semver.org/):

- `0.x.y` — pre-1.0, breaking changes allowed in minor bumps. Document them prominently in `CHANGELOG.md`.
- `1.0.0` — first stable release. Public API/CLI surface committed.
- After 1.0: breaking changes require a major bump (`2.0.0`).

The "public API" includes: the `ephew` CLI flags, the `MODES` tuple's mode names and their *meaning* (directive wording can shift within reason), the proxy's environment variables (`EPHEW_PORT`, `ANTHROPIC_BASE_URL` honoring), and the validation log line shape.
