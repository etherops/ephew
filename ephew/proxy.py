from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Mapping

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from ephew import transform
from ephew.activity import ActivityNotifier
from ephew.modes import Mode
from ephew.state import CurrentMode

log = logging.getLogger("ephew.proxy")

_DROP_REQUEST_HEADERS = frozenset({"host", "content-length"})
_DROP_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "content-encoding",
    }
)

_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def build_app(
    upstream_client: httpx.AsyncClient,
    state: CurrentMode,
    include_markers: bool = True,
    activity: ActivityNotifier | None = None,
) -> Starlette:
    async def proxy(request: Request) -> Response:
        if activity is not None:
            activity.pulse()
        body = await request.body()
        mode = state.get()
        effective = mode
        override: str | None = None
        if request.method == "POST" and request.url.path == "/v1/messages":
            body, effective, override = _transform_body(body, mode, include_markers)
        return await _forward(request, upstream_client, body, effective, override)

    return Starlette(routes=[Route("/{path:path}", proxy, methods=_METHODS)])


def _transform_body(
    body: bytes, mode: Mode, include_markers: bool
) -> tuple[bytes, Mode, str | None]:
    try:
        body_dict = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body, mode, None
    new_body, effective, override = transform.apply(
        body_dict, mode, include_markers=include_markers
    )
    if effective is mode and override is None and effective.directive is None:
        # Pure passthrough — keep original bytes verbatim.
        return body, mode, None
    encoded = json.dumps(new_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encoded, effective, override


async def _forward(
    request: Request,
    client: httpx.AsyncClient,
    body: bytes,
    mode: Mode,
    override: str | None,
) -> Response:
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
        _log_validation(method, path, "NA", 0, mode, override)
        return JSONResponse(
            {"error": "upstream_unreachable", "detail": type(exc).__name__},
            status_code=502,
        )

    status = upstream.status_code
    response_headers = _filter_response_headers(upstream.headers)
    media_type = upstream.headers.get("content-type")

    async def body_iter() -> AsyncIterator[bytes]:
        total = 0
        try:
            async for chunk in upstream.aiter_bytes():
                total += len(chunk)
                yield chunk
        finally:
            await upstream.aclose()
            _log_validation(method, path, status, total, mode, override)

    return StreamingResponse(
        content=body_iter(),
        status_code=status,
        headers=response_headers,
        media_type=media_type,
    )


def _log_validation(
    method: str,
    path: str,
    status: object,
    total: int,
    mode: Mode,
    override: str | None,
) -> None:
    parts = [
        f"proxy method={method}",
        f"path={path}",
        f"upstream_status={status}",
        f"bytes={total}",
        f"mode={mode.name}",
    ]
    if override is not None:
        parts.append(f"override={override}")
    if log.isEnabledFor(logging.DEBUG) and mode.directive is not None:
        parts.append(f"directive={mode.directive!r}")
    log.info(" ".join(parts))


def _filter_request_headers(incoming: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP_REQUEST_HEADERS}


def _filter_response_headers(incoming: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in incoming.items() if k.lower() not in _DROP_RESPONSE_HEADERS}
