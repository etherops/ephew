from __future__ import annotations

import asyncio
import logging
import threading
import time

import fastapi
import uvicorn

log = logging.getLogger("ephew.server")


class ProxyServer:
    def __init__(self, app: fastapi.FastAPI, host: str = "127.0.0.1", port: int = 47821):
        self._app = app
        self._host = host
        self._port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def start(self) -> None:
        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False,
            loop="asyncio",
            lifespan="off",
            http="h11",
        )
        self._server = uvicorn.Server(config)
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
        assert self._server is not None
        try:
            asyncio.run(self._server.serve())
        except SystemExit as exc:
            log.warning("proxy server thread exited early (SystemExit code=%s)", exc.code)
        except Exception:
            log.exception("proxy server thread crashed")

    def stop(self, timeout: float = 3.0) -> None:
        if self._server is None or self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            log.warning("proxy did not stop within %.1fs; leaving as daemon", timeout)
        self._server = None
        self._thread = None
