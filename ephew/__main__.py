from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

import httpx

from ephew import __version__
from ephew.proxy import build_app
from ephew.security import CredentialRedactionFilter, install_redaction
from ephew.server import ProxyServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ephew",
        description="Local passthrough proxy for the Anthropic API (Pre-MVP).",
    )
    parser.parse_args(argv)

    install_redaction()
    _configure_logging()

    port = int(os.environ.get("EPHEW_PORT", "47821"))

    upstream_client = httpx.AsyncClient(
        base_url="https://api.anthropic.com",
        http2=False,
        timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=10.0),
    )
    app = build_app(upstream_client)
    server = ProxyServer(app, port=port)

    try:
        server.start()
    except Exception as exc:
        print(f"ephew: failed to start proxy: {exc}", file=sys.stderr)
        return 1

    _print_banner(server.url)

    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop(timeout=3.0)

    return 0


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(CredentialRedactionFilter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _print_banner(url: str) -> None:
    print(
        f"ephew {__version__} (Pre-MVP passthrough) running on {url}\n"
        f"point your Anthropic client at this proxy:\n"
        f"  export ANTHROPIC_BASE_URL={url}\n"
        f"Ctrl-C to stop.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    sys.exit(main())
