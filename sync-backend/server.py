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
  GET  /nag         -> 200 while today's exercises are done (or it's early);
                       503 once the evening cutoff passes with today still
                       incomplete. Built for an Uptime Kuma HTTP monitor: the
                       monitor sees "down" and fires the don't-forget alert.

Config via environment variables:
  MORO_DATA    path to the JSON state file   (default: ~/moro-state.json)
  MORO_STATIC  path to index.html to serve   (default: ./index.html)
  MORO_ORIGIN  allowed browser origin        (default: * — same-origin in prod)
  MORO_PORT    port to listen on             (default: 8787)
  MORO_TZ      IANA timezone for /nag's idea of "today" and the cutoff clock
               (default: America/New_York)
  MORO_NAG_CUTOFF  local HH:MM after which an incomplete day turns /nag into
               503 (default: 22:00)
"""
import json
import os
import sys
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

DATA_FILE = os.environ.get('MORO_DATA', os.path.expanduser('~/moro-state.json'))
STATIC_FILE = os.environ.get(
    'MORO_STATIC', os.path.join(os.path.dirname(__file__), 'index.html'))
ALLOW_ORIGIN = os.environ.get('MORO_ORIGIN', '*')
PORT = int(os.environ.get('MORO_PORT', '8787'))
MAX_BODY = 1024 * 1024  # sane cap; real state is a few KB

NAG_TZ = os.environ.get('MORO_TZ', 'America/New_York')
NAG_CUTOFF = os.environ.get('MORO_NAG_CUTOFF', '22:00')

# Mirror of SCHEDULE in index.html — keep the two in sync if the program
# ever changes. /nag needs it server-side to judge whether *today* is done.
SCHEDULE = {
    1:  ["Prayer Pose"],
    2:  ["Prayer Pose"],
    3:  ["Prayer Pose", "Starfish"],
    4:  ["Prayer Pose", "Starfish"],
    5:  ["Starfish", "Duck and Pigeon Walk With Stick"],
    6:  ["Starfish", "Duck and Pigeon Walk With Stick"],
    7:  ["Starfish", "Duck and Pigeon Walk With Markers"],
    8:  ["Starfish", "Duck and Pigeon Walk With Markers"],
    9:  ["Duck and Pigeon Walk Without Markers"],
    10: ["Duck and Pigeon Walk Without Markers"],
    11: ["Duck and Pigeon Hops"],
    12: ["Duck and Pigeon Hops"],
}


def nag_status():
    """Judge today's exercises the same way isDayComplete() in index.html
    judges *today*: the current week's set must be fully covered (or the day
    forgiven). Returns (ok, detail-dict); ok is False only when the day is
    incomplete AND the local clock is past the cutoff."""
    now = datetime.now(ZoneInfo(NAG_TZ))
    today = now.strftime('%Y-%m-%d')
    try:
        with open(DATA_FILE) as f:
            state = json.load(f)
    except Exception:
        state = {}
    done = state.get('completedDays', {}).get(today, [])
    complete = today in state.get('forgivenDays', [])
    needed = []
    start = state.get('startDate')
    if start and not complete:
        days = (date.fromisoformat(today) - date.fromisoformat(start)).days
        if days >= 0:
            week = min(12, days // 7 + 1)
            needed = SCHEDULE.get(week, [])
            complete = all(ex in done for ex in needed)
    hh, mm = (int(p) for p in NAG_CUTOFF.split(':'))
    past_cutoff = (now.hour, now.minute) >= (hh, mm)
    return complete or not past_cutoff, {
        'ok': complete or not past_cutoff,
        'date': today,
        'complete': complete,
        'needed': needed,
        'done': done,
        'cutoff': NAG_CUTOFF,
        'pastCutoff': past_cutoff,
    }

# ThreadingHTTPServer handles requests concurrently, but all writers share the
# same .tmp file — serialize them so concurrent PUTs can't corrupt the store.
WRITE_LOCK = threading.Lock()


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
        if self.path == '/nag':
            ok, detail = nag_status()
            body = json.dumps(detail).encode()
            self.send_response(200 if ok else 503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self._cors()
            self.end_headers()
            return self.wfile.write(body)
        if self.path != '/state':
            return self._empty(404)
        try:
            with open(DATA_FILE, 'rb') as f:
                body = f.read()
        except FileNotFoundError:
            body = b'{}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        if self.path != '/state':
            return self._empty(404)
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return self._empty(400)
        if length <= 0:
            return self._empty(400)
        if length > MAX_BODY:
            return self._empty(413)
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)  # validate it is JSON before saving
        except Exception:
            return self._empty(400)
        tmp = DATA_FILE + '.tmp'
        with WRITE_LOCK:
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
