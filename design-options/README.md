# design-options — visual exploration galleries

Self-contained HTML mockups for picking a visual direction. Two galleries:

- **This folder (`design-options/`)** — the **warehouse dashboard** (`sklad`,
  the post-login `Přehled` homepage). Open `index.html`.
- **[`public/`](./public/index.html)** — the **public marketing website**
  (`/`). Open `public/index.html`.

Exploration artifacts only — the live templates are not touched until a
direction is chosen.

## Sklad gallery (this folder)

Each `NN-*.html` is fully standalone (own `<style>`, no Django, no shared CSS)
and renders the **same dashboard content with the same realistic Czech sample
data** — only the *styling* differs. `assets/` holds the logo + favicon.

After the first review round, the set was narrowed to four chosen directions
plus ten new ones designed in the same light / minimalist / modern feel.

### Chosen directions (kept)

| # | Name | Flavour |
|---|------|---------|
| 01 | Mono Minimal | near-monochrome, one accent, hairline rules |
| 02 | Swiss Grid | strict typographic grid, single sharp accent |
| 04 | Green Brand-forward | accent lifted from the logo green |
| 07 | Soft Cards | rounded cards, soft shadows, friendly modern |

### New directions (same spirit)

| # | Name | Flavour |
|---|------|---------|
| 11 | Indigo Minimal | mono + cool indigo accent, hairlines |
| 12 | Slate & Amber | cool slate UI, warm amber accent |
| 13 | Sidebar App | left-sidebar admin app shell |
| 14 | Teal Calm | airy, soft teal accent |
| 15 | Data / Numerals | big tabular KPI numbers, analytics feel |
| 16 | Pastel Cards | soft per-section pastel colour-coding |
| 17 | Outline / Line-art | all-outline, zero-fill geometric |
| 18 | Sand Minimal | warm sand/stone neutral, muted accent |
| 19 | Compact Pro | dense, efficient daily-driver layout |
| 20 | Green Pro | green header band + card-strip structure |

All ten are light, minimalist, and modern — no dark/old-school/maximalist.

## How to view

Thumbnails only load over HTTP:

```bash
cd design-options && uv run python -m http.server 8000
```

Open <http://localhost:8000/> (sklad) and <http://localhost:8000/public/> (public).
On prod the galleries are served under `/static/navrhy/` and `/static/navrhy/public/`
(entry redirect `/navrhy/`), per `context/decisions/0047-design-review-gallery.md`.

## How to pick

Browse, open your favourites full-screen, and tell Matej the numbers. The
chosen direction becomes a logged decision and a separate port task into the
real templates — this folder is never shipped as-is.
