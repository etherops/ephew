# spec-server.md — uvicorn lifecycle

**Phase:** Pre-MVP — the full start/stop lifecycle ships in Pre-MVP. MVP adds the `tray.on_quit` hookup. Dot release refines the error surface on port-in-use. See [LAUNCH.md](./LAUNCH.md).

## Purpose

Run the FastAPI proxy (see [spec-proxy.md](./spec-proxy.md)) on a background daemon thread so the main thread is free for the AppKit runloop. Provide a clean startup handshake (main thread waits until the server has bound the port) and a clean shutdown (main thread signals stop and joins with a timeout).

## Public surface

Module: `ephew/server.py`.

```python
class ProxyServer:
    def __init__(self, app: fastapi.FastAPI, host: str = "127.0.0.1", port: int = 47821): ...
    def start(self) -> None:
        """Spawn the uvicorn thread; block until the server has bound the port or raised."""
    def stop(self, timeout: float = 3.0) -> None:
        """Signal shutdown; join the thread within timeout seconds."""
    @property
    def url(self) -> str: ...  # e.g. "http://127.0.0.1:47821"
```

Invariants:
- Binds to `127.0.0.1` only. Never accepts connections from non-loopback interfaces.
- `start()` does not return until either `server.started` is set (success) or the thread has exited with an exception (failure; re-raised on the calling thread).
- `stop()` is idempotent.
- The server thread is `daemon=True` so process exit isn't blocked even if the join timeout fires.

## Behavior

### Programmatic uvicorn

Rather than shelling out to `uvicorn` CLI, construct the server in-process:

```python
config = uvicorn.Config(
    app=self._app,
    host=self._host,
    port=self._port,
    log_level="warning",      # quiet by default; access logs disabled
    access_log=False,
    loop="asyncio",
    lifespan="off",           # we don't use startup/shutdown events
    http="h11",
)
self._server = uvicorn.Server(config)
```

### Startup handshake

Before spawning the uvicorn thread, `start()` pre-checks that the port can be bound and raises a typed exception on the common failure — port-in-use — so the caller (CLI, see [spec-cli.md](./spec-cli.md)) can format a clear one-line error without parsing stack traces:

```python
class PortInUseError(RuntimeError): ...

def start(self) -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((self._host, self._port))
    except OSError as exc:
        raise PortInUseError(
            f"port {self._port} is already in use on {self._host}"
        ) from exc
    finally:
        probe.close()

    self._thread = threading.Thread(target=self._run, daemon=True, name="ephew-proxy")
    self._thread.start()
    deadline = time.monotonic() + 5.0
    while not self._server.started:
        if not self._thread.is_alive():
            raise RuntimeError("proxy thread exited before binding; see logs")
        if time.monotonic() > deadline:
            raise TimeoutError("proxy failed to bind within 5s")
        time.sleep(0.02)

def _run(self) -> None:
    asyncio.run(self._server.serve())
```

The probe-then-bind sequence is racy in the strict sense (another process could grab the port between probe close and uvicorn bind), but it is strictly better than the previous silent-`SystemExit`-in-thread behavior: the user gets a clear, typed, actionable message in the common case, and the rare race falls back to the existing "thread exited before binding" path.

### Shutdown

```python
def stop(self, timeout: float = 3.0) -> None:
    if self._server is None:
        return
    self._server.should_exit = True
    self._thread.join(timeout=timeout)
    if self._thread.is_alive():
        log.warning("proxy did not stop within %.1fs; leaving as daemon", timeout)
```

`should_exit = True` tells uvicorn's main loop to break; any in-flight streaming response is cancelled. The `daemon=True` flag ensures a hung thread never prevents Python from exiting.

### Port

Default `47821`. Configurable via the `EPHEW_PORT` environment variable, which the CLI (see [spec-cli.md](./spec-cli.md)) reads and passes in at construction. The server itself only cares about its constructor arg.

### Logging

Uvicorn's loggers (`uvicorn`, `uvicorn.error`, `uvicorn.access`) are reconfigured on startup to route through the redacted Ephew root logger (see [spec-security.md](./spec-security.md)). Access logging is off.

## Dependencies

Upstream:
- [spec-proxy.md](./spec-proxy.md) — provides the `FastAPI` app
- [spec-security.md](./spec-security.md) — redaction filter must be installed before the server starts

Downstream:
- [spec-cli.md](./spec-cli.md) — constructs `ProxyServer`, calls `start()` then enters AppKit loop, calls `stop()` on quit

Third-party: `uvicorn`, `fastapi`.

## Out of scope

- HTTPS listener (binds `127.0.0.1` only)
- Multiple workers (single-process, single-event-loop)
- IPv6 binding
- Hot reload on code change
- Exposing the server to non-loopback interfaces
- Non-uvicorn runners (`hypercorn`, `granian`, etc.)

## Verification

Unit tests (`tests/test_server.py`):
- `ProxyServer` with a trivial FastAPI app (single `GET /` returning 200) starts, serves one request via `httpx.Client(base_url=server.url)`, and stops cleanly within 1 s.
- `start()` raises `TimeoutError` or `RuntimeError` if the port is already in use (simulate by binding a socket to the same port first).
- `stop()` is idempotent (calling twice does not raise).
- The server thread is `daemon=True` (assert `thread.daemon`).
- The server binds only to `127.0.0.1` (assert a connect to `0.0.0.0:47821` from a non-loopback alias would be refused — approximate by asserting the uvicorn `Config.host`).

Manual: covered by [spec-testing.md](./spec-testing.md).
