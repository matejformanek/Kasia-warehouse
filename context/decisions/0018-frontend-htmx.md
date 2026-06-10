# 0018 — Frontend: Django templates + htmx 2 + WhiteNoise

## Context

R2 in [`../tech-options.md`](../tech-options.md) calls for a
responsive web app, no native mobile, no SPA. The hard preferences in
[`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
("no SPA unless a screen demands client state — and none in the
design does") narrow the field to server-rendered HTML with light
JS where useful.

A few screens want interactivity:

- [`../screens/07-vydej.md`](../screens/07-vydej.md) — live PDF
  preview while the operator builds the výdej.
- [`../screens/03-prehled-pobocky.md`](../screens/03-prehled-pobocky.md)
  and [`../screens/04-katalog-produktu.md`](../screens/04-katalog-produktu.md)
  — search-as-you-type.
- [`../screens/08-seznam-dodaku.md`](../screens/08-seznam-dodaku.md)
  and [`../screens/10-historie-pohybu.md`](../screens/10-historie-pohybu.md)
  — filter updates.

htmx fits — partial HTML over the wire, server-rendered, no JS
build step, no Node dependency. **htmx 2** is the current major
release. **django-htmx 1.27** is the helper layer (middleware,
template tags, request-detection helpers). Static-asset serving in
production handled by **WhiteNoise** with compressed-manifest
storage — single-process gunicorn + WhiteNoise serves CSS/JS/fonts
directly, no separate static-file server.

## Options considered

- **Django templates + htmx 2 + django-htmx + WhiteNoise.**
  Server-rendered HTML; partials returned for htmx calls. No build
  step. Static files compressed at deploy time.
- **Django templates + Alpine.js.** Alpine is fine for tiny
  interactivity but doesn't help the "live PDF preview" case
  (that wants a partial swap from the server).
- **Django templates + custom vanilla JS.** Works for 2 screens;
  becomes a maintenance burden as the interactions grow.
- **Django + React (DRF + Vite).** Splits the codebase into API +
  frontend with CORS, build steps, two deploys, duplicate
  validation. Conference-talk shaped per
  [`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md).
- **Django + HTMX + Stimulus.** Stimulus adds value mostly for
  reusable behaviour controllers; the few interactive widgets in
  this app are server-driven, so Stimulus is unused weight.

## Choice

**Server-rendered Django templates + htmx 2 + django-htmx 1.27 +
WhiteNoise** (compressed-manifest static-files storage). No JS
bundler, no Node, no SPA. Pinned versions:

- `django-htmx==1.27.*`
- `htmx.org` 2.x bundled as a single static asset (CDN-fetched at
  build time or vendored under `kasia/static/vendor/`).
- `whitenoise` (latest stable; pulled via uv).

## Rationale

- Matches the requested screens' interactivity without paying for
  client-side state management.
- No JS toolchain to maintain — `uv` covers the whole dev
  dependency story.
- WhiteNoise lets gunicorn serve static files behind Caddy without
  a separate nginx static block, simplifying
  [`0024`](./0024-tls-caddy.md).
- htmx 2 is stable and likely to outlive any React major rev.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The Django settings module adds WhiteNoise to `MIDDLEWARE` and
  sets `STATICFILES_STORAGE` to compressed-manifest storage.
- Live-preview interactions on screen 07 implemented as htmx
  partial swaps backed by a Django view rendering the preview
  fragment.

**Forecloses (without follow-on decision):**

- A React / Vue / Svelte frontend.
- A separate static-file server (S3, dedicated nginx).

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R2 (browser-first, mobile-usable, no SPA).

**Makes implementable (0001–0013):**

- Live PDF preview on
  [`../screens/07-vydej.md`](../screens/07-vydej.md) — htmx swap on
  every line-item change.
- Search-as-you-type on catalogue + branch screens.
- Filter updates on dodáky list and movement history.
