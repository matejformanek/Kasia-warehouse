# 0091 — „Prázdný na" chip lists branches empty at effective ≤ 0, independent of threshold

**Date:** 2026-07-22
**Decider:** Matej (standing in for Petr)
**Status:** Active — refines the display side of
[`0072`](./0072-reorder-threshold-not-null.md) /
[`0064`](./0064-grouped-catalogue-client-filter.md)

## Context

On the grouped Katalog (and the vlastník/obsluha Přehled, same partial
`_catalogue_group.html`), the red „Prázdné" group has a per-branch column
(„Prázdný na") meant to show **where** the product is empty. It was fed by
`row.low_branches`, computed in `_catalogue_rows` as the branches where
`effective < threshold_for(product, branch)`.

Per [`0072`](./0072-reorder-threshold-not-null.md) the reorder threshold is now
always set with a **default of 0**, and the „Prázdné" group keys on
**`effective ≤ 0` alone** (threshold no longer gates empty). But the branch chip
never followed suit: for a genuinely-empty product at the default threshold 0,
`effective (0) < threshold (0)` is **false**, so `low_branches` is empty and the
„Prázdný na" column renders **blank** — even though the product is plainly empty
on that branch. The freshly-entered garlic products (TYN at 0 kg, threshold 0)
hit this: all sit correctly in the red group but show no branch, so the operator
can't tell where the gap is.

## Options considered

1. **Set every product's threshold to a positive number.** Rejected — abuses the
   threshold (an alert boundary) to drive an unrelated display, and contradicts
   0072's "default 0 = empty shows in red without a threshold".
2. **Reuse `low_branches` for the empty column but change its rule to `≤ 0`.**
   Rejected — `low_branches` also feeds the „Dochází na" column of the *low*
   group, which correctly means "below a (nonzero) threshold". Overloading one
   list for two different meanings would mislabel low branches.
3. **Add a separate `empty_branches` list (branches carried where
   `effective ≤ 0`) and render it in the „Prázdný na" column.** **Chosen.** The
   empty column now mirrors the group's own `effective ≤ 0` rule; the low
   column keeps `low_branches` unchanged.

## Choice

In `_catalogue_rows` compute, per row, **`empty_branches`** = the carried
branches (a Stock row exists, per 0053) whose `effective ≤ 0`. Render it in the
„Prázdný na" column of `_catalogue_group.html` (the `branch_kind == "empty"`
case), keeping the `.empty-branch` chip style. The „Dochází na" (low) column and
`low_branches` / `is_low` / group membership are **unchanged**.

## Rationale

- **Matches the group's own rule.** The empty group keys on `effective ≤ 0`; its
  branch chip now does too — no more blank column for threshold-0 empties.
- **No overload.** `low_branches` keeps its single meaning (below a nonzero
  threshold) for the low group; a separate list avoids mislabeling.
- **Display-only, contained.** No change to grouping, KPIs, alerts, or
  `low_stock_rows`. One list added in the shared view helper + one template line.

## Date & by-whom

2026-07-22 — Matej (standing in for Petr).

## Consequences

**Unblocks:**

- The „Prázdný na" column now shows the branch(es) for genuinely-empty products
  (the garlic data shows „TYN"), across Katalog + both Přehled surfaces (shared
  `_catalogue_group.html`).

**Commits us to:**

- Keeping `empty_branches` (eff ≤ 0) and `low_branches` (eff < nonzero threshold)
  as *separate* lists. Merging them again is a new decision. Recorded in
  `.claude/rules/design-system.md`.

**No change to:**

- Group membership / KPIs (`_is_empty` / `_is_low` / `catalogue_stock_groups`),
  the low („Dochází na") column, `low_stock_rows`, or alerts.
- 0072's empty rule or the threshold model.
