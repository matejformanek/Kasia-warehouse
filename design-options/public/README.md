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

The **2026 overhaul set** (16–17) comes from the deep public-site rework — see
[`context/public-site-research.md`](../../context/public-site-research.md) for the
UX findings, visual POV, and per-page blueprint. Unlike 06–15, these use the real
`branch-*.jpg` photos and hand-authored SVG koření (never stock/fabricated imagery),
and bake in sharper Czech B2B copy. Built honestly: **no certifications, no
testimonials/customer logos, no product photos, no prices/SKUs** — the whole point is
to escape the generic "AI-template" look with verifiable facts only.

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
| `16-technical-b2b.html` | Overhaul (2026) — "Clean technical B2B": sober spec-sheet, IBM Plex Mono numerals. **Deferred for the public site**; kept as a candidate look for a future **sklad (warehouse-app) restyle**. |
| `17-modern-grocer.html` | Overhaul (2026) — "Bold modern grocer": oversized Sora + green/spice blocks + commodity SVG. **Superseded** by the modern-minimalist set (18–21). |
| `18-airy-editorial.html` | Modern minimalist — "Vzdušný editorial": whitespace + typography led, Fraunces display + Inter, single green accent, hairline rules, no boxes. |
| `19-soft-warm.html` | Modern minimalist — "Měkký moderní": warm cream canvas, soft shadows, rounded frames, friendly contemporary B2B. |
| `20-mono-contrast.html` | Modern minimalist — "Monochrom": near-monochrome high-contrast, Space Grotesk + Inter, one decisive green, precise hierarchy. |
| `21-swiss-grid.html` | Modern minimalist — "Švýcarská mřížka": disciplined editorial grid, numbered micro-labels, column rules, generous negative space. |
| `22-mono-centered.html` | **Lead candidate** — fuses 20 (Monochrom) + 11 (centered). Sharp monochrome, centered, real logo image, slogan "Koření, které gurmán ocení", centered facts, redesigned sortiment, contained story, no export, closing with contact + all 4 provozovny. |
| `23-mono-centered-soft.html` | **Chosen direction** — same fusion, softened (pill buttons, rounded frames, gentle green-tint bands, more breathing room). |
| `24-mono-centered-green.html` | Refined 23 + all tweaks; **green primary buttons**. (Process in page-21 format, KASIA VERA \| VERA GURMET, aligned provozovny cards, closing → contacts, footer bottom = © / Přihlášení.) |
| `25-mono-centered-black.html` | Refined 23 + all tweaks; **black/ink primary buttons** (comparison). |
| `26-mono-centered-green-accent.html` | Refined 23 + all tweaks; **green buttons + warmer green-tint bands & more breathing room**. |
| `27-mono-final.html` | **★ Final homepage** (from 24) — green `#006634` nav bar + white text + logo, green buttons, hero buttons swapped (left "Náš sortiment" ghost / right green "Poptat sortiment"), "Jak pracujeme" compact 6-step page-21 grid, brand line "KASIA VERA \| VERA GURMET" only, closing adds a "Naše provozovny" button, footer trimmed (no Po–Pá / IČO / datová schránka), bottom strip = © left + "Přihlášení do skladu" right. The basis for the real port. |
| `28-mono-final-lightgreen.html` | **★ Chosen homepage** — sections 02 "Jak pracujeme" + 06 "Spojte se s námi" on a deep forest-green band (`--lgreen #0a3b20`, white text). Nav links to the sub-pages below. The locked theme all other pages inherit. |
| `29-o-nas.html` | **Page proposition — O nás** (theme 28): story + milestone timeline, vedení (3 exec portraits), deep-green statement band, dovoz a dosah, CTA. |
| `30-produkty.html` | **Page proposition — Sortiment** (theme 28): 5 category clusters (hand-authored SVG, no photos/prices/SKUs), KASIA VERA \| VERA GURMET brand, VEGA/Zlaté kuře flagged keep-or-drop, deep-green "balení na míru" band. |
| `31-provozovny.html` | **Page proposition — Provozovny** (theme 28): 4 location cards (real building photo + address + tel + Po–Pá hours + OSM embed + "Otevřít v mapách"), Říčany marked Sídlo, obchodní zástupci note. |
| `32-kontakt.html` | **Page proposition — Kontakt** (theme 28, info-only, no form): statutory block (IČO + datová schránka live here), 3 kontaktní osoby (honest empty slots for personal contacts), OSM map of sídlo, deep-green phone CTA band. |
| `assets/` | Local copy of `favicon-32.png`, `kasia-logo.jpg` (01–04), and the real `branch-*.jpg` + `exec-*.jpg` photos (used by 16–17 and the Phase-3 per-page mockups). |

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
