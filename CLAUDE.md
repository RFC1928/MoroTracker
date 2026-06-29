# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoroTracker is a 12-week Moro Reflex Integration exercise tracking app ("Brain Sync Reflex Integration"). It is a **single-file, zero-dependency web application** — the entire app lives in `index.html`. There is no build step, no package manager, no bundler, and no test suite.

## Development

**To run locally:** Open `index.html` directly in any modern browser. No server needed.

**To deploy:** Push changes to `main` on the Forgejo remote
(`ssh://git@docker01:222/mark/moro.git`). A Forgejo Actions workflow
(`.forgejo/workflows/deploy.yml`) runs on the self-hosted `docker01` runner and
`docker compose -p moro up -d --build`s the stack behind the shared Caddy reverse
proxy at `https://moro.marksocks.com`. See `DEPLOY.md`.

There are no lint, build, or test commands.

## Architecture

Everything lives in `index.html` (~1,000 lines), structured in three blocks:

1. **`<style>`** — All CSS, including CSS custom properties, keyframe animations, and mobile-first layout (target viewport: 480px max-width).
2. **`<body>`** — Static HTML scaffolding for cards, modals, and the header. JavaScript writes dynamic content into these containers.
3. **`<script>`** — All application logic in vanilla JS with no modules or classes.

### State & Persistence

All state is stored in `localStorage` under the key `'moroTracker'` as a JSON string:

```js
{
  startDate: 'YYYY-MM-DD',         // program start date
  completedDays: {                  // exercises done per day
    'YYYY-MM-DD': ['ExerciseName', ...]
  },
  forgivenDays: ['YYYY-MM-DD'],    // days pardoned by forgiveness tokens
  forgivenUsed: boolean            // whether a token was ever used
}
```

State is loaded at startup and written back on every user action via a `save()` call.

### Shared sync (`sync-backend/`)

localStorage is the instant local cache and offline fallback; the **shared**
source of truth is a single JSON file (`moro-state.json`) served by a tiny
zero-dependency Python server (`sync-backend/server.py`). That same server also
serves `index.html`, so the app and its `/state` API are **same-origin** — the
frontend just fetches the relative path `STATE_PATH = '/state'` (no
`SYNC_ENDPOINT` host, no CORS). `save()` pushes to `/state` (debounced via
`pushRemote`); `syncFromRemote()` pulls on load and does an **additive union
merge** (`mergeState()`) so completions are never lost across devices. In
production the server runs in a Docker container on docker01 behind Caddy, with
`moro-state.json` on the persistent `moro_data` volume (see `DEPLOY.md`). The app
still works fully offline from localStorage when `/state` is unreachable.

### Exercise Schedule

The 12-week program is defined in a `SCHEDULE` object mapping week numbers (1–12) to arrays of exercise names. The current week is derived from:

```js
Math.floor(daysSinceStart / 7) + 1  // capped at 12
```

Exercises link out to `brain-sync.net` for instructions.

### Streak & Forgiveness Logic

- **Streak** counts consecutive days (backwards from yesterday) where each day is either fully complete or forgiven.
- **Forgiveness tokens** are earned at every 7-day streak boundary, banked up to a max of 2. Using one pardons the most recent incomplete/unforgiven day within the past 7 days.
- **Milestones** fire at hardcoded day counts (7, 10, 14, 20, 21, 28, 30, 40, 50, 60, 84) and at every multiple of 7 or 10 beyond that. Day 84 is graduation.

### Visual Effects

Particle animations (confetti, burst, magic burst) are rendered on a dynamically created `<canvas>` element. Each effect spawns particles with velocity/gravity and self-removes the canvas when the animation completes.

## Key Conventions

- **Dates** are always handled as local time (no UTC conversions) using `'YYYY-MM-DD'` string keys. The timezone-fix commit (`3c5410d`) established this — do not introduce `toISOString()` or UTC-based date math.
- **DOM updates** are done by re-rendering full sections (calling render functions that set `innerHTML`) rather than patching individual elements.
- **No external JS dependencies.** Do not introduce libraries or CDN script tags.
- **CSS variables** define the color palette — use them rather than hardcoded hex values when adding new styles:
  - `--primary: #4f6ef7`, `--success: #22c55e`, `--warning: #f59e0b`, `--danger: #ef4444`, `--forgive: #a855f7`
