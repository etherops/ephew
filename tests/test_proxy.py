import logging

import httpx
from fastapi.testclient import TestClient

from ephew.proxy import build_app
from tests.conftest import make_mock_client

FAKE_KEY = "sk-ant-fake-DO-NOT-LOG-EVER"


def test_post_messages_passthrough_byte_identical():
    received: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["method"] = request.method
        received["path"] = request.url.path
        received["body"] = request.content
        received["auth"] = request.headers.get("x-api-key")
        return httpx.Response(200, content=b'{"id":"msg_1"}')

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    body = b'{"model":"claude-3","messages":[{"role":"user","content":"hello"}]}'
    r = tc.post(
        "/v1/messages",
        content=body,
        headers={"x-api-key": FAKE_KEY, "content-type": "application/json"},
    )
    assert r.status_code == 200
    assert r.content == b'{"id":"msg_1"}'
    assert received["method"] == "POST"
    assert received["path"] == "/v1/messages"
    # Pre-MVP: body must pass through byte-identical (no transform).
    assert received["body"] == body
    # Credential forwarded verbatim.
    assert received["auth"] == FAKE_KEY


def test_get_passthrough():
    def handler(request):
        return httpx.Response(200, content=b'{"data":[]}')

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    r = tc.get("/v1/models")
    assert r.status_code == 200
    assert r.content == b'{"data":[]}'


def test_sse_streaming_passthrough():
    chunks = [
        b"event: message_start\ndata: {}\n\n",
        b"event: content_block_delta\ndata: {}\n\n",
        b"event: message_stop\ndata: {}\n\n",
    ]

    def handler(request):
        return httpx.Response(
            200,
            content=b"".join(chunks),
            headers={"content-type": "text/event-stream"},
        )

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    with tc.stream("POST", "/v1/messages", content=b"{}") as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())
    assert body == b"".join(chunks)


def test_upstream_4xx_forwarded_verbatim():
    def handler(request):
        return httpx.Response(401, content=b'{"error":"unauthorized"}')

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    r = tc.post("/v1/messages", content=b"{}")
    assert r.status_code == 401
    assert r.content == b'{"error":"unauthorized"}'


def test_connect_error_returns_502():
    def handler(request):
        raise httpx.ConnectError("fail")

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    r = tc.post("/v1/messages", content=b"{}")
    assert r.status_code == 502
    assert "upstream_unreachable" in r.text


def test_drops_host_and_content_length_from_request():
    received: dict = {}

    def handler(request):
        received["host"] = request.headers.get("host")
        received["content_length"] = request.headers.get("content-length")
        return httpx.Response(200, content=b"{}")

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    tc.post(
        "/v1/messages",
        content=b"{}",
        headers={"content-type": "application/json"},
    )
    # httpx rebuilds these from the target URL and body.
    assert received["host"] == "api.anthropic.com"
    # content-length should reflect the re-serialized body length ("{}" == 2 bytes).
    assert received["content_length"] == "2"


def test_validation_log_line_emitted(caplog):
    def handler(request):
        return httpx.Response(200, content=b"hello", headers={"content-type": "text/plain"})

    client = make_mock_client(handler)
    tc = TestClient(build_app(client))
    with caplog.at_level(logging.INFO, logger="ephew.proxy"):
        r = tc.post("/v1/messages", content=b"{}")
    assert r.status_code == 200
    messages = [rec.getMessage() for rec in caplog.records]
    assert any(
        "method=POST" in m and "path=/v1/messages" in m and "upstream_status=200" in m
        for m in messages
    ), f"no validation log line found; got: {messages}"
