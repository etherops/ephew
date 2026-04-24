# ephew

Local verbosity-toggle proxy for the Anthropic API. Run it, point any Claude client (Claude Code, the `anthropic` SDK, `curl`) at `127.0.0.1`, press `⇧⌘E` to cycle the response-length mode, and watch Claude's reply shape change — all without editing prompts by hand.

## Why

Claude Code (and every other Anthropic-API client) has no fast way to toggle response verbosity mid-conversation. Today you retype *"one sentence"* / *"yes-or-no"* / *"as a table"* over and over. Ephew injects the right directive into each outgoing `/v1/messages` request based on a mode you pick with a hotkey — zero prompt editing, zero context switching, a tiny glyph in the menu bar so you always know which mode is active.

## Install

```bash
git clone <this-repo>
cd ephew
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.12+ and macOS. Linux will run the proxy headlessly but without the tray, chip, or hotkey.

## Run

```bash
ephew
```

You'll see a banner:

```
ephew 1.1.0 running on http://127.0.0.1:47821
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

Cycle with `⇧⌘E`, or click a mode in the menu-bar dropdown. The title reads `fu <glyph>` so you always know which mode is active:

| Glyph | Mode | Response shape |
|---|---|---|
| `.` | very concise | Yes/no if possible, max 5 words otherwise |
| `..` | concise | One sentence |
| `-` | normal | Passthrough — no modification |
| `"` | thorough | Reasoning, tradeoffs, an example |
| `""` | very thorough | Deep — reasoning, tradeoffs, edge cases (skip padding) |
| `⊞` | table | Markdown table only, no prose |

Startup mode is always `normal`. Cycle order: very-concise → concise → normal → thorough → very-thorough → table → (wrap).

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
