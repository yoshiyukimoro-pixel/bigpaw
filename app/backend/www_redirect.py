#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import os

TARGET='https://bigpaw.site'

class RedirectHandler(BaseHTTPRequestHandler):
    server_version='BigPawRedirect/1.0'
    def log_message(self, fmt, *args):
        print('[BIG PAW WWW REDIRECT]', fmt % args, flush=True)
    def _send(self, head_only=False):
        path=urlsplit(self.path).path
        if path=='/health':
            body=b'ok\n'
            self.send_response(200)
            self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            if not head_only:self.wfile.write(body)
            return
        location=TARGET+self.path
        self.send_response(308)
        self.send_header('Location',location)
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length','0')
        self.end_headers()
    def do_GET(self): self._send(False)
    def do_HEAD(self): self._send(True)
    def do_POST(self): self._send(False)

if __name__=='__main__':
    port=int(os.environ.get('PORT','8080'))
    print(f'BIG PAW www redirect running on port {port} -> {TARGET}', flush=True)
    ThreadingHTTPServer(('0.0.0.0',port),RedirectHandler).serve_forever()
