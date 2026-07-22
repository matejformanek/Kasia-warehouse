# 0089 — Per-mixture default batch size (`Product.default_batch_kg`)

**Date:** 2026-07-22
**Decider:** Matej (standing in for Petr) — alongside the real-recipe entry batch
**Status:** Active

## Context

The 3 real „Česneková drť" receptury (entered via the ORM per
[`0088`](./0088-recipe-component-notes-and-untracked-ingredients.md)) each have a
canonical batch size that is used in ~99 % of mixes — **337 / 339.1 / 320 kg**.
Petr/Matej want that number **prefilled** wherever a mix starts, so the operator
rarely retypes it:

- on the **míchání** screen (`mixing_job_create`), the „Cílové množství (kg)"
  input (`#id_target_qty`), and
- on the **mixture product-detail** page, the „Spočítat dávku" scaler + the
  one-click „Zahájit míchání" that lands on míchání already prefilled.

There is nowhere to persist this today. `Product.notes` is free text (the
„Pracovní postup"); overloading it would be unparseable. A number field is the
faithful model.

## Options considered

1. **Overload `Product.notes` / a magic first line.** Rejected: `notes` is
   human-readable free text (recipe postup); parsing a number out of it is
   fragile and would break the moment Petr edits the prose.
2. **A separate per-recipe config table (`RecipeConfig`).** Rejected: enormous
   for one number. One mixture = one batch size; a 1:1 side table is a new model,
   a new form, a new join, for a scalar that belongs on the product row.
3. **A new `Product.default_batch_kg` decimal field (default `0`, `0` = unset),
   editable on the vlastník product form + admin/ORM.** **Chosen** — copies the
   exact not-null-with-default + `0`-means-unset pattern
   [`0072`](./0072-reorder-threshold-not-null.md) established for
   `reorder_threshold_kg`, so the migration never prompts and prefill logic is a
   simple `> 0` gate.

## Choice

Add **`Product.default_batch_kg = DecimalField(max_digits=10, decimal_places=3,
null=False, blank=True, default=Decimal("0.000"))`** (migration
`inventory/migrations/0027_product_default_batch_kg.py`, DB default so the
non-interactive CI/SSH `migrate` never prompts — same guarantee as 0088's 0026).

- **`0` means "no default set".** All prefill logic is gated on `> 0`, so raw
  spices and mixtures without a set batch fall back to today's behaviour (blank
  míchání input / scaler `"10"`). Meaningful only for mixtures; harmless on raws.
- **No `CheckConstraint`** — matching its sibling `reorder_threshold_kg` (which
  has none). A stray negative is harmless: prefill reads `> 0`, so it presents as
  unset.
- **Editable on `ProductForm` only for vlastník** — reuses the existing
  `can_edit_threshold` kwarg (the field is popped for non-vlastník, exactly like
  `reorder_threshold_kg`). Always settable via admin / ORM. Workers don't see it.
- **On the míchání screen**, switching the recipe dropdown **overwrites** the
  total with the newly-selected recipe's default when that default is `> 0`;
  otherwise the field is left untouched. Implemented as a `#mixture-defaults`
  `json_script` blob + a capture-phase `change` listener on `#id_mixture` (no
  synthetic event dispatch — the select's existing htmx `change` preview request
  already serialises the freshly-set qty), plus a **GET-only** server prefill of
  `target_qty_value` so a plain `?mixture=<pk>` link lands prefilled too.

Czech label: **„Výchozí dávka (kg)"**.

## Rationale

- **Copies a proven pattern.** `reorder_threshold_kg` already solved
  not-null-with-default + `0`-as-unset + vlastník-only-form-gating (0072). Reusing
  it keeps the migration non-interactive, the coercion trivial, and the review
  surface small.
- **Rides existing seams.** Product-detail already links `?mixture=<pk>` and
  threads `&target_qty=` (per [`0060`](./0060-michani-immediate-only.md)); the
  míchání view already echoes `?mixture/?branch/?target_qty`. The prefill is
  wiring on top of those, no new endpoint.
- **Right-sized.** ~6 users, one scalar per mixture. No new model, no new screen.

## Date & by-whom

2026-07-22 — Matej (standing in for Petr), alongside the real-recipe entry batch.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Prefilling the batch size on both mix-start surfaces.
- Migration `inventory/migrations/0027_product_default_batch_kg.py` (DB-defaulted).
- Setting `default_batch_kg` on the 3 real mixtures in the same ORM entry batch
  (337 / 339.1 / 320).

**Commits us to:**

- Keeping the prefill gated on `> 0`. Renaming the `#mixture-defaults`
  `json_script` hook or the prefill gating is a **new decision** (recorded in
  `.claude/rules/design-system.md`).

**Supersedes nothing.** Purely additive — it changes no prior decision. It builds
on 0072 (the field pattern), 0060 (the míchání prefill seam), and 0088 (the
immediately-prior additive `Product`-field precedent).
