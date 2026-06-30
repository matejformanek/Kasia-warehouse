# 0058 — Public-site redesign adoption + Produkty page

**Date:** 2026-06-30 · **By:** Matej (stand-in for Petr)

## Context

The public marketing site (`web` app) shipped under
[`0050`](./0050-public-site-and-sklad-split.md) /
[`0051`](./0051-public-site-ia-and-content.md) /
[`0054`](./0054-adopt-ui-directions.md) as a **centered / curvy green** look
(Sora + Inter, soft shadows, radius 18px) across **four** pages
(Domů / O nás / Provozovny / Kontakt).

Matej found it incomplete and "AI-only" and ran a heavy redesign exploration
(PR #17 — `design-options/public/`, `context/public-site-research.md`): research
→ named directions → homepage iterations → a chosen direction → a full 5-page
proposition. The chosen direction is mockup **`28-mono-final-lightgreen.html`**
(homepage) + **`29`–`32`** (sub-pages). This decision adopts it into the real
templates and promotes the **Produkty/Sortiment** page to the live IA.

## Options considered

- **Keep 0054** (centered/curvy/green, 4 pages) — rejected; Matej wants the new look.
- **Adopt the new direction, public surface only** — chosen.
- Adopt across sklad too — rejected; the warehouse app keeps its sharp/sidebar
  system (the "Technical B2B" mockup 16 is parked as a *possible future* sklad
  restyle, not in scope here).

## Choice

Adopt the **"mono × centered, light-green-sections"** direction for the
**public surface only** and grow the IA to **five pages**:

- **Visual system (public `web/base.html`):** brand-green sticky nav bar
  `#006634` with white nav text + the real logo image; **Space Grotesk**
  (display) + **Inter** (body); white body; **deep forest-green `#0a3b20`**
  section bands (white text) for the "process" / "contact" beats; sharp-ish
  radii + pill buttons; green primary / outline secondary buttons. Slogan
  **"Koření, které gurmán ocení."**
- **IA → 5 pages:** Domů · O nás · **Sortiment (`/produkty/`, new)** ·
  Provozovny · Kontakt. **Kvalita** and **Pro koho** stay **folded** into
  Domů / O nás sections (decided at design time — they leaned on certs /
  testimonials we don't have); they do **not** become standalone pages.
- **Kontakt** stays **info-only** (no form, per [`0052`](./0052-kontakt-info-only-drop-contactinquiry.md)):
  a compact "rychlý kontakt" block + map + a "kontaktní osoby" section below.
- **Maps:** switch the public embeds from OpenStreetMap to **Google Maps**
  (Matej's preference). The footer privacy note is updated accordingly (see
  Consequences — this trades the cookie-free OSM promise for Google's embed).
- **Honest facts only:** no fabricated certifications, testimonials, customer
  logos, product photography, prices, or SKUs. **No "na míru"** claims — Kasia
  does not do made-to-order work.

## Rationale

The direction was chosen after a multi-round exploration Matej drove
personally; this records the already-made design choice (per
`feedback_no_signoff_gate`) and lifts the `no-premature-tech-choices` /
`design-system.md` gate for the public surface. Right-sized: still one Django
project, one DB, static request/response, hand-authored CSS/SVG, no new tech
layer.

## Consequences

- **Supersedes [`0054`](./0054-adopt-ui-directions.md) for the PUBLIC surface
  only.** The sklad sharp/sidebar/green system in `kasia/templates/base.html`
  is unchanged. 0054's banner points here.
- **Amends [`0051`](./0051-public-site-ia-and-content.md)'s locked 4-page IA →
  5 pages** by promoting Produkty/Sortiment. The other deferred pages
  (Encyklopedie, Sponzorství) stay deferred; Kvalita / Pro koho are folded, not
  shipped.
- **Public shared CSS class names change** (the 0054 contract — `.eyebrow`,
  `.contact-panel`, `.people`/`.person`, `.branches`/`.branch`, `.btn-outline`,
  …). `design-system.md`'s **public block** is rewritten to the new contract;
  the **sklad block + JS/HTMX hooks are untouched**.
- **New code:** `web/produkty` view (`@login_not_required`), `path` in
  `web/urls.py`, `produkty.html` template, a `Sortiment` entry in
  `web/content.py` `NAV`, and product-category / brand data in `content.py`.
  Sitemap's hardcoded page list (`web/views.py`) gains `web:produkty`.
  `web/tests.py` updated for the new copy + the new page.
- **Privacy:** Google Maps embeds set third-party cookies; the footer note is
  changed from "nepoužívá sledovací cookies … OpenStreetMap" to an honest
  Google-Maps wording. A formal consent shim is **not** built now (right-sized,
  pre-launch, ~6 users) — flagged for revisit before public launch.
- **`/navrhy/` gallery** stays for now (per [`0047`](./0047-design-gallery.md));
  retiring its public exposure is a later, separate change.
- Production public pages change for real visitors on the next deploy to `main`.
