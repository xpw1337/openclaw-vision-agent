"""Tiny stdlib HTTP server exposing /healthz (liveness) and /readyz (readiness).

Runs in a daemon thread so it never blocks the asyncio worker loop. Readiness
is delegated to a callable (the worker passes its NATS connection check), so
`readinessProbe` fails fast when the bus connection drops.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def start_health_server(port: int, ready_check: Callable[[], bool]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib API name)
            if self.path == "/healthz":
                self._respond(200, b"ok")
            elif self.path == "/readyz":
                if ready_check():
                    self._respond(200, b"ready")
                else:
                    self._respond(503, b"not ready")
            elif self.path == "/metrics":
                self._respond(200, generate_latest(), CONTENT_TYPE_LATEST.encode())
            else:
                self._respond(404, b"not found")

        def _respond(self, status: int, body: bytes, content_type: bytes = b"text/plain") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type.decode())
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002 (stdlib API name)
            pass  # probes fire every few seconds; don't spam the worker logs

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
