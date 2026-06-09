#!/usr/bin/env python3
"""Tiny zero-dependency state store for MoroTracker.

Runs on a free GCP e2-micro VM behind `tailscale serve`, so it is reachable
ONLY from devices on your tailnet, over HTTPS, with no password.

Endpoints:
  GET  /state  -> current JSON blob (or {} if nothing stored yet)
  PUT  /state  -> overwrite the JSON blob

Config via environment variables:
  MORO_DATA    path to the JSON file        (default: ~/moro-state.json)
  MORO_ORIGIN  allowed browser origin       (default: https://rfc1928.github.io)
  MORO_PORT    localhost port to listen on  (default: 8787)
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_FILE = os.environ.get('MORO_DATA', os.path.expanduser('~/moro-state.json'))
ALLOW_ORIGIN = os.environ.get('MORO_ORIGIN', 'https://rfc1928.github.io')
PORT = int(os.environ.get('MORO_PORT', '8787'))


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', ALLOW_ORIGIN)
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _empty(self, code):
        self.send_response(code)
        self._cors()
        self.end_headers()

    def do_OPTIONS(self):
        self._empty(204)

    def do_GET(self):
        if self.path != '/state':
            return self._empty(404)
        try:
            with open(DATA_FILE, 'rb') as f:
                body = f.read()
        except FileNotFoundError:
            body = b'{}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        if self.path != '/state':
            return self._empty(404)
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)  # validate it is JSON before saving
        except Exception:
            return self._empty(400)
        tmp = DATA_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f)
        os.replace(tmp, DATA_FILE)  # atomic replace
        self._empty(204)

    def log_message(self, *args):
        pass  # quiet


if __name__ == '__main__':
    print(f'MoroTracker store on 127.0.0.1:{PORT}, data -> {DATA_FILE}', file=sys.stderr)
    # Bind to localhost only; Tailscale Serve handles TLS + tailnet exposure.
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
