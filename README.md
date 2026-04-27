# ephew

Local verbosity-toggle proxy for the Anthropic API. Run it, point any Claude client (Claude Code, the `anthropic` SDK, `curl`) at `127.0.0.1`, press `⇧⌘E` to cycle the response-length mode, and watch Claude's reply shape change — all without editing prompts by hand.

## Why

Claude Code (and every other Anthropic-API client) has no fast way to toggle response verbosity mid-conversation. Today you retype *"one sentence"* / *"yes-or-no"* / *"as a table"* over and over. Ephew injects the right directive into each outgoing `/v1/messages` request based on a mode you pick with a hotkey — zero prompt editing, zero context switching, a tiny glyph in the menu bar so you always know which mode is active.

## Install

```bash
brew tap etherops/funstuff
brew install ephew
```

Requires Python 3.12+ and macOS (the menu-bar tray + global hotkey are macOS-only).

For development setup (`git clone` + editable install + tests), see [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Run

```bash
ephew
```

You'll see a banner:

```
ephew 0.1.0 running on http://127.0.0.1:47821
point your Anthropic client at this proxy:
  export ANTHROPIC_BASE_URL=http://127.0.0.1:47821
hotkey: ⇧⌘E to cycle modes
```

Then in any terminal:

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:47821
claude "is python compiled"
```

The request flows through ephew → `api.anthropic.com` → back to your client. Claude's reply shape now depends on the active mode.

## Modes

Cycle with `⇧⌘E`, or click a mode in the menu-bar dropdown. The title reads `ephew <glyph>` so you always know which mode is active:

| Glyph | Mode | Response shape |
|---|---|---|
| `-x` | none | Passthrough — no modification |
| `-c` | concise | Fewest words possible; one-sentence cap |
| `-p` | paragraph | 2 paragraphs max; biased toward the shortest response that fits |
| `-v` | verbose | Deep — reasoning, tradeoffs, edge cases (skip padding) |
| `-t` | table | Markdown table only, no prose |

Startup mode is always `none`. Cycle order: none → concise → paragraph → verbose → table → (wrap).

### Per-request override

Append a flag to the very end of any prompt to one-shot a specific mode without touching the tray:

```bash
claude "explain go channels -v"        # forces verbose for this request
claude "list HTTP status codes -t"     # forces table
claude "summarize the rfc -p"          # forces a single dense paragraph
claude "is python interpreted -c"      # forces concise
claude "just chat -x"                  # forces passthrough
```

The flag (`-x`/`-c`/`-p`/`-v`/`-t` or the long forms `--none`/`--concise`/`--paragraph`/`--verbose`/`--table`) is stripped before the request is forwarded; the active tray mode is **not** modified. Each override is logged with `mode=<chosen> override=<flag>` so you can audit.

## Flags

- `--port N` — override the default proxy port (`47821`). Also honors the `EPHEW_PORT` environment variable.
- `--verbose` / `-v` — extend the per-request log line with the full directive text, *and* annotate each tray menu item with its directive in parens.
- `--version` — print version and exit.
- `--help` — print help including the modes table.

## How it works

Ephew is a local HTTP proxy that impersonates `api.anthropic.com` on `127.0.0.1`. Setting `ANTHROPIC_BASE_URL` points any Anthropic-compatible client at the proxy. For every `POST /v1/messages`:

1. Read the active mode from shared state.
2. If the mode has a directive, append it after `\n\n` to the last user message in the request body. No brackets, no tags — a natural P.S.
3. Forward the (possibly modified) request to real `api.anthropic.com`.
4. Stream the response (SSE) back to the client unchanged.

The mode is toggled in real time via a global hotkey — Carbon `RegisterEventHotKey`, **no macOS Accessibility permission required** — or the menu-bar dropdown. Every mode change logs one line on `ephew.state`.

## Credential safety

Ephew sits between your client and the Anthropic API. The daemon:

- Never reads `x-api-key` / `authorization` values into its own context.
- Redacts those header names (case-insensitive) from any log output via a compile-time `logging.Filter`.
- Never logs request bodies, response bodies, or user message content.
- Logs exactly one line per request: `proxy method=POST path=/v1/messages upstream_status=200 bytes=12345 mode=concise`.
- Under `--verbose`, extends that line with the *directive* (ephew's own string, not the user's content).

## Run at login (optional)

Keep ephew running across logins with `launchctl`. Create `~/Library/LaunchAgents/com.patrickkennel.ephew.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.patrickkennel.ephew</string>
    <key>ProgramArguments</key>
    <array>
      <string>/ABSOLUTE/PATH/TO/ephew/.venv/bin/ephew</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardErrorPath</key>
    <string>/tmp/ephew.log</string>
  </dict>
</plist>
```

Load: `launchctl load ~/Library/LaunchAgents/com.patrickkennel.ephew.plist`
Unload: `launchctl unload ~/Library/LaunchAgents/com.patrickkennel.ephew.plist`

## Development

Specs live in [`specs/`](./specs/). Every feature has a `spec-<name>.md` covering purpose, public surface, behavior, dependencies, out-of-scope, and verification. The three-phase launch plan is [`specs/LAUNCH.md`](./specs/LAUNCH.md). The project workflow is strict: **specs → tests → code**, in that order, for every change.

```bash
pytest                # full suite, no API key or network needed
pytest -v -k modes    # narrow by keyword
```

## License

MIT.
