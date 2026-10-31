"""Opt-in, staging-only Basic-Auth gateway for isolated full BIG PAW app tests.

Never used by production Docker CMD. The Railway staging service explicitly
starts this module, with its own secret environment variables. No credentials
are bundled into the Git repository. Protect every route except /healthz.
"""
from __future__ import annotations

import base64
from contextlib import closing
import hmac
import http.client
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HOP = {
    "connection", "proxy-connection", "keep-alive", "te", "trailer",
    "transfer-encoding", "upgrade", "proxy-authorization", "proxy-authenticate",
    "authorization", "host", "x-forwarded-proto", "x-forwarded-host",
}
_MAX_BODY = 32 * 1024 * 1024


def make_handler(*, user, password, upstream_port):
    if (not isinstance(user, str) or not 4 <= len(user) <= 60
            or not isinstance(password, str) or len(password) < 24
            or not isinstance(upstream_port, int)
            or not 1 <= upstream_port <= 65535):
        raise ValueError("Secure staging credentials and upstream port required")
    expected = ("Basic " + base64.b64encode(
        (user + ":" + password).encode("utf-8")).decode("ascii")).encode()

    class StagingGate(BaseHTTPRequestHandler):
        server_version = "BIGPAW-Staging-Gateway"
        sys_version = ""

        def log_message(self, format, *args):
            # No URLs, cookies, credentials or customer data in proxy logs.
            return

        def _send(self, code, body=b""):
            self.send_response(code)
            self.send_header("Cache-Control", "no-store")
            if code == 401:
                self.send_header("WWW-Authenticate",
                                 'Basic realm="BIG PAW Staging", charset="UTF-8"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD" and body:
                self.wfile.write(body)

        def _authenticated(self):
            raw = self.headers.get_all("Authorization", [])
            if len(raw) != 1 or not isinstance(raw[0], str):
                return False
            return hmac.compare_digest(raw[0].encode("utf-8"), expected)

        def _health(self):
            try:
                with closing(http.client.HTTPConnection(
                    "127.0.0.1", upstream_port, timeout=3
                )) as conn:
                    conn.request("GET", "/api/health")
                    res = conn.getresponse()
                    healthy = res.status == 200
                    res.read(8192)
                self._send(200 if healthy else 503,
                           b"staging-ready" if healthy else b"unavailable")
            except (OSError, http.client.HTTPException):
                self._send(503, b"unavailable")

        def _handle(self):
            if self.path == "/healthz" and self.command == "GET":
                return self._health()
            if not self._authenticated():
                return self._send(401, b"Authentication required")
            # No streaming/chunked request parsing: reject rather than
            # permitting HTTP request smuggling or unbounded body buffering.
            if self.headers.get("Transfer-Encoding"):
                return self._send(400, b"Unsupported request")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) > 1:
                return self._send(400, b"Invalid request")
            try:
                size = int(lengths[0]) if lengths else 0
            except (ValueError, TypeError):
                return self._send(400, b"Invalid request")
            if not 0 <= size <= _MAX_BODY:
                return self._send(413, b"Request too large")
            body = self.rfile.read(size) if size else None
            if size and len(body) != size:
                return self._send(400, b"Invalid request")
            headers = {
                k: v for k, v in self.headers.items()
                if k.lower() not in _HOP and k.lower() != "content-length"
            }
            headers["Host"] = self.headers.get("Host", "")
            headers["X-Forwarded-Proto"] = "https"
            headers["Connection"] = "close"
            if body is not None:
                headers["Content-Length"] = str(len(body))
            try:
                with closing(http.client.HTTPConnection(
                    "127.0.0.1", upstream_port, timeout=40
                )) as conn:
                    conn.request(self.command, self.path, body=body,
                                 headers=headers)
                    upstream = conn.getresponse()
                    data = upstream.read(_MAX_BODY + 1)
                    if len(data) > _MAX_BODY:
                        return self._send(502, b"Upstream response too large")
                    self.send_response(upstream.status)
                    for key, value in upstream.getheaders():
                        if key.lower() in _HOP or key.lower() in (
                            "content-length", "server", "date"):
                            continue
                        self.send_header(key, value)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(data)
            except (OSError, http.client.HTTPException):
                self._send(502, b"Staging upstream unavailable")

        do_GET = _handle
        do_HEAD = _handle
        do_POST = _handle
        do_PUT = _handle
        do_PATCH = _handle
        do_DELETE = _handle
        do_OPTIONS = _handle

    return StagingGate


def main():
    if os.environ.get("BIGPAW_ENV") != "staging":
        raise SystemExit("Staging gateway cannot run outside staging")
    user = os.environ.get("BIGPAW_STAGING_BASIC_USER", "")
    password = os.environ.get("BIGPAW_STAGING_BASIC_PASSWORD", "")
    port = int(os.environ.get("PORT", "8080"))
    backend_port = 8081 if port != 8081 else 8082
    handler = make_handler(user=user, password=password,
                           upstream_port=backend_port)
    env = dict(os.environ)
    env["PORT"] = str(backend_port)
    child = subprocess.Popen([sys.executable, "backend/server.py"], env=env)
    try:
        with ThreadingHTTPServer(("0.0.0.0", port), handler) as web:
            web.serve_forever()
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


if __name__ == "__main__":
    main()
