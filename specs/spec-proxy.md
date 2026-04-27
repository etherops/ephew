# spec-proxy.md — HTTP proxy

**Phase:** Mixed — see [LAUNCH.md](./LAUNCH.md).

- **Pre-MVP:** passthrough only. Every path (including `/v1/messages`) is forwarded verbatim. Validation-log line emitted per request (method, path, upstream status, response byte count — no headers, no body).
- **MVP:** adds transform integration for `POST /v1/messages`. The `### POST /v1/messages` behavior section below is the **[MVP]** feature; in Pre-MVP that path uses the passthrough branch described in "All other paths."
- **Dot:** tightened upstream-failure error messages; hardened header handling for edge cases surfaced during MVP use.

## Purpose

The proxy is the wire-level half of Ephew. It impersonates `api.anthropic.com` on `127.0.0.1`, transforms outgoing `/v1/messages` requests by injecting the active mode's directive (see [spec-transform.md](./spec-transform.md)) into the last user message, and streams responses back to the client byte-for-byte. All other paths pass through untouched. The proxy itself is stateless; it reads `CurrentMode.get()` per request.

## Public surface

Module: `ephew/proxy.py`.

```python
def build_app(
    upstream_client: httpx.AsyncClient,
    state: CurrentMode,
    include_markers: bool = True,
    activity: ActivityNotifier | None = None,
) -> starlette.applications.Starlette
```

Returns a configured `Starlette` instance ready to hand to uvicorn (see [spec-server.md](./spec-server.md)). The app has one catch-all route whose handler chooses between transform and passthrough based on method and path. If an `ActivityNotifier` is supplied, the handler calls `activity.pulse()` once at the top of every request so the tray (or any other subscriber) can reflect the activity in real time — see [spec-activity.md](./spec-activity.md).

We deliberately use bare Starlette rather than FastAPI: FastAPI's added value (Pydantic-based request validation, OpenAPI auto-docs, dependency injection) is unused in this project, and FastAPI's transitive dependency on `pydantic_core` (Rust) makes Homebrew installs slow and complicates packaging. Starlette is pure Python and provides the routing primitive we need natively.

Invariants:
- `build_app` does no I/O and opens no network connections at construction time.
- The returned app honors client cancellation: if the client disconnects mid-stream, the upstream request is aborted.
- No module-level mutable state; everything travels through `state` and `upstream_client`.

## Behavior

### Endpoint match

A single catch-all route is registered via Starlette's `Route`:

```python
Starlette(routes=[
    Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
])
```

The handler signature is `async def proxy(request: Request) -> Response`. The catch-all path component is available as `request.path_params["path"]`, but in practice we use `request.url.path` since branching is on the *full* request path.

### `POST /v1/messages` **[MVP]**

In Pre-MVP this path is handled by the "All other paths" passthrough branch below. The transform sequence described here lands with MVP.

1. Read raw request body bytes.
2. Parse as JSON. If parsing fails, forward untransformed — preserves Anthropic's own error reporting for malformed bodies.
3. Read `state.get()` once, store as `mode`.
4. Call `new_body, effective_mode = transform.apply(body_dict, mode, include_markers=...)`. The transform layer may swap to a different mode if the user appended an override flag (`-c`, `-v`, `-t`, `-x`, or long forms) to the very end of their message; see [spec-transform.md](./spec-transform.md). Re-serialize to JSON bytes with `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` to match typical client encoding.
5. Build the upstream request (see "Headers" and "Upstream forwarding").
6. Stream the upstream response through to the client.

### All other paths

`/v1/models`, `/v1/messages/count_tokens`, legacy `/v1/complete`, `GET /`, and anything else: forward verbatim. No JSON parsing, no body modification. Still stream the response.

### Validation logging

Every request emits exactly one log line at INFO level. Pre-MVP shape:

```
proxy method=POST path=/v1/messages upstream_status=200 bytes=12345
```

MVP adds the **effective mode name** (always — i.e. post-override):

```
proxy method=POST path=/v1/messages upstream_status=200 bytes=12345 mode=concise
```

When the request was overridden by an in-prompt flag, an `override=` field is appended naming the exact flag the user typed (so the user can audit override hits in logs):

```
proxy method=POST path=/v1/messages upstream_status=200 bytes=12345 mode=verbose override=-v
```

When the CLI is launched with `--verbose` (see [spec-cli.md](./spec-cli.md)) **and** the effective mode has a non-`None` directive, the same line is extended with the directive (repr-quoted for unambiguous whitespace display):

```
proxy method=POST path=/v1/messages upstream_status=200 bytes=12345 mode=concise directive='Fewest words possible. Max one sentence.'
```

Fields: request method, request path (no query string), upstream HTTP status code, total response byte count forwarded to the client, effective mode name, optionally the override flag, and optionally the directive. No headers, no request body, no user message content, no client/upstream IPs. Still exactly one log line per request.

### Headers

Forward every incoming header to upstream with two exceptions:
- Drop `host` — httpx sets it from the URL.
- Drop `content-length` — httpx recomputes after any body change.

Never read the values of `x-api-key` or `authorization`. Never log them. Never copy them into variables that outlive the request function scope. See [spec-security.md](./spec-security.md).

### Upstream forwarding

Use a single module-level `httpx.AsyncClient` with:
- `base_url="https://api.anthropic.com"`
- `http2=False` — parity with most Anthropic clients; avoids HTTP/2 edge cases in streaming
- `timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=10.0)` — `read=None` because SSE streams can be arbitrarily long

Issue the call inside `async with client.stream(method, path, headers=..., content=body_bytes) as response:` and yield chunks from `response.aiter_raw()` as they arrive.

### Response streaming

Return a `starlette.responses.StreamingResponse`:
- `content` = async generator over `response.aiter_raw()`
- `status_code` = upstream status
- `headers` = upstream headers minus hop-by-hop (`connection`, `transfer-encoding`, `keep-alive`) and `content-length` (stream is chunked)
- `media_type` = upstream `content-type`

Do not JSON-decode SSE frames. Do not buffer. The generator must propagate `CancelledError` to abort the upstream request.

### Error handling

- Upstream 4xx / 5xx: forwarded verbatim with status and body preserved.
- `httpx.ConnectError` / `httpx.ReadError` / `httpx.ReadTimeout` before any bytes have been sent: return `502` with `{"error":"upstream_unreachable","detail":"<exception class name>"}`. Never include the exception message verbatim — it may carry URL or IP data.
- Exceptions after streaming has started: close the stream; Starlette handles the partial response correctly.
- Client disconnect: the `async for` loop raises; the upstream context manager cancels cleanly.

## Dependencies

Upstream (required):
- [spec-state.md](./spec-state.md) — reads `CurrentMode.get()` per request
- [spec-transform.md](./spec-transform.md) — calls `transform.apply`
- [spec-security.md](./spec-security.md) — logger redaction filter must be installed before proxy serves traffic

Downstream (consumers):
- [spec-server.md](./spec-server.md) — hosts the FastAPI app under uvicorn

Third-party:
- `starlette`, `httpx`

## Out of scope

- Request replay, caching, deduplication
- Rate limiting, request queuing
- Any logging of request/response bodies or credential headers
- HTTPS on the listening side (binds `127.0.0.1` only)
- Alternative upstreams (Bedrock, Vertex, any non-Anthropic endpoint)
- Modifying the system prompt (see [spec-transform.md](./spec-transform.md) for rationale)

## Verification

Unit tests (`tests/test_proxy.py`), using `httpx.MockTransport` as fake upstream:
- `POST /v1/messages` with realistic body; mode=`concise`. Upstream saw body with directive appended to the last user message.
- `POST /v1/messages` with mode=`none`. Upstream body equals input body byte-identical.
- `GET /v1/models`. No JSON parsing, body passed through.
- Upstream returns SSE stream of 3 chunks. Client sees the same 3 chunks in order, identical bytes.
- Upstream returns 401. Client gets 401 with identical body.
- Upstream refuses connection. Client gets 502 with expected JSON shape.
- `x-api-key` and `authorization` pass through byte-identical.
- `host` and `content-length` from client are stripped before upstream call.

Manual: covered by [spec-testing.md](./spec-testing.md).
