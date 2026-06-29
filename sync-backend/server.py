#!/usr/bin/env python3
"""Tiny zero-dependency app server + state store for MoroTracker.

Self-hosted in a Docker container on docker01, fronted by the shared Caddy
reverse proxy (Caddy terminates TLS and proxies to `moro:8787`). One process
serves both the static single-page app and its JSON state, so the browser talks
to a single same-origin endpoint — no CORS, no separate API host.

Endpoints:
  GET  /            -> the app (static index.html)
  GET  /index.html  -> same
  GET  /state       -> current JSON blob (or {} if nothing stored yet)
  PUT  /state       -> overwrite the JSON blob

Config via environment variables:
  MORO_DATA    path to the JSON state file   (default: ~/moro-state.json)
  MORO_STATIC  path to index.html to serve   (default: ./index.html)
  MORO_ORIGIN  allowed browser origin        (default: * — same-origin in prod)
  MORO_PORT    port to listen on             (default: 8787)
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_FILE = os.environ.get('MORO_DATA', os.path.expanduser('~/moro-state.json'))
STATIC_FILE = os.environ.get(
    'MORO_STATIC', os.path.join(os.path.dirname(__file__), 'index.html'))
ALLOW_ORIGIN = os.environ.get('MORO_ORIGIN', '*')
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

    def _serve_static(self):
        try:
            with open(STATIC_FILE, 'rb') as f:
                body = f.read()
        except FileNotFoundError:
            return self._empty(404)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            return self._serve_static()
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
    print(f'MoroTracker on 0.0.0.0:{PORT}, data -> {DATA_FILE}, '
          f'app -> {STATIC_FILE}', file=sys.stderr)
    # Bind to all interfaces inside the container; only the Caddy reverse proxy
    # on the shared `proxy` network can reach it (no published host port).
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
