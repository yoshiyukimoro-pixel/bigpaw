"""Offline staging gateway auth tests: no real Railway/Square connections."""
from __future__ import annotations
import base64
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(Path("app/backend").resolve()))
from staging_auth_gateway import make_handler


class Upstream(BaseHTTPRequestHandler):
    hits = []
    def log_message(self, *_): pass
    def do_GET(self):
        self.hits.append((self.path, self.headers.get("Authorization", ""),
                          self.headers.get("X-Forwarded-Proto")))
        if self.path == "/api/health":
            data = b'{"ok":true}'
        else:
            data = b"Private staging body"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_POST(self):
        self.do_GET()


class StagingGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        cls.gateway = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            user="bigpaw_staging", password="never-real-password-for-synthetic-tests",
            upstream_port=cls.upstream.server_port))
        cls.threads = [threading.Thread(target=s.serve_forever, daemon=True)
                       for s in (cls.upstream, cls.gateway)]
        for t in cls.threads: t.start()

    @classmethod
    def tearDownClass(cls):
        for s in (cls.gateway, cls.upstream):
            s.shutdown()
            s.server_close()
        for t in cls.threads: t.join(timeout=3)

    def setUp(self):
        Upstream.hits.clear()

    def call(self, path, headers=None, method="GET", body=None):
        with http.client.HTTPConnection("127.0.0.1",
                                       self.gateway.server_port, timeout=5) as c:
            c.request(method, path, body=body, headers=headers or {})
            response = c.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def auth(self):
        token = base64.b64encode(
            b"bigpaw_staging:never-real-password-for-synthetic-tests").decode()
        return {"Authorization": "Basic " + token, "Host": "shop-staging.invalid"}

    def test_missing_or_wrong_auth_never_reaches_app(self):
        for headers in ({}, {"Authorization": "Bearer token"}, 
                        {"Authorization": "Basic wrong"}):
            status, h, _ = self.call("/shop.html", headers=headers)
            self.assertEqual(status, 401)
            self.assertIn("WWW-Authenticate", h)
        self.assertEqual(Upstream.hits, [])

    def test_health_is_only_unprotected_path(self):
        status, _, body = self.call("/healthz")
        self.assertEqual((status, body), (200, b"staging-ready"))
        self.assertEqual(Upstream.hits[0][0], "/api/health")
        status, _, _ = self.call("/api/health")
        self.assertEqual(status, 401)

    def test_authenticated_get_and_post_sanitizes_authorization(self):
        status, _, body = self.call("/shop.html", headers=self.auth())
        self.assertEqual((status, body), (200, b"Private staging body"))
        self.assertEqual(Upstream.hits[-1],
                         ("/shop.html", "", "https"))
        status, _, _ = self.call("/api/shop/checkout", headers=self.auth(),
                                  method="POST", body=b"{}")
        self.assertEqual(status, 200)
        self.assertEqual(Upstream.hits[-1][1], "")

    def test_hostile_request_rejected_before_backend(self):
        auth = self.auth()
        for headers in (
            {**auth, "Transfer-Encoding": "chunked"},
            {**auth, "Content-Length": "999999999"},
        ):
            status, _, _ = self.call("/api/user", headers=headers)
            self.assertIn(status, (400, 413))
        self.assertEqual(Upstream.hits, [])

    def test_staging_secret_is_required(self):
        for password in ("", "too-short"):
            with self.assertRaises(ValueError):
                make_handler(user="shop", password=password, upstream_port=8081)


if __name__ == "__main__":
    unittest.main()
