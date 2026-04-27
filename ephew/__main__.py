from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from ephew import __version__


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        return _run_setup(args)

    return _run_daemon(args)


# ---------------------------------------------------------------------------
# argparse


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ephew",
        description="Local verbosity-toggle proxy for the Anthropic API.",
        epilog=_modes_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ephew {__version__}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="N",
        help="proxy port (overrides EPHEW_PORT env var; default 47821)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="extend per-request log with directive text; annotate tray menu items",
    )

    subparsers = parser.add_subparsers(dest="command")

    setup_p = subparsers.add_parser(
        "setup",
        help="emit the ANTHROPIC_BASE_URL export so Claude clients route through ephew",
        description=(
            "Helper to set ANTHROPIC_BASE_URL so claude / anthropic SDK / curl route through "
            "this ephew daemon. Bare `ephew setup` prints instructions; `--print` emits the "
            "export line for `eval`; `--append-rc` writes it to your shell rc once."
        ),
    )
    setup_p.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help='emit just the export line, suitable for `eval "$(ephew setup --print)"`',
    )
    setup_p.add_argument(
        "--append-rc",
        action="store_true",
        help="append the export to your shell rc (~/.zshrc, etc.) for persistent setup",
    )
    setup_p.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="N",
        help="port to use in the URL (overrides EPHEW_PORT; default 47821)",
    )

    return parser


def _modes_epilog() -> str:
    from ephew.modes import MODES

    lines = ["modes (cycle in order; hotkey ⇧⌘E):"]
    glyph_w = max(len(m.glyph) for m in MODES)
    display_w = max(len(m.display) for m in MODES)
    for mode in MODES:
        directive = mode.directive if mode.directive else "passthrough — no directive appended"
        lines.append(f"  {mode.glyph:<{glyph_w}}  {mode.display:<{display_w}}  {directive}")
    lines.append("")
    lines.append("per-request override (append to the last line of your prompt):")
    lines.append("  -x / --none      one-shot passthrough")
    lines.append("  -c / --concise   one-shot concise")
    lines.append("  -v / --verbose   one-shot verbose")
    lines.append("  -t / --table     one-shot table")
    return "\n".join(lines)


def _resolve_port(port_flag: int | None) -> int:
    if port_flag is not None:
        return port_flag
    env = os.environ.get("EPHEW_PORT")
    if env:
        return int(env)
    return 47821


# ---------------------------------------------------------------------------
# `ephew setup` subcommand


def _run_setup(args: argparse.Namespace) -> int:
    port = _resolve_port(args.port)
    url = f"http://127.0.0.1:{port}"

    if args.append_rc:
        return _append_rc(url)

    if args.print_only:
        print(f"export ANTHROPIC_BASE_URL={url}")
        return 0

    # Default: friendly multi-line message.
    print(f"To route Claude clients through ephew, set ANTHROPIC_BASE_URL to {url}.")
    print()
    print("Apply to the current shell:")
    print('  eval "$(ephew setup --print)"')
    print()
    print("Persist across shells (writes to ~/.zshrc / ~/.bashrc / fish config):")
    print("  ephew setup --append-rc")
    return 0


_RC_MARKER = "# ephew"


def _append_rc(url: str) -> int:
    shell = os.environ.get("SHELL", "/bin/bash").rsplit("/", 1)[-1]
    home = Path(os.environ.get("HOME", str(Path.home())))

    if shell == "fish":
        rc = home / ".config" / "fish" / "config.fish"
        line = f"set -gx ANTHROPIC_BASE_URL {url}  {_RC_MARKER}"
    else:
        rc = {
            "zsh": home / ".zshrc",
            "bash": home / ".bashrc",
        }.get(shell, home / ".profile")
        line = f"export ANTHROPIC_BASE_URL={url}  {_RC_MARKER}"

    rc.parent.mkdir(parents=True, exist_ok=True)
    existing = rc.read_text() if rc.exists() else ""

    if _RC_MARKER in existing:
        print(f"ephew: {rc} already contains an ephew line; leaving it alone.", file=sys.stderr)
        return 0

    with rc.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(line + "\n")
    print(f"ephew: appended ANTHROPIC_BASE_URL line to {rc}.", file=sys.stderr)
    print(f"  open a new shell, or run: source {rc}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Daemon mode (default — no subcommand)


def _run_daemon(args: argparse.Namespace) -> int:
    # Import after parse_args so --help / --version don't drag in macOS-only deps.
    import httpx
    import rumps

    from ephew.activity import ActivityNotifier
    from ephew.hotkey import HotkeyRegistration
    from ephew.modes import DEFAULT
    from ephew.proxy import build_app
    from ephew.security import install_redaction
    from ephew.server import PortInUseError, ProxyServer
    from ephew.state import CurrentMode
    from ephew.tray import TrayApp

    install_redaction()
    _configure_logging(verbose=args.verbose)

    port = _resolve_port(args.port)

    state = CurrentMode(initial=DEFAULT)
    activity = ActivityNotifier()

    upstream_client = httpx.AsyncClient(
        base_url="https://api.anthropic.com",
        http2=False,
        timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=10.0),
    )
    app = build_app(upstream_client, state, activity=activity)
    server = ProxyServer(app, port=port)

    try:
        server.start()
    except PortInUseError as exc:
        print(f"ephew: failed to start — {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ephew: failed to start — {exc}", file=sys.stderr)
        return 1

    hotkey = HotkeyRegistration(on_press=state.cycle)
    hotkey_installed = hotkey.install()

    _print_banner(server.url, hotkey_installed)

    shutdown_flag = {"fired": False}

    def shutdown() -> None:
        if shutdown_flag["fired"]:
            return
        shutdown_flag["fired"] = True
        try:
            hotkey.uninstall()
        except Exception:
            logging.getLogger("ephew").exception("hotkey teardown failed")
        try:
            server.stop(timeout=3.0)
        except Exception:
            logging.getLogger("ephew").exception("server teardown failed")

    quit_requested = {"flag": False}

    def _on_signal(_signum: int, _frame: object) -> None:
        quit_requested["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    tray = TrayApp(state, on_quit=shutdown, verbose=args.verbose, activity=activity)

    def _check_quit(_timer: object) -> None:
        if quit_requested["flag"]:
            rumps.quit_application()

    rumps.Timer(_check_quit, 0.5).start()

    try:
        tray.run()
    finally:
        shutdown()

    return 0


def _configure_logging(verbose: bool = False) -> None:
    from ephew.security import CredentialRedactionFilter

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(CredentialRedactionFilter())

    # Root stays at WARNING so third-party libs (httpx, httpcore, uvicorn, asyncio,
    # anyio, etc.) don't spew their own DEBUG/INFO into our stderr. Our own
    # `ephew.*` namespace gets DEBUG (verbose) or INFO (default) explicitly.
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.addHandler(handler)

    logging.getLogger("ephew").setLevel(logging.DEBUG if verbose else logging.INFO)

    # Defense in depth — pin the known noisy ones at WARNING regardless.
    for noisy in ("httpx", "httpcore", "uvicorn", "asyncio", "anyio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _print_banner(url: str, hotkey_installed: bool) -> None:
    lines = [
        f"ephew {__version__} running on {url}",
        "point your Anthropic client at this proxy:",
        f"  export ANTHROPIC_BASE_URL={url}",
        "  (or run `ephew setup --append-rc` to persist this in your shell rc)",
    ]
    if hotkey_installed:
        lines.append("hotkey: ⇧⌘E to cycle modes")
    else:
        lines.append(
            "hotkey unavailable (conflict with another app); use the menu-bar icon to change modes"
        )
    lines.append("Ctrl-C or tray → Quit to stop.")
    print("\n".join(lines), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
