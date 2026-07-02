# Sklad (warehouse-app) UX-refresh mockups (`design-options/sklad/`)

Standalone static HTML mockups of the **login-gated warehouse app** (`inventory`
+ `accounts`, under `/sklad/…`) — a review surface to pick the per-screen design.
Not production code; served at `/static/navrhy/sklad/`, reached from the root
gallery. Polish + UX **within the locked 0054 direction** (sharp / radius-0, brand
green, left sidebar, Inter + IBM Plex Mono, KPI strips) — not a redesign.

## Locked choices

- **Warning hue = Orange** `--warn:#c2410c` / `--warn-tint:#fdeee3` (kills the old
  brown). 
- **Czech number format** — displayed decimals use a comma (`182,400`); form
  `value=`/`data-*` keep a dot; JS parses `,`→`.` and emits `,`.
- **Zebra striping = NEUTRAL grey `#f4f4f4`** (not greenish — green next to the
  orange "dochází" was a good/bad clash). On Přehled, colour is **section-level**
  (red/orange headers), never per-row tint, so green never sits beside orange.
- **Inventura + Detail produktu = approved.**

## Two picks to make

- **Katalog — A–D.** All based on A and unified with the Přehled visual language
  (red = prázdné, orange = dochází, `.sub-head` sections, neutral zebra, commas,
  breathing). They differ in how the table shows state: standard (A) / grouped
  like the Přehled (B) / left-border urgent-first (C) / Efektivně-emphasis (D).
- **Přehled — converged** (branches side by side). Overview KPI strip on top;
  per branch three distinct groups **Vyprodáno** (red) / **Dochází** (orange, to
  reorder) / **Objednáno** (muted, already handled), a per-branch summary line +
  an **Inventura {branch}** button, and a **K vyřešení** block with actions
  (resend e-mail / open dodák). Colour is section-level only.

## Files

| File | What it is |
|------|------------|
| `index.html` | Sub-gallery grid. |
| `01a-katalog-kpi.html` | **Katalog A** (baseline, liked) — KPI strip + standard table; quiet row-tint + loud `dochází` chip; per-row `upravit`. Warn swatch. |
| `01b-katalog-grouped.html` | **Katalog B** — grouped by state with the Přehled `.sub-head` sections (Prázdné / Dochází / V pořádku), colour at section level, breathing between. |
| `01c-katalog-leftborder.html` | **Katalog C** — one flat table, urgent-first, status via a sharp coloured left border (red empty / orange low), chips kept, airier. |
| `01d-katalog-emphasis.html` | **Katalog D** — "Efektivně" number dominant, secondary columns muted. |
| `02a-prehled.html` | **Přehled** (chosen) — branches side by side; overview KPI strip (Vyprodáno · Dochází · Objednáno · K vyřešení); per branch Vyprodáno / Dochází / Objednáno groups + summary + Inventura button; K vyřešení with resend/open actions; bottom: Poslední pohyby + Poslední dodací listy. |
| `03-inventura.html` | **Approved** — sticky tally bar, changed-row accent, type-to-filter, `[STAV]` card. |
| `04-detail-produktu.html` | **Approved** — stock KPI strip, obsluha scope note, qty in movements, recipe-scaler JS preserved. |
| `05-vydej.html` | Secondary — live dodací-list preview + bottom summary; overdraw error-red. |
| `06-michani.html` | Secondary — consumption shortfall + state chips; Zrušit-dávku on warn-tint. Warn swatch. |
| `07-branch-dashboard.html` | Secondary — obsluha home, stock rows → detail, KPI + as-of. |
| `assets/` | Local `favicon-32.png` + `kasia-logo.jpg`. |

## Conventions

- Czech UI text, diacritics intact. English only in HTML comments / filenames.
- Self-contained: one HTML file, all CSS + JS inline (only external = Google Fonts
  Inter + IBM Plex Mono). No standalone `.css`/`.js`, no other CDNs, no external
  images. Tokens mirror `kasia/templates/base.html`; class names + hooks unchanged.
- Data: TYN (Týniště nad Orlicí) + SEZ (Sezimovo Ústí), real product names, kg
  tabular-nums.

## Phase 2 (after sign-off)

Adopt the chosen Katalog look + Přehled layout into `kasia/templates/*` +
`inventory/views.py`/`urls.py`, retone `base.html`, then tests/docs. The
**Objednáno** signal needs new backing data (no purchase-order concept in MVP) —
follow-up decision if kept.
