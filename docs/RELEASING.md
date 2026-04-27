# Releasing ephew

How a new version of ephew makes its way to GitHub and Homebrew. Read this if you're cutting a release; skip otherwise.

A release produces:

1. A `vX.Y.Z` git tag in `etherops/ephew`.
2. A GitHub Release at `https://github.com/etherops/ephew/releases/tag/vX.Y.Z` with notes from `CHANGELOG.md`.
3. A Homebrew formula update in `etherops/homebrew-funstuff` referencing the new tag.

## Cutting the release

1. **Bump versions** in `pyproject.toml` and `ephew/__init__.py` to the new `X.Y.Z`.
2. **Update `CHANGELOG.md`** — add an `[X.Y.Z]` entry under the `[Unreleased]` heading.
3. **Commit + tag**:
   ```bash
   git commit -am "release: vX.Y.Z"
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin main
   git push origin vX.Y.Z
   ```
4. **Create the GitHub Release** (optional but recommended):
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag
   ```
5. **Update the Homebrew formula** in `etherops/homebrew-funstuff`:
   ```bash
   curl -sL https://github.com/etherops/ephew/archive/refs/tags/vX.Y.Z.tar.gz \
     | shasum -a 256
   # Edit Formula/ephew.rb: bump url + sha256.
   git -C ~/path/to/homebrew-funstuff commit -am "formula: bump to vX.Y.Z"
   git -C ~/path/to/homebrew-funstuff push
   ```
6. **Smoke test**:
   ```bash
   brew update && brew upgrade ephew
   ephew --version   # should print X.Y.Z
   ```

## Homebrew formula notes

The formula uses a custom `def install` that runs `pip install --prefer-binary buildpath` rather than the standard `Language::Python::Virtualenv` mixin. The mixin would force `pip install --no-binary :all:`, which makes pip compile `pyobjc-core` and `pyobjc-framework-Cocoa` from source. That compile fails on any Mac where the Xcode SDK and Command Line Tools SDK don't perfectly align (a common situation — e.g. Xcode 26.2 vs CLT 26.3).

`--prefer-binary` lets pip use prebuilt wheels for pyobjc and source-build the pure-Python deps where it's instant. Tradeoff: less reproducible (pip resolves at install time) but vastly more reliable.

## Yanking a bad release

1. Delete the bad tag and cut a new patch version: `git push origin :refs/tags/vX.Y.Z`, then tag the fix and push.
2. Revert the formula in `etherops/homebrew-funstuff` to the previous version (`url` + `sha256`).
3. Cut a fixed `X.Y.Z+1` and follow the normal release process above.
