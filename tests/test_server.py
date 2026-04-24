import socket

import httpx
import pytest
from fastapi import FastAPI

from ephew.server import ProxyServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _trivial_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def test_start_serve_stop():
    port = _free_port()
    server = ProxyServer(_trivial_app(), port=port)
    server.start()
    try:
        r = httpx.get(f"{server.url}/ping", timeout=2.0)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
    finally:
        server.stop(timeout=2.0)


def test_stop_idempotent():
    server = ProxyServer(_trivial_app(), port=_free_port())
    server.start()
    server.stop()
    server.stop()


def test_daemon_thread():
    server = ProxyServer(_trivial_app(), port=_free_port())
    server.start()
    try:
        assert server._thread is not None
        assert server._thread.daemon is True
    finally:
        server.stop()


def test_url_property():
    server = ProxyServer(_trivial_app(), host="127.0.0.1", port=12345)
    assert server.url == "http://127.0.0.1:12345"


def test_port_in_use_raises():
    port = _free_port()
    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    occupier.bind(("127.0.0.1", port))
    occupier.listen(1)
    try:
        server = ProxyServer(_trivial_app(), port=port)
        with pytest.raises((RuntimeError, TimeoutError, OSError)):
            server.start()
    finally:
        occupier.close()
