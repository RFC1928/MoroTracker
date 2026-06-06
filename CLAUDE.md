# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoroTracker is a 12-week Moro Reflex Integration exercise tracking app ("Brain Sync Reflex Integration"). It is a **single-file, zero-dependency web application** — the entire app lives in `index.html`. There is no build step, no package manager, no bundler, and no test suite.

## Development

**To run locally:** Open `index.html` directly in any modern browser. No server needed.

**To deploy:** Push changes to `main` — the app is hosted on GitHub Pages at `https://rfc1928.github.io/MoroTracker/`.

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

State is loaded at startup and written back on every user action via a `saveState()` call.

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
