from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, StreamingResponse

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


def build_app(upstream_client: httpx.AsyncClient) -> FastAPI:
    app = FastAPI()

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def proxy(path: str, request: Request):
        return await _passthrough(request, upstream_client)

    return app


async def _passthrough(request: Request, client: httpx.AsyncClient):
    method = request.method
    path = request.url.path
    query = request.url.query
    target = path + (f"?{query}" if query else "")
    headers = _filter_request_headers(request.headers)
    body = await request.body()

    upstream_request = client.build_request(method, target, headers=headers, content=body)
    try:
        upstream = await client.send(upstream_request, stream=True)
    except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
        log.warning("upstream unreachable: %s", type(exc).__name__)
        log.info(
            "proxy method=%s path=%s upstream_status=%s bytes=%d",
            method, path, "NA", 0,
        )
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
            log.info(
                "proxy method=%s path=%s upstream_status=%s bytes=%d",
                method, path, status, total,
            )

    return StreamingResponse(
        content=body_iter(),
        status_code=status,
        headers=response_headers,
        media_type=media_type,
    )


def _filter_request_headers(incoming) -> dict[str, str]:
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP_REQUEST_HEADERS}


def _filter_response_headers(incoming) -> dict[str, str]:
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP_RESPONSE_HEADERS}
