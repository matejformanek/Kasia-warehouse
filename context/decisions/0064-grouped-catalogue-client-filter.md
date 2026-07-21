# 0064 — Grouped catalogue + multi-tbody client filter (extends 0063)

> **Amended by 0084** — the "counts/KPIs stay server-side, not search-scoped" trade-off is reversed; the KPI strip + per-group .sub-head counts now live-recompute client-side as you type.

**Date:** 2026-07-02
**Decider:** Matej (sklad UX-refresh Phase 2 replace, live review)
**Status:** Active
**Relates to:**
- [`0063-diacritic-insensitive-client-filtering.md`](./0063-diacritic-insensitive-client-filtering.md)
  — this widens the locked `data-filter-*` hook from a single tbody to many.
- [`0054-adopt-ui-directions.md`](./0054-adopt-ui-directions.md) +
  [`.claude/rules/design-system.md`](../../.claude/rules/design-system.md) —
  the Katalog is the sklad grouped-by-state screen; `.sub-head` section header
  joins the shared class list.

## Context

The locked Katalog mockup (`design-options/sklad/01b-katalog-grouped.html`) is
grouped by stock state into **three separate tables** — Prázdné (red) / Dochází
(orange) / V pořádku (neutral) — each under a `.sub-head` section header with a
count. Empty groups are not shown at all.

The 0063 live client filter was written for one flat list: `apply(input)` does
`document.querySelector(input.dataset.filterRows)` — **a single tbody** — and
has no notion of per-group section headers. Porting Katalog to the grouped
layout needs the one search box to filter across all three group tables at
once, and to hide a whole group's section (header + table) when nothing in it
matches. That is a behavioral change to a locked hook, so it is decision-gated.

## Options considered

- **Per-page bespoke JS for Katalog.** Rejected — 0063's whole point is one
  attribute-driven behaviour with no per-page JS; a second copy would drift.
- **Re-flatten Katalog into one table with group separator rows.** Rejected —
  the grouped three-table layout is the locked mockup, and separate `<table>`s
  keep each group's column set (Prázdné/Dochází carry a branch column, V pořádku
  does not).
- **Extend the shared `apply()` to iterate multiple tbodies + hide group
  sections.** Chosen. Backward-compatible: single-tbody lists that don't set
  `data-filter-group` behave exactly as before.

## Choice

Extend the shared filter behaviour in `kasia/templates/base.html`:

- `apply()` uses `document.querySelectorAll(input.dataset.filterRows)` (was
  `querySelector`) and iterates **every** matched tbody, filtering each tbody's
  `tr[data-filter-text]` rows. Total visible / total rows are summed across all
  tbodies for `data-filter-count` / `data-filter-empty` (unchanged semantics).
- **New optional per-tbody attribute `data-filter-group="<section selector>"`.**
  After filtering a tbody, if it carries `data-filter-group` the referenced
  section (the `.sub-head` header + its table, wrapped in one container) is
  hidden when the group has rows but none match, and shown otherwise. A tbody
  without `data-filter-group` is a plain single-list — no section hiding.
- The Katalog wires one `<input data-filter-rows=".cat-body" …>` targeting the
  three group `<tbody class="cat-body" data-filter-group="#cat-group-…">`.
- **Server-side grouping.** `catalogue_index` splits its computed rows into
  `empty_rows` / `low_rows` / `ok_rows` (reusing the existing effective/threshold
  state logic) and the template renders only the non-empty groups. The
  structured `kind` / `status` / `state` / `branch` selects stay server-side, as
  in 0063.
- **`.sub-head`** (group section header: dot + label + count, coloured
  red/orange/neutral) joins the shared sklad class list in `design-system.md`.

## Rationale

One shared, attribute-driven filter stays the rule; the extension is additive
and backward-compatible (every existing single-tbody filter — Historie, branch
dashboard stock, Dodavatelé/Odběratelé/Pobočky — keeps working untouched
because it sets no `data-filter-group` and `querySelectorAll` returns its one
tbody). Server-side grouping keeps the "Nalezeno: N" and per-group counts as
honest server-rendered totals (per 0063), while live typing narrows rows and
collapses emptied groups in the browser.

## Consequences

- `data-filter-rows` may now be a **multi-match selector**; `data-filter-group`
  joins the locked `data-filter-*` hook contract in `design-system.md`.
  Renaming any of them needs a new decision.
- Per-group `.sub-head` counts are **server-rendered totals** for the current
  server-side filter state; live client typing does not rewrite them (same
  trade-off as the "Nalezeno: N" count in 0063). An emptied group's whole
  section is hidden, so a stale non-zero count is never shown over zero rows.
- Katalog rows are **whole-row `row-link` with no per-row buttons** (the
  per-row "upravit" link is dropped; editing is on the product detail page).
- No new dependency, no DB migration, no Postgres-only SQL.
