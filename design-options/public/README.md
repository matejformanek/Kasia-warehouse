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

| File | What it is |
|------|------------|
| `index.html` | Sub-gallery — thumbnail grid linking everything below (same card/iframe/cover mechanism as the parent `design-options/index.html`). |
| `01-warm-editorial.html` | Homepage — warm, editorial, spice-toned (paprika/cumin warmth), serif display type, generous spacing. |
| `02-clean-green.html` | Homepage — clean modern, green brand-forward, crisp and corporate-friendly. |
| `03-bold-photographic.html` | Homepage — bold, photo-led. CSS-gradient blocks stand in for photography with `(zde foto …)` captions showing where real images go. |
| `04-minimalist.html` | Homepage — restrained, lots of whitespace, type-driven, minimal color. |
| `05-kontakt.html` | Kontakt page — contact-details block + poptávkový/kontaktní formulář (jméno, e-mail, telefon, zpráva, GDPR souhlas) + static map placeholder. Form is visual only. Done in the `02-clean-green` direction. |
| `logos.html` | Three hand-authored inline-SVG wordmark/leaf-mark concepts for "Kasia vera", each on light + dark backgrounds at two sizes. |
| `assets/` | Local copies of `kasia-logo.jpg` + `favicon-32.png` (copied from `design-options/assets/`). |

## Conventions

- Czech UI text, diacritics intact (UTF-8). English only in HTML comments / filenames.
- Each mockup is fully self-contained: one HTML file, all CSS inline. The only
  external request is the Google Fonts `<link>` (as in the parent gallery).
  No other CDNs, no external images. Brand logo via local `assets/kasia-logo.jpg`.
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
