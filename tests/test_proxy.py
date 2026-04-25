import json
import logging

import httpx
from fastapi.testclient import TestClient

from ephew.modes import DEFAULT, find_by_name
from ephew.proxy import build_app
from ephew.state import CurrentMode
from tests.conftest import make_mock_client

FAKE_KEY = "sk-ant-fake-DO-NOT-LOG-EVER"


def _make_client_and_state(handler, mode=None):
    client = make_mock_client(handler)
    state = CurrentMode(initial=mode or DEFAULT)
    return client, state


def test_post_messages_passthrough_when_normal():
    received: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["body"] = request.content
        received["auth"] = request.headers.get("x-api-key")
        return httpx.Response(200, content=b'{"id":"msg_1"}')

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    body = b'{"model":"claude-3","messages":[{"role":"user","content":"hello"}]}'
    r = tc.post(
        "/v1/messages",
        content=body,
        headers={"x-api-key": FAKE_KEY, "content-type": "application/json"},
    )
    assert r.status_code == 200
    # Normal mode: body passes through unchanged.
    assert received["body"] == body
    assert received["auth"] == FAKE_KEY


def test_post_messages_transformed_under_concise_mode():
    received: dict = {}

    def handler(request):
        received["body"] = request.content
        return httpx.Response(200, content=b'{"id":"msg_1"}')

    concise = find_by_name("concise")
    client, state = _make_client_and_state(handler, mode=concise)
    tc = TestClient(build_app(client, state))
    original = {
        "model": "claude-3",
        "messages": [{"role": "user", "content": "hello"}],
    }
    r = tc.post("/v1/messages", content=json.dumps(original).encode())
    assert r.status_code == 200

    forwarded = json.loads(received["body"])
    assert forwarded["messages"][0]["content"].endswith(concise.directive)


def test_get_passthrough():
    def handler(_r):
        return httpx.Response(200, content=b'{"data":[]}')

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    r = tc.get("/v1/models")
    assert r.status_code == 200
    assert r.content == b'{"data":[]}'


def test_non_messages_post_not_transformed():
    received: dict = {}

    def handler(request):
        received["body"] = request.content
        return httpx.Response(200, content=b"{}")

    client, state = _make_client_and_state(handler, mode=find_by_name("concise"))
    tc = TestClient(build_app(client, state))
    body = b'{"messages":[{"role":"user","content":"hello"}]}'
    # Different path — not transformed even in concise mode.
    tc.post("/v1/messages/count_tokens", content=body)
    assert received["body"] == body


def test_sse_streaming_passthrough():
    chunks = [
        b"event: message_start\ndata: {}\n\n",
        b"event: content_block_delta\ndata: {}\n\n",
        b"event: message_stop\ndata: {}\n\n",
    ]

    def handler(_r):
        return httpx.Response(
            200,
            content=b"".join(chunks),
            headers={"content-type": "text/event-stream"},
        )

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    with tc.stream("POST", "/v1/messages", content=b"{}") as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())
    assert body == b"".join(chunks)


def test_upstream_4xx_forwarded_verbatim():
    def handler(_r):
        return httpx.Response(401, content=b'{"error":"unauthorized"}')

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    r = tc.post("/v1/messages", content=b"{}")
    assert r.status_code == 401
    assert r.content == b'{"error":"unauthorized"}'


def test_connect_error_returns_502():
    def handler(_r):
        raise httpx.ConnectError("fail")

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    r = tc.post("/v1/messages", content=b"{}")
    assert r.status_code == 502
    assert "upstream_unreachable" in r.text


def test_drops_host_and_content_length_from_request():
    received: dict = {}

    def handler(request):
        received["host"] = request.headers.get("host")
        received["content_length"] = request.headers.get("content-length")
        return httpx.Response(200, content=b"{}")

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    tc.post("/v1/messages", content=b"{}", headers={"content-type": "application/json"})
    assert received["host"] == "api.anthropic.com"
    assert received["content_length"] == "2"


def test_validation_log_line_emitted(caplog):
    def handler(_r):
        return httpx.Response(200, content=b"hello", headers={"content-type": "text/plain"})

    client, state = _make_client_and_state(handler)
    tc = TestClient(build_app(client, state))
    with caplog.at_level(logging.INFO, logger="ephew.proxy"):
        r = tc.post("/v1/messages", content=b"{}")
    assert r.status_code == 200
    messages = [rec.getMessage() for rec in caplog.records]
    assert any(
        "method=POST" in m and "path=/v1/messages" in m and "upstream_status=200" in m
        for m in messages
    ), f"no validation log line found; got: {messages}"


def test_validation_log_includes_mode(caplog):
    def handler(_r):
        return httpx.Response(200, content=b"{}")

    concise = find_by_name("concise")
    client, state = _make_client_and_state(handler, mode=concise)
    tc = TestClient(build_app(client, state))
    body = b'{"messages":[{"role":"user","content":"hi"}]}'
    with caplog.at_level(logging.INFO, logger="ephew.proxy"):
        tc.post("/v1/messages", content=body)

    messages = [rec.getMessage() for rec in caplog.records]
    assert any(
        "method=POST" in m and "mode=concise" in m and "directive=" not in m for m in messages
    ), f"expected validation line with mode but no directive; got: {messages}"


def test_validation_log_includes_directive_at_debug_level(caplog):
    def handler(_r):
        return httpx.Response(200, content=b"{}")

    concise = find_by_name("concise")
    client, state = _make_client_and_state(handler, mode=concise)
    tc = TestClient(build_app(client, state))
    body = b'{"messages":[{"role":"user","content":"hi"}]}'
    with caplog.at_level(logging.DEBUG, logger="ephew.proxy"):
        tc.post("/v1/messages", content=body)

    messages = [rec.getMessage() for rec in caplog.records]
    assert any("mode=concise" in m and concise.directive in m for m in messages), (
        f"expected directive in validation line at DEBUG; got: {messages}"
    )


def test_normal_mode_validation_line_has_no_directive(caplog):
    def handler(_r):
        return httpx.Response(200, content=b"{}")

    client, state = _make_client_and_state(handler)  # normal mode
    tc = TestClient(build_app(client, state))
    with caplog.at_level(logging.DEBUG, logger="ephew.proxy"):
        tc.post("/v1/messages", content=b'{"messages":[{"role":"user","content":"hi"}]}')

    messages = [rec.getMessage() for rec in caplog.records]
    assert any("mode=normal" in m for m in messages)
    assert not any("directive=" in m for m in messages)


def test_malformed_json_body_forwarded_untransformed():
    received: dict = {}

    def handler(request):
        received["body"] = request.content
        return httpx.Response(200, content=b"{}")

    client, state = _make_client_and_state(handler, mode=find_by_name("concise"))
    tc = TestClient(build_app(client, state))
    body = b"not-valid-json{{{"
    tc.post("/v1/messages", content=body)
    # Defensive: malformed JSON passes through unchanged so Anthropic returns the real error.
    assert received["body"] == body
