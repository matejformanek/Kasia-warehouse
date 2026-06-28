# Public-site design mockups (`design-options/public/`)

Standalone static HTML mockups of the **new public marketing website** for
Kasia vera s.r.o. — a review surface for Petr to pick a visual direction.
These are **not** production code; they live alongside the warehouse-dashboard
mockups in `design-options/` and are served at `/static/navrhy/public/`.

Each homepage mockup renders the **same realistic Czech sample content** (real
company facts from `web/content.py`) so the comparison is about *style*, not
copy. Final winner gets ported into the real `web/` Django templates per
`context/public-site.md`.

## Files

`logos.html` was removed (logo concepts dropped from this set). The original
four homepage mockups (01–04) are kept as reference; ten new homepage
directions (06–15) were added — **all without a logo image** (text wordmark
"Kasia vera" only), minimalistic & modern, anchored mainly on the current
green/clean look + `02-clean-green`.

| File | What it is |
|------|------------|
| `index.html` | Sub-gallery — thumbnail grid (new directions, original directions, Kontakt). |
| `01-warm-editorial.html` | Original — warm, editorial, spice-toned, serif display. |
| `02-clean-green.html` | Original — clean modern, green brand-forward (a key reference). |
| `03-bold-photographic.html` | Original — bold, photo-led, gradient placeholders. |
| `04-minimalist.html` | Original — restrained, type-driven, minimal colour. |
| `05-kontakt.html` | Kontakt page — details + poptávkový formulář + map placeholder (visual only). |
| `06-green-split.html` | New — split-screen hero, deep green + cream. |
| `07-mono-green.html` | New — near-monochrome, green as single accent, type-driven. |
| `08-sage-cards.html` | New — soft sage-green tinted cards, friendly modern B2B. |
| `09-editorial-minimal.html` | New — serif-led editorial, generous whitespace, one green accent. |
| `10-dark-green.html` | New — premium dark forest-green, gold accent. |
| `11-centered-modern.html` | New — centered single-axis landing, green CTA. |
| `12-saas-clean.html` | New — corporate B2B-SaaS structure, green primary. |
| `13-warm-neutral.html` | New — warm sand/stone palette + green accent. |
| `14-bold-type.html` | New — oversized bold grotesque headline, graphic. |
| `15-grid-sections.html` | New — modular tiled grid, Swiss-influenced. |
| `assets/` | Local copy of `favicon-32.png` (+ `kasia-logo.jpg`, used only by the original 01–04). |

## Conventions

- Czech UI text, diacritics intact (UTF-8). English only in HTML comments / filenames.
- Each mockup is fully self-contained: one HTML file, all CSS inline. The only
  external request is the Google Fonts `<link>` (as in the parent gallery).
  No other CDNs, no external images.
- **New designs (06–15) use no logo image** — a styled text wordmark "Kasia vera".
  The original 01–04 still reference the local `assets/kasia-logo.jpg`.
- All links are relative (the set is served from a static subdirectory).
- Real Kasia facts: IČO 25756729, Nádražní 1202/5, 251 01 Říčany u Prahy,
  +420 323 601 422 / 424, info@kasia.cz, datová schránka emye9prc,
  Po–Pá 7:00–15:00, founded leden 1993, brand VERA GURMET, "369 druhů koření /
  236 kulinářských produktů".
- TYN/SEZ provozovny use placeholder "(adresa bude doplněna)" — no invented streets.

## Imagery to source (placeholders only in these mockups)

These mockups use **CSS gradients / colored blocks** wherever photography would
go (see the captions like "(zde foto koření)" in `03-bold-photographic.html`).
Real imagery must come from Petr or licensed stock before the public site ships:

- **Hero / brand photography** — koření in bulk, spice close-ups (texture, color).
- **Process photos** — dovoz → čištění/třídění/mletí → míchání → balení.
- **Sídlo / provozovny** — exterior or interior of Říčany u Prahy + (later) TYN/SEZ.
- **Team / firma** — a human, rodinná-firma touch for the O nás page.
- **Open Graph / social preview image** — a single branded share image.

No text-to-image generation is used. Until real photos exist, the gradient
placeholders mark composition only.
