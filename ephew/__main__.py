from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

from ephew import __version__


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Import after parse_args so --help / --version don't drag in macOS-only deps.
    import httpx
    import rumps

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

    upstream_client = httpx.AsyncClient(
        base_url="https://api.anthropic.com",
        http2=False,
        timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=10.0),
    )
    app = build_app(upstream_client, state)
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

    def _on_signal(signum, _frame) -> None:
        quit_requested["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    tray = TrayApp(state, on_quit=shutdown, verbose=args.verbose)

    def _check_quit(_timer):
        if quit_requested["flag"]:
            rumps.quit_application()

    rumps.Timer(_check_quit, 0.5).start()

    try:
        tray.run()
    finally:
        shutdown()

    return 0


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
        help=f"proxy port (overrides EPHEW_PORT env var; default 47821)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="extend per-request log with directive text; annotate tray menu items",
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
    return "\n".join(lines)


def _resolve_port(port_flag: int | None) -> int:
    if port_flag is not None:
        return port_flag
    env = os.environ.get("EPHEW_PORT")
    if env:
        return int(env)
    return 47821


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
    ]
    if hotkey_installed:
        lines.append("hotkey: ⇧⌘E to cycle modes")
    else:
        lines.append("hotkey unavailable (conflict with another app); use the menu-bar icon to change modes")
    lines.append("Ctrl-C or tray → Quit to stop.")
    print("\n".join(lines), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
