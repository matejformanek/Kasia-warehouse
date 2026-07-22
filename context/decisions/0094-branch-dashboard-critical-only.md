# 0094 — Obsluha branch Přehled „Stav skladu" renders only critical groups (Prázdné + Dochází)

**Date:** 2026-07-22
**Decider:** Matej (standing in for Petr)
**Status:** Active — supersedes the three-group clause of the branch-dashboard
design in [`0064`](./0064-grouped-catalogue-client-filter.md) /
`design-system.md`; interacts with [`0072`](./0072-reorder-threshold-not-null.md)
+ [`0084`](./0084-live-kpi-recompute-on-name-filter.md)

## Context

The obsluha branch Přehled (`branch_dashboard`) „Stav skladu" card renders the
**whole** branch catalog: three groups — Prázdné / Dochází / **V pořádku** — via
`catalogue_stock_groups([branch])`, matching the branch-scoped Katalog. On a
real branch the V-pořádku tail is the vast majority of rows, so the landing page
(the obsluha's first screen after login) is flooded with healthy stock and the
few items that actually need attention are buried below the fold.

The full catalog is already reachable to obsluha via the **branch-scoped
Katalog** (a nav item they have) and **Inventura** — so the dashboard doesn't
need to duplicate it. The owner home already shows only the attention buckets;
the branch dashboard is the outlier.

## Options considered

1. **Keep three groups, collapse V pořádku behind a `<details>`.** Rejected —
   extra interaction, still ships hundreds of rows, and the KPI-live recompute
   would still need them rendered.
2. **Render only the two critical groups (Prázdné + Dochází); drop V pořádku.**
   **Chosen.** The healthy tail lives in Katalog; the landing shows only what
   needs action, mirroring the owner home.

## Choice

`branch_dashboard()` still calls `catalogue_stock_groups([branch])` (its
`kpi_empty`/`kpi_low` keep feeding the header) but **no longer passes
`ok_rows`** to the template. `branch_dashboard.html` renders only the
`empty_rows` + `low_rows` groups, and shows a positive empty-state („Vše nad
objednacím bodem — nic nedochází. Celý sklad najdete v Katalogu.") when nothing
is critical. The `#branch-stock-empty` „Nic neodpovídá hledání." filter line
stays.

Because V pořádku no longer renders, the two KPI spans that the
[`0084`](./0084-live-kpi-recompute-on-name-filter.md) live-recompute sums from
**visible rows** — `products-stocked` and `total-kg` — **drop their
`data-kpi-live` attribute** and stay static server-wide branch values (a live
recompute would under-count while filtering). `empty` + `low` **keep**
`data-kpi-live`: they recompute correctly from the visible critical rows.

## Rationale

- **Right-sized for the operator.** The landing shows only actionable stock;
  ~6 users don't need the healthy tail on their home screen.
- **No duplication.** Full stock stays in the branch-scoped Katalog + Inventura,
  both already available to obsluha.
- **Consistent.** Matches the owner home, which already shows only attention
  buckets.

## Date & by-whom

2026-07-22 — Matej (standing in for Petr).

## Consequences

**Unblocks:**

- A focused obsluha landing — Prázdné + Dochází only, no scrolling past the
  healthy tail.

**Commits us to:**

- V pořádku is **Katalog-only** on the branch surface; re-adding it to the
  dashboard is a new decision. Recorded in `.claude/rules/design-system.md`
  („Obsluha Přehled" bullet).
- `products-stocked`/`total-kg` on `branch_dashboard` are **static** (no
  `data-kpi-live`). This is a per-template choice, not a hook rename — the
  `data-kpi-live` hook itself is unchanged and still forbidden to rename.

**No change to:**

- The shared `catalogue_stock_groups` helper (still returns all three groups;
  the view just doesn't forward `ok_rows`), the Katalog (still three groups),
  the header `kpi_empty`/`kpi_low` source, or the 0064 grouped-filter hooks.
- The „do not flatten this back to a status-badge table" + shared-hook-rename
  prohibitions from the original branch-dashboard design still hold.
