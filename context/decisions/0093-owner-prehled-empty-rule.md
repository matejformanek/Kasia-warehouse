# 0093 — Owner Přehled „Vyprodáno" counts the real empties (broader `_below_alert` rule)

**Date:** 2026-07-22
**Decider:** Matej (standing in for Petr)
**Status:** Active — refines the attention-bucket source of the owner Přehled,
building on [`0072`](./0072-reorder-threshold-not-null.md) +
[`0074`](./0074-event-driven-low-stock-alert.md)

## Context

The owner Přehled (`home()`) header KPI „Vyprodáno" (and the per-branch empty
lists) is sourced from `low_stock_rows()` (`inventory/services/reorder.py`),
whose membership gate is the bare **`effective < threshold`**. Per
[`0072`](./0072-reorder-threshold-not-null.md) the default `reorder_threshold_kg`
is **0**, so a carried (product, branch) pair at exactly **0 kg** evaluates
`0 < 0 == False` and never enters the list.

The Katalog „Prázdné" group, by contrast, keys on `effective ≤ 0` alone
(threshold-independent, `catalogue.py:_is_empty`). The two disagree: confirmed
against prod, **67** carried pairs (58 distinct products — spices *and* směsi)
are actually at `effective ≤ 0`, but the Přehled showed only **19** (SEZ 11 ·
TYN 8), silently dropping the **48** empty-at-threshold-0 pairs. The owner sees
„19" where Katalog says „58" and can't trust the number.

The codebase already carries the correct broader rule —
`_below_alert(effective, threshold)` (`reorder.py`, per
[`0074`](./0074-event-driven-low-stock-alert.md)), the union of the Katalog
„Prázdné" + „Dochází" groups — but `low_stock_rows()` never adopted it, and the
inventura „Dochází zboží" roll-up (0057 contract) deliberately wants the *narrow*
rule.

## Options considered

1. **Make `low_stock_rows()` always use `_below_alert`.** Rejected — it would
   also broaden the inventura „Dochází zboží" roll-up, which is a separate 0057
   contract that must stay `effective < threshold`.
2. **Compute the owner empties from a fresh `catalogue_stock_groups` call.**
   Rejected — duplicates the per-branch + Objednáno-split bucketing the Přehled
   already does over `low_stock_rows`, and loses the PLANNED-order overlay.
3. **Add an opt-in `include_empty` flag to `low_stock_rows`, gated on
   `_below_alert` when set; owner Přehled passes `include_empty=True`.**
   **Chosen.** One caller broadens; every other caller (inventura roll-up, tests)
   is untouched.

## Choice

`low_stock_rows(*, include_empty: bool = False)`:

- `include_empty=False` (default): keep `effective < threshold` — inventura
  „Dochází zboží" roll-up + all existing callers unchanged.
- `include_empty=True`: gate on the existing `_below_alert(effective, threshold)`
  helper (the Katalog Prázdné + Dochází union). Empties at the default threshold
  0 now enter the list; their `deficit` is `0` (Decimal, sorts last).

`home()` calls `low_stock_rows(include_empty=True)`. The existing bucketing
(`ordered_kg is not None → ordered`, `elif effective ≤ 0 → empty`, `else → low`)
routes the added rows to **empty** (or **ordered** if they carry an open PLANNED
příjem). Per-branch granularity + the Objednáno split are retained.

## Rationale

- **The number matches Katalog.** „Vyprodáno" now equals the real carried-pairs
  at `effective ≤ 0` (minus those with an open order, which sit under Objednáno).
- **Reuses the existing helper.** No new rule — `_below_alert` already is the
  „Prázdné + Dochází" boundary (0074); the change is only *where* it applies.
- **Contained + opt-in.** The inventura roll-up and every existing test keep the
  narrow rule; only the owner Přehled opts in.

## Date & by-whom

2026-07-22 — Matej (standing in for Petr).

## Consequences

**Unblocks:**

- The owner Přehled „Vyprodáno" KPI + per-branch empty lists count the true
  empties (the ~48 previously-dropped threshold-0 pairs now appear).

**Commits us to:**

- Keeping the broadening **opt-in** (`include_empty`). The inventura „Dochází
  zboží" roll-up stays on the narrow `effective < threshold` (0057). Recorded in
  `.claude/rules/design-system.md` so a future agent doesn't "fix" the owner home
  back to the narrow rule.

**No change to:**

- The threshold model (0072), the alert crossing logic (0074), the inventura
  roll-up, or the branch-dashboard groups (those already come from
  `catalogue_stock_groups`).
