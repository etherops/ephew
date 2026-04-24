from __future__ import annotations

import json
import logging

import httpx
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, StreamingResponse

from ephew import transform
from ephew.modes import Mode
from ephew.state import CurrentMode

log = logging.getLogger("ephew.proxy")

_DROP_REQUEST_HEADERS = frozenset({"host", "content-length"})
_DROP_RESPONSE_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
})


def build_app(upstream_client: httpx.AsyncClient, state: CurrentMode) -> FastAPI:
    app = FastAPI()

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def proxy(path: str, request: Request):
        body = await request.body()
        mode = state.get()
        if request.method == "POST" and request.url.path == "/v1/messages" and mode.directive is not None:
            body = _transform_body(body, mode)
        return await _forward(request, upstream_client, body, mode)

    return app


def _transform_body(body: bytes, mode: Mode) -> bytes:
    try:
        body_dict = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body
    new_body = transform.apply(body_dict, mode)
    return json.dumps(new_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


async def _forward(request: Request, client: httpx.AsyncClient, body: bytes, mode: Mode):
    method = request.method
    path = request.url.path
    query = request.url.query
    target = path + (f"?{query}" if query else "")
    headers = _filter_request_headers(request.headers)

    upstream_request = client.build_request(method, target, headers=headers, content=body)
    try:
        upstream = await client.send(upstream_request, stream=True)
    except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
        log.warning("upstream unreachable: %s", type(exc).__name__)
        _log_validation(method, path, "NA", 0, mode)
        return JSONResponse(
            {"error": "upstream_unreachable", "detail": type(exc).__name__},
            status_code=502,
        )

    status = upstream.status_code
    response_headers = _filter_response_headers(upstream.headers)
    media_type = upstream.headers.get("content-type")

    async def body_iter():
        total = 0
        try:
            async for chunk in upstream.aiter_bytes():
                total += len(chunk)
                yield chunk
        finally:
            await upstream.aclose()
            _log_validation(method, path, status, total, mode)

    return StreamingResponse(
        content=body_iter(),
        status_code=status,
        headers=response_headers,
        media_type=media_type,
    )


def _log_validation(method: str, path: str, status, total: int, mode: Mode) -> None:
    if log.isEnabledFor(logging.DEBUG) and mode.directive is not None:
        log.info(
            "proxy method=%s path=%s upstream_status=%s bytes=%d mode=%s directive=%r",
            method, path, status, total, mode.name, mode.directive,
        )
    else:
        log.info(
            "proxy method=%s path=%s upstream_status=%s bytes=%d mode=%s",
            method, path, status, total, mode.name,
        )


def _filter_request_headers(incoming) -> dict[str, str]:
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP_REQUEST_HEADERS}


def _filter_response_headers(incoming) -> dict[str, str]:
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP_RESPONSE_HEADERS}
