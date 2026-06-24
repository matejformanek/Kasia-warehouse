# design-options — homepage visual exploration

Eighteen self-contained HTML mockups of the **owner dashboard** (the post-login
`Přehled` homepage), built so Petr can pick a visual direction. Exploration
artifacts only — **the live app (`base.html`, `home.html`) is not touched.**

## What this is

- Each `NN-*.html` is a fully standalone page (its own `<style>`, no Django,
  no shared CSS). All ten render the **same dashboard content with the same
  realistic Czech sample data** — only the *styling* differs, so you compare
  look-and-feel, not content.
- `index.html` is a gallery with live scaled thumbnails linking to each variant.
- `assets/` holds a copy of the Kasia logo + favicon so the folder is portable.

## Set one — bespoke directions

| # | Name | Flavour |
|---|------|---------|
| 01 | Mono Minimal | minimalist — near-monochrome, one accent, hairline rules |
| 02 | Swiss Grid | minimalist — strict typographic grid, single sharp accent |
| 03 | Warm Minimal | minimalist — paper background, spice-tone accent |
| 04 | Green Brand-forward | minimalist — accent lifted from the logo green |
| 05 | Dark Minimal | minimalist — calm dark dashboard, one luminous accent |
| 06 | Airy Editorial | minimalist — generous space, large type scale |
| 07 | Soft Cards | modern — rounded cards, soft shadows, friendly SaaS |
| 08 | Editorial / Typographic | modern — bold magazine-grade type hierarchy |
| 09 | Classic Serif Business | old-school — serif, navy/burgundy, formal, bordered |
| 10 | Bordered ERP | old-school — dense bordered tables, beveled chrome |

Spread: **6 minimalist · 2 modern · 2 old-school.**

## Set two — inspired by popular products

Each channels the design language of a well-known product (same content, different "voice").

| # | Name | Inspired by |
|---|------|-------------|
| 11 | Linear | Linear — dark indigo, ultra-crafted, low-chrome |
| 12 | Stripe | Stripe dashboard — light, blurple gradient hero, fintech-clean |
| 13 | Notion | Notion — document-like, monochrome, soft callouts |
| 14 | Vercel | Vercel/Geist — stark black & white, monospace numerics |
| 15 | Shopify | Shopify admin (Polaris) — green, badge-driven, merchant-friendly |
| 16 | Apple | macOS / System Settings — frosted glass, rounded, Apple blue |
| 17 | GitHub | GitHub (Primer) — bordered boxes, blue/green, dev-dashboard |
| 18 | Airbnb | Airbnb DLS — warm coral, rounded, consumer-friendly |

## How to view

Double-clicking a single `NN-*.html` works, but the **gallery thumbnails only
load when served over HTTP**. From the repo root:

```bash
cd design-options && uv run python -m http.server 8000
```

Then open <http://localhost:8000/>. Click any thumbnail to open the full page.

## How to pick

Browse the gallery, open the two or three you like full-screen, and tell Matej
the number. The chosen direction then becomes:

1. a logged decision in `context/decisions/NNNN-*.md`, and
2. a separate port task that applies the style to the real `base.html` /
   `home.html` templates (this folder is never shipped as-is).

## Not in scope

- No changes to the production app until a direction is picked.
- Only the homepage — no other screens were restyled.
