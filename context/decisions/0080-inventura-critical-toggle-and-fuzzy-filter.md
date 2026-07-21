# 0080 — Inventura „Dochází / prázdné" critical toggle + fuzzy filter

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, sklad UX round — found while reviewing)
**Status:** Accepted
**Amends:** [`0065`](./0065-inventura-sidebar-nav.md) (the single-branch toggle),
relates to [`0063`](./0063-diacritic-insensitive-client-filtering.md) (filter),
[`0072`](./0072-reorder-threshold-not-null.md) (empty rule)

## Context

Two inconsistencies surfaced on the single-branch Inventura, both against the
Katalog behaviour a user reasonably expects:

1. **The „Dochází" toggle hid genuinely-empty products.** Its membership came
   from `low_stock_rows()`, whose rule is bare `effective < threshold`. Since
   [`0072`](./0072-reorder-threshold-not-null.md) made the reorder threshold
   **not-null, default 0**, an empty product (effective 0) with the default
   threshold 0 fails `0 < 0` and was excluded. So a branch with 6 empty + 1 low
   product showed only the handful with a *positive* threshold (e.g. 3/12),
   while the Katalog correctly shows all 7 as Prázdné + Dochází. The toggle is
   meant to surface „what needs attention" — an empty spice is the most
   critical case, yet it was hidden.
2. **The name filter wasn't the smart one.** Inventura used a bespoke
   `name.includes(q)` (case-insensitive substring only). The Katalog uses the
   diacritic-insensitive, typo-tolerant matcher from
   [`0063`](./0063-diacritic-insensitive-client-filtering.md), so „perp" finds
   „Pepř" there but not on Inventura. Inventura needs a bespoke filter (it
   AND-combines the name query with the toggle), so it never adopted the 0063
   `data-filter-*` hook and thus never got the fuzzy matching.

## Choice

### 1 — Toggle shows CRITICAL = empty + low, from the Katalog's source of truth

The single-branch toggle now marks a row `data-low="1"` when the product is in
the Katalog's **Prázdné OR Dochází** group at that branch. The view computes
membership from **`catalogue_stock_groups([branch])`** (`empty_rows` +
`low_rows`) — the one source of truth for the empty/low grouping per 0072 —
instead of `low_stock_rows()` alone. The `data-low` attribute name is unchanged
(only its meaning broadens); the toggle is **relabelled „Dochází / prázdné"**
with tooltip „Zobrazit jen kritické položky — prázdné i pod objednacím bodem".

### 2 — Bespoke filter reuses the 0063 fuzzy matcher

`base.html` exposes the 0063 filter internals as
**`window.kasiaRowFilter`** — `fold(s)`, `tokenize(s)`, and
`matches(tokens, folded, words)` (thin aliases of the existing `foldText` /
`matchesQuery`, no rename). Inventura's `applyFilter` uses them for the name
match, so it gets the exact same diacritic-insensitive, typo-tolerant behaviour
as the Katalog, then ANDs the result with the „Dochází / prázdné" toggle. A
defensive fallback to plain substring is kept if the global is somehow absent.

## Rationale

Both fixes make Inventura agree with the Katalog by **reusing the Katalog's own
logic** rather than duplicating a second definition:

- The critical set comes from `catalogue_stock_groups`, so „what the Inventura
  toggle hides" can never again drift from „what the Katalog calls Prázdné /
  Dochází". This is exactly the single-source-of-truth the design system already
  mandates for grouping (0072).
- The fuzzy match comes from the 0063 matcher, exposed once and reused, so there
  is no second copy of the fold/Levenshtein logic to keep in sync.

The `data-low` attribute is intentionally **not** renamed — only its meaning
widens — so no other consumer or test that keys on it breaks.

## Consequences

**Now:**
- `inventory/views/inventura.py`: `low_pks` computed from
  `catalogue_stock_groups([branch])` (empty + low); imports
  `catalogue_stock_groups`.
- `kasia/templates/base.html`: exposes `window.kasiaRowFilter`.
- `kasia/templates/inventory/inventura_edit.html`: `applyFilter` uses the shared
  matcher; toggle relabelled „Dochází / prázdné" + tooltip; page-help updated.
- `design-system.md`: 0063 § notes the `window.kasiaRowFilter` export; 0065 §
  notes the toggle now scopes to critical (empty + low) via
  `catalogue_stock_groups`, relabelled.
- Test: an empty product with threshold 0 is now flagged `data-low="1"` at its
  branch.

**Amends 0065:** the single-branch toggle is no longer „below reorder threshold
(from `low_stock_rows()`)" — it is „critical: empty + low (from
`catalogue_stock_groups`)".

**Not changed:** the cross-branch „Dochází zboží" (`dochazi`) roll-up still uses
`low_stock_rows()` (its own long-standing contract, 0057); this decision is
about the single-branch toggle only. The `data-filter-*` (0063) hook and its
matcher are unchanged — merely also exposed for reuse.

## Cross-references

- [`0065-inventura-sidebar-nav.md`](./0065-inventura-sidebar-nav.md) — the toggle this amends
- [`0063-diacritic-insensitive-client-filtering.md`](./0063-diacritic-insensitive-client-filtering.md) — the fuzzy matcher now reused
- [`0072-reorder-threshold-not-null.md`](./0072-reorder-threshold-not-null.md) — why empties (threshold 0) must count as critical
- [`design-system.md`](../../.claude/rules/design-system.md) — Katalog grouping is the single source of truth
