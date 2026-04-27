import socket

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ephew.server import PortInUseError, ProxyServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _trivial_app() -> Starlette:
    async def ping(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return Starlette(routes=[Route("/ping", ping, methods=["GET"])])


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


def test_port_in_use_raises_typed_error():
    port = _free_port()
    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    occupier.bind(("127.0.0.1", port))
    occupier.listen(1)
    try:
        server = ProxyServer(_trivial_app(), port=port)
        with pytest.raises(PortInUseError) as exc_info:
            server.start()
        assert str(port) in str(exc_info.value)
        assert "127.0.0.1" in str(exc_info.value)
    finally:
        occupier.close()
