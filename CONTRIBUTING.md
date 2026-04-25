# Contributing to ephew

Thanks for considering a contribution. The repo follows a strict spec-first workflow; reading this once will save you the back-and-forth.

## The cardinal rule: specs → tests → code

Every change, no matter how small, lands in this order:

1. **Specs first.** Update the relevant `specs/spec-<name>.md` (and `specs/LAUNCH.md` if the change affects phase scope) to describe the new end-state. Specs are the contract.
2. **Tests next.** Add or modify tests so they pass only when the new spec is satisfied. Tests lock in the spec before any implementation exists.
3. **Code last.** Once specs and tests agree, write or edit the implementation. Run the full check suite before submitting.

This isn't a stylistic preference — it's the mechanism that keeps `specs/` authoritative as the project grows. PRs that change code without first updating specs will be sent back.

## Setup

```bash
git clone git@github.com:etherops/ephew.git
cd ephew
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install   # if .pre-commit-config.yaml is present
```

Python 3.12+ required. macOS for the full daemon experience (tray, hotkey); Linux for headless proxy work.

## Running checks locally

The same checks CI runs:

```bash
ruff check .                      # lint
ruff format --check .             # formatting
mypy ephew/                       # type checking
bandit -r ephew/ -ll              # security lint (low-level and above)
pip-audit                         # dependency CVE scan
pytest --cov=ephew --cov-report=term-missing
```

All of these must pass before a PR is mergeable.

## Spec structure

Every `spec-*.md` follows the same six sections:

1. **Purpose** — what this feature does and why
2. **Public surface** — exported functions/classes, signatures, invariants
3. **Behavior** — runtime behavior, including edge cases
4. **Dependencies** — upstream and downstream
5. **Out of scope** — explicit non-goals
6. **Verification** — how to test in isolation

Plus a `**Phase:**` callout near the top mapping the spec to a launch phase (see `specs/LAUNCH.md`).

## Pull requests

- Branch from `main`.
- Keep PRs focused — one feature or fix per PR.
- The PR description should reference the spec change(s) it implements.
- CI must be green.
- Commits should follow the `<area>: <imperative summary>` style (look at `git log` for examples).

## Filing issues

- **Bug reports:** include reproduction steps, expected vs actual behavior, and the output of `ephew --version`.
- **Feature requests:** describe the user-facing problem first; proposed solutions second.

## Reporting security concerns

Please don't open a public issue for credential leaks, header pass-through bugs, or other security-sensitive findings. See `SECURITY.md` for the disclosure path.

## Code style

- Type hints on all public functions.
- Docstrings only when the *why* isn't obvious from names — never to restate what the code does.
- One short comment per non-obvious line; no multi-paragraph comment blocks.
- Function names: snake_case, action verbs.
- Module names: short, all lowercase.

`ruff` enforces most of this mechanically. When in doubt, follow the surrounding code.
