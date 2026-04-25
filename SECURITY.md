# Security policy

## Supported versions

Ephew is in `0.x` — only the latest minor (currently `0.1.x`) receives fixes. Please run a recent release before reporting issues.

## Reporting a concern

Do **not** open a public GitHub issue for security-sensitive findings. Instead:

- Open a private security advisory via GitHub: <https://github.com/etherops/ephew/security/advisories/new>
- Or email the maintainer at the address listed on their GitHub profile.

You can expect an acknowledgement within a few days. Coordinated-disclosure timelines are negotiable; the default is 90 days from acknowledgement.

## What we want to hear about

The credential-handling guarantee in `specs/spec-security.md` is the project's most important promise. Reports that demonstrate any of the following are highest priority:

- Credential header values appearing in log output, stdout, or stderr.
- Credential header values being read into Python variables that outlive the request scope.
- The proxy forwarding requests to anything other than `api.anthropic.com`.
- The listener binding to anything other than `127.0.0.1` under default configuration.
- The proxy modifying or recording user message content beyond the documented directive append.
- Any path where the daemon causes a credential to enter an LLM context (logs, exception messages, tracebacks).

## What's out of scope

- Issues that require the attacker to already control the user's local machine.
- Issues with third-party tools (e.g. `httpx`, `uvicorn`, `rumps`) that don't affect ephew's documented behavior — please report those upstream.
- Feature requests dressed as security concerns.

## Our process

1. Triage the report against `specs/spec-security.md`.
2. If the report is in scope, write a failing test that reproduces it.
3. Fix; release a patch version; credit the reporter in `CHANGELOG.md` (with permission).

## Background

For the full technical model — what the daemon must never do, how the redaction filter works, what the unit tests defend — read `specs/spec-security.md`.
