# MoroTracker backend — setup

`server.py` is a tiny zero-dependency (stdlib-only) Python server that does two
things on one origin:

```
GET  /            -> the app (index.html)
GET  /state       -> the shared state JSON  (or {} if empty)
PUT  /state       -> overwrite the shared state JSON
```

State is a single JSON file; the frontend reads `/state` on load, merges it with
local completions (additive union — nothing is ever lost), and pushes back.

## Production (docker01)

The server runs in a Docker container behind the shared Caddy reverse proxy at
`https://moro.marksocks.com`, with the state file on the persistent `moro_data`
volume. Deploys are automatic on push to `main`. **See [`../DEPLOY.md`](../DEPLOY.md)**
for the full topology, the one-time volume creation + seeding, and how to migrate
existing streak data off the old GCP/Tailscale backend.

## Run locally

```sh
MORO_STATIC=../index.html MORO_DATA=./moro-state.json python3 server.py
# then open http://localhost:8787/
```

Config via environment variables:

| Var           | Default            | Meaning                          |
|---------------|--------------------|----------------------------------|
| `MORO_DATA`   | `~/moro-state.json`| path to the JSON state file      |
| `MORO_STATIC` | `./index.html`     | path to the app HTML to serve    |
| `MORO_ORIGIN` | `*`                | CORS origin (no-op when same-origin) |
| `MORO_PORT`   | `8787`             | port to listen on                |

## Notes

- **Merge is additive**: completions are unioned across devices, so a checkmark
  is never lost. The flip side — **un-checking won't reliably propagate** if
  another device still has it checked (the union re-adds it). For a habit tracker
  that's the safe trade-off.
- **Backup**: the whole dataset is one file. `cat moro-state.json` (or, in the
  container, read it off the `moro_data` volume — see `DEPLOY.md`) is a complete
  backup.

> **History:** this backend used to run on a free GCP e2-micro VM exposed only
> over a Tailscale tailnet (`tailscale serve`), with the app hosted separately on
> GitHub Pages and pointed at it via a `SYNC_ENDPOINT` const. It now serves the
> app itself and runs on docker01 behind Caddy; the Tailscale/GCP path is retired.
