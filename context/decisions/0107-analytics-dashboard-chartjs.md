# 0107 — Statistiky: vlastník-only analytics dashboard at `/sklad/statistiky/`, charts via vendored Chart.js

**Date:** 2026-11-02
**Decider:** Matej (on Petr's request of 2026-10-23)
**Status:** Active (wording confirmed by Matej 2026-11-02; named „Statistiky" because „Přehled" is the home screen)

## Context

Petr asked "kolik se spotřebovalo za měsíc česnek G5 minced / česnek granule"
in míchání. Nothing in the app answers consumption-over-time questions: Historie
lists movements, Přehled shows current stock. Petr will not build charts
himself; he asks Matej and Matej adds a panel in code. Charts are a new layer
(client-side charting library), so per `no-premature-tech-choices.md` it needs a
decision before code.

Data meaning (no new data is needed): `Movement` (`status=done`,
`date_issued`) + `MovementLine.quantity_kg`. **Míchání consumption** = výdej to
the internal `micharna` customer; **sales** = výdej to non-internal customers;
**příjem** = prijem; **produced** = `MixingJob` (done). `Product.is_unlimited`
products are excluded from kg sums.

## Options considered

1. **Server-rendered tables only** — no new layer, but no trend view; weak for the
   "per month" question.
2. **Chart.js, vendored** in `kasia/static/vendor/` (single file, like htmx per
   0018) — canvas charts, tooltips, legend toggle, no bundler.
3. **Chart.js from a CDN** — third-party request from `/sklad/`; rejected (0076
   forbids third-party trackers there, and the file should be pinned).
4. **Inline SVG hand-rolled** — no interactivity without a lot of code.
5. **Chart builder / saved views for Petr** — rejected: Petr will not use it;
   far more code and permission surface.

## Choice

Option 2. A **fixed set of panels** with a global filter bar (date range,
granularity day/month/year, pobočka, produkty), as GET params (shareable URL).

- **Vlastník only** (`require_vlastnik`); obsluha gets 403, anonymous is
  redirected to login. Route `statistiky/` under `/sklad/`, nav link in Správa.
- **Chart.js** pinned and vendored in `kasia/static/vendor/` (version and
  licence added to `vendor/README.md`). No CDN, no bundler. No CSP is set
  (0105), so no header change.
- **Server-side aggregation** (ORM `Sum` / `TruncDay|Month|Year`) in
  `inventory/services/analytics.py`; chart data handed to the page with
  `json_script`. **No new model, no migration, no cache, no background job.**
- **Panel registry** (`PANELS`: key, title, section, query function, chart
  type): adding a panel is one function + one entry. No user-defined charts.
- Sections: Přehled, Spotřeba v míchání, Výdeje, Příjem, Dávky a lidé. Per-table
  CSV download (UTF-8 BOM, `;`).
- Theme from the existing sklad CSS tokens (sharp corners, green accent).
  Quantities follow 0061 (1 dp, comma display).

## Rationale

Smallest thing that answers Petr's question and the next ones: one vendored
file, queries on existing tables, vlastník-only. A builder or saved views would
be enterprise-shaped for one reader (`right-sized-for-small-business.md`).

## Consequences

- New vendored JS dependency (Chart.js, ~200 KB) to bump by hand.
- New hooks to treat as stable once shipped (listed in `design-system.md`).
- Early charts are sparse: prod data was wiped at go-live (0087).
- Date basis is `Movement.date_issued`; retroactive mixes follow it, not
  `started_at`.
- Future per-user dashboards, exports to the účetní, or caching are new
  decisions.
