from __future__ import annotations

import argparse
import logging
import os
import signal
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ephew",
        description="Local verbosity-toggle proxy for the Anthropic API (MVP).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="emit a DEBUG log line per transformed /v1/messages request showing mode + directive",
    )
    args = parser.parse_args(argv)

    # Import after parse_args so --help doesn't drag in macOS-only deps.
    import httpx
    import rumps

    from ephew.hotkey import HotkeyRegistration
    from ephew.modes import DEFAULT
    from ephew.proxy import build_app
    from ephew.security import CredentialRedactionFilter, install_redaction
    from ephew.server import ProxyServer
    from ephew.state import CurrentMode
    from ephew.tray import TrayApp

    install_redaction()
    _configure_logging(verbose=args.verbose)

    port = int(os.environ.get("EPHEW_PORT", "47821"))

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
    except Exception as exc:
        print(f"ephew: failed to start proxy: {exc}", file=sys.stderr)
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

    # Periodic Python callback lets queued signal handlers run while the AppKit
    # runloop is blocked in native code. On signal, trigger rumps.quit_application.
    def _check_quit(_timer):
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
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _print_banner(url: str, hotkey_installed: bool) -> None:
    from ephew import __version__

    lines = [
        f"ephew {__version__} (MVP) running on {url}",
        "point your Anthropic client at this proxy:",
        f"  export ANTHROPIC_BASE_URL={url}",
    ]
    if hotkey_installed:
        lines.append("hotkey: ⇧⌘E to cycle modes")
    else:
        lines.append("hotkey unavailable; use the menu-bar icon to change modes")
    lines.append("Ctrl-C or tray → Quit to stop.")
    print("\n".join(lines), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
