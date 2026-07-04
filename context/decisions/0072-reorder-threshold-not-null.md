# 0072 — Reorder threshold is not-null, default 0 (supersedes part of 0043)

**Date:** 2026-07-04
**Decider:** Matej (from the live walkthrough feedback)
**Status:** Active

## Context

During the live walkthrough, an operator logged in-app feedback (12:06) that a
product's **reorder threshold** should default to **0** rather than being left
unset. Under [`0043`](./0043-reorder-threshold.md) the field is nullable and
`None` means "no threshold set, do not alert" — a deliberate distinction from
`0`, which meant "alert at literal empty". In practice that `None` semantics
produced a surprise Matej confirmed in the walkthrough: **a product sitting at
0 kg with no threshold set does not show up as empty** — the Katalog "Prázdné"
(empty) group gates membership on `threshold is not None`, so an un-configured,
genuinely-empty product silently drops out of the red group.

The intent Matej confirmed: **a product at 0 kg should *always* show in the red
"Prázdné" group.** Empty is empty, regardless of whether anyone typed a
threshold. The cleanest way to get there is to stop treating "unset" as a
distinct state — make the threshold always a real number, defaulting to 0.

## Options considered

1. **Keep `None`, only change the Katalog gate.** Drop the
   `threshold is not None` check in `_is_empty` but leave the field nullable.
   Works for the empty-group symptom, but leaves the confusing tri-state
   (`None` / `0` / `>0`) in the schema, forms, and `low_stock_rows()`. Half a
   fix.
2. **Schema change: not-null, default 0, backfill NULLs → 0.** Make
   `reorder_threshold_kg` always a number; a new product starts at 0; existing
   NULLs become 0. Collapses the tri-state to a clean "every product has a
   threshold". **Chosen.**

## Choice

**Option 2: `Product.reorder_threshold_kg` becomes `null=False, default=0`**
(`Decimal("0.000")`), with a data migration backfilling existing `NULL`s to
`0`. `blank=True` stays so the form field is optional; a blank submit coerces to
`0` (`ProductForm.clean_reorder_threshold_kg`). The Katalog `_is_empty` gate
drops its `threshold is not None` condition — a product at **effective ≤ 0**
always groups as **"Prázdné"**.

This **supersedes the `None`-vs-`0` semantics under § Choice of
[`0043`](./0043-reorder-threshold.md)**. The rest of 0043 — the per-product
default **plus** per-branch `StockThresholdOverride`, the `threshold_for` /
`effective_kg` helpers, the vlastník-only tier, the computed-on-read
effective-stock formula — stands.

## Rationale

- **Empty must read as empty.** The walkthrough showed the `None`-excludes-from-
  Prázdné behaviour is wrong for the operator: a spice at 0 kg is empty whether
  or not a threshold was ever typed. Making 0 the floor guarantees it lands in
  the red group.
- **Tri-state was the source of the bug.** `None` / `0` / `>0` forced every
  consumer (Katalog gate, form, e-mail) to special-case "unset". A non-null
  default removes the special case at the root rather than patching one symptom.
- **0043's architecture is fine.** Only the null semantics were wrong; the
  per-product-plus-override shape and the read-time effective formula are
  unaffected, so this is a partial supersede, not a rewrite.
- **Backfill is safe at this scale.** ~30 products; a one-shot `NULL → 0`
  RunPython before the `AlterField` to not-null is trivial and reversible
  (reverse = no-op).

## Date & by-whom

2026-07-04 — Matej (from the live walkthrough feedback).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Migration `inventory/migrations/0018_reorder_threshold_not_null.py`: a
  `RunPython` backfill (`reorder_threshold_kg__isnull=True → 0.000`, reverse
  no-op) **before** the `AlterField` to `null=False, default=Decimal("0.000")`
  (Postgres won't backfill from a default on `AlterField`).
- `ProductForm.clean_reorder_threshold_kg` coerces empty → `Decimal("0.000")`
  (Django's `construct_instance` doesn't apply the model default for a
  present-but-empty field, so a blank submit would otherwise `IntegrityError`).
- `catalogue._is_empty` drops the `threshold is not None` gate → `effective ≤ 0`
  always groups as "Prázdné". Ties into
  [`0064`](./0064-grouped-catalogue-client-filter.md)'s grouped Katalog.

**Membership shifts (intended, not regressions):**

- Katalog/dashboard: products at **effective ≤ 0** now group as **"Prázdné"**,
  bumping the Vyprodáno KPI — this is the goal (empty is empty).
- `low_stock_rows()` membership shifts: products previously excluded by a `None`
  threshold (including over-reserved products at effective < 0) now surface.
  This flows to the daily low-stock e-mail too, **but the mailing behaviour is
  explicitly the concern of a separate session — 0072 does not redesign
  `send_low_stock_summary` or its membership rule.**

**Forecloses (without follow-on decision):**

- The "seasonal products deliberately let to zero, don't alert" case that 0043
  reserved `None` for. If Petr wants a product excluded from alerts again, a new
  decision reintroduces an explicit "untracked" flag (not a nullable threshold).

**No change to:**

- The per-branch `StockThresholdOverride` model, `threshold_for` /
  `effective_kg`, the vlastník-only tier, or the computed-on-read formula — all
  from 0043, all still current.
