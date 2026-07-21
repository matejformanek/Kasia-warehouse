# 0084 — Live KPI + group-count recompute on the name filter

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, sklad UX round — live-app review)
**Status:** Accepted
**Amends:** [`0063`](./0063-diacritic-insensitive-client-filtering.md) +
[`0064`](./0064-grouped-catalogue-client-filter.md) — the "counts/KPIs stay
server-side, not search-scoped" trade-off recorded in both is reversed. The
folding/fuzzy filter itself (0063) and the grouped multi-tbody hide/show (0064)
stand unchanged; only the frozen-numbers behaviour is amended.
**Relates to:**
- [`0054-adopt-ui-directions.md`](./0054-adopt-ui-directions.md) +
  [`.claude/rules/design-system.md`](../../.claude/rules/design-system.md) —
  adds new locked sklad JS hooks (`data-kpi-live`, `data-filter-bucket`,
  `data-filter-kg`) to the `data-filter-*` contract.
- [`0072-reorder-threshold-not-null.md`](./0072-reorder-threshold-not-null.md)
  — the empty/low grouping the live counts mirror.

## Context

On the two grouped stock screens — the Katalog (`catalogue_index`) and the
branch **Stav skladu** on `branch_dashboard` — the top KPI strip
(Prázdné / Dochází / Produktů / Celková zásoba) and the per-group `.sub-head`
counts ("Prázdné 5", "Dochází 3") are computed server-side in
`catalogue_stock_groups` and rendered once. The shared live name filter (0063 /
0064, `base.html` `apply()`) only hides/shows rows and whole groups; it never
touches the KPI values or the `.sub-head .count`. The name box (`q`) is
deliberately client-only, so no reload recomputes them.

The result: typing in the search box narrows the visible rows, but every "top"
number stays frozen at the whole-scope figure. Petr/Karolína want the top
numbers to update as you type — the same way selecting a dropdown reloads and
recomputes them. That directly reverses the trade-off recorded in **0063**
(Consequences) and **0064** (Consequences), which chose to keep counts/KPIs
server-rendered and *not* search-scoped (so they wouldn't move while typing, and
to leave the count assertions green).

## Options considered

- **Server round-trip on `q` (drop the client-only search).** Rejected —
  reintroduces a reload per keystroke, loses the as-you-type feel that 0063 was
  built for, and defeats the point of the client filter.
- **Leave it as-is (documented trade-off).** Rejected — the frozen numbers read
  as a bug to the operators; the ask is explicit.
- **Client recompute of the KPI strip + group counts from visible rows,
  cache-and-restore (chosen).** The filter already walks every row; it can
  accumulate per-state buckets, a stocked count, and a kg sum in the same loop
  and write them into marked elements.

## Choice

Extend the existing 0063/0064 `apply()` — no per-page JS — to **recompute the
KPI strip and each group's `.sub-head` count client-side from the currently
visible rows** as the operator types, and **restore the server-original values
when the box is emptied**.

- The server contract is pinned by three new attributes: `data-filter-bucket`
  (`empty`/`low`/`ok`) on each group `<tbody>`, `data-filter-kg` (raw on-hand
  sum, `|unlocalize`d dot-decimal) on each row, and `data-kpi-live`
  (`empty`/`low`/`products`/`products-stocked`/`total-kg`) on each KPI value
  span.
- **Cache-and-restore**: on every `apply()` run the first thing done per target
  element is to cache the server-original text if not yet cached, then branch to
  recompute (query present) or restore (query empty). This matters because the
  on-load `apply()` may run against an echoed `?q=` (Katalog), and because the
  Katalog KPIs are intentionally whole-scope *before* `?state=` narrows — a
  plain load must never clobber them to the rendered subset.
- `data-kpi-live` is a **separate hook** from the reserved-but-unwired
  `data-filter-count` (0063) because the KPI strip is several per-state buckets +
  a kg sum, not a single visible-row total; `data-filter-count` remains the
  single-total hook.
- Gated on `hasBuckets` (any matched tbody carrying `data-filter-bucket`), so the
  history / email-log single-list filters and the filter-less home Přehled are
  untouched.

## Rationale

The loop that already hides/shows rows is the cheapest place to also tally the
buckets — one pass, no extra DOM queries per row. Cache-and-restore keeps the
server render authoritative (whole-scope, `?state=`-aware) while giving the
live, search-scoped numbers on demand. Attribute-driven keeps it inside the
established filter contract with zero per-page JS, consistent with 0063/0064.

## Consequences

- New locked JS hooks join the `data-filter-*` contract in `design-system.md`:
  `data-kpi-live`, `data-filter-bucket`, `data-filter-kg`. Renaming any of them
  is a new decision.
- The KPI strip + per-group `.sub-head` counts now **live-recompute** from
  visible rows while typing, and **restore** to the server originals when the
  box is cleared. Server-rendered values remain the initial / whole-scope figure
  (and, on the Katalog, stay whole-scope before `?state=` narrows).
- `data-filter-kg` must be `|unlocalize`d (dot-decimal) — a Czech-comma value
  would make JS `parseFloat` truncate the kg sum silently. Display cells keep
  `floatformat:1`.
- The Katalog server KPIs now reflect **every** server filter combined — kind
  (Typ) / status / branch / **state (Stav skladu)** — computed from the
  displayed row set *after* the `?state=` narrowing, so the top numbers always
  match what's on screen (a Typ + Stav-skladu combo narrows them together, not
  just Typ). This supersedes the earlier "KPIs are whole-scope before `?state=`
  narrows" behaviour. An empty name box therefore restores the state-consistent
  server values; typing narrows further within them.
- Intended edge (documented, not a bug): an archived product with residual
  stock is in the server `kpi_products` but has no rendered row, so the live
  count omits it — clearing the box restores the exact server value.
