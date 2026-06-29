# Deploying MoroTracker to docker01

MoroTracker runs as its own container on docker01, behind the shared Caddy
reverse proxy, at **`https://moro.marksocks.com`**. One zero-dependency Python
process (`sync-backend/server.py`) serves both the app (`index.html`) and the
shared state API (`/state`) on the same origin — so the browser needs no CORS and
no separate API host. The whole dataset is a single JSON file
(`moro-state.json`) on a persistent volume; every device reads it on load and
merges its completions back in (additive union — checkmarks are never lost).

| Hostname              | Upstream     | Stack / repo |
|-----------------------|--------------|--------------|
| `moro.marksocks.com`  | `moro:8787`  | this repo    |

Pushes to `main` auto-deploy via a Forgejo Actions workflow
(`.forgejo/workflows/deploy.yml`) on the self-hosted `docker01` runner — the same
runner caddy + fcc use.

## The shared `proxy` network

moro attaches to the external `proxy` network owned by the caddy stack, so Caddy
reaches it at `reverse_proxy moro:8787`. Created once on docker01
(`docker network create proxy`); the deploy workflow recreates it if missing, so
a clean host self-heals.

## The state volume (read before first deploy)

The single `moro-state.json` lives in an **external** Docker volume named
`moro_data`, mounted at `/app/data`. It is declared `external: true` in compose,
so Compose refuses to start if it's missing — a deploy can therefore never
silently create an empty store and wipe the shared streak data.

Create it once, and **seed it with the captured streak before the first real
use** (see "Migrating the streak" below):

```sh
docker volume create moro_data

# seed from the JSON pulled off the old GCP/Tailscale backend (or phone export):
docker run --rm -v moro_data:/data -v "$PWD":/src alpine \
  cp /src/moro-state.json /data/moro-state.json
```

## The Forgejo Actions runner

Reuses the existing `docker01` runner (host docker socket mounted). Nothing new
to set up. Enable Actions on this repo: **Settings → Advanced → Enable Integrated
CI/CD (Actions)**.

## Deploy flow

1. Push to `main` (the Forgejo remote is `ssh://git@docker01:222/mark/moro.git`).
2. The `Deploy Moro` workflow runs on docker01: checkout → ensure the `proxy`
   network → `docker compose -p moro up -d --build --remove-orphans` → image
   prune.
3. Add the Caddy route: in the `caddy` repo's `Caddyfile`, add
   ```
   moro.marksocks.com {
       import tls_dns
       encode gzip
       reverse_proxy moro:8787
   }
   ```
   and push — Caddy redeploys and issues the cert via Cloudflare DNS-01.

Manual deploy / status from docker01:

```sh
docker compose -p moro up -d --build      # redeploy current checkout
docker compose -p moro ps                 # status
docker compose -p moro logs -f moro       # tail
```

## Migrating the streak off the old setup

The old app lived on GitHub Pages and synced (optionally, over Tailscale) to a
GCP VM. `moro.marksocks.com` is a **different origin** than `rfc1928.github.io`,
so a phone's `localStorage` does NOT carry over automatically — the new volume
must be seeded from the authoritative JSON.

1. Capture it from the old backend (any Tailscale device):
   ```sh
   curl -s https://socks-gcp.piranha-mine.ts.net/state | tee moro-state.json
   ```
   Confirm it has a `startDate` and `completedDays` covering the streak. If the
   phone never synced, export `localStorage['moroTracker']` from the phone
   browser instead and save it as `moro-state.json`.
2. Seed `moro_data` with it (commands above) **before** first use.
3. Deploy, open `https://moro.marksocks.com`, confirm the streak renders, then
   retire the GCP VM and the GitHub Pages deploy.

## Backup

The entire dataset is one file:

```sh
docker run --rm -v moro_data:/data alpine cat /data/moro-state.json > backup.json
```
