# 0102 — Výdej allows the same product on multiple lines (sum it)

**Date:** 2026-08-20
**Decider:** Matej (from a branch-worker request; confirmed with Petr)
**Status:** Active

## Context

A branch worker asked that **výdej** (issue) let her add the **same spice on
multiple lines** and have the quantities sum. Her reason: one spice is physically
packaged in different sizes (e.g. 10 kg vs 5 kg) and she wants each package
recorded as its own line — even though the catalogue is **mass-only** (per
[`0028`](./0028-mass-only-no-packs.md)) and carries no packaging field.

Today the výdej form **blocks** picking the same product twice. That block is the
`refreshProductOptions()` client-side dedup that
[`0071`](./0071-prijem-dedup-products.md) moved out of the výdej-only block into an
always-run IIFE so it covered **both** movement forms. 0071's own reasoning was
mass-only-catalogue + consistency; the same reasoning does **not** hold for the
worker's package-size workflow, where two lines of one spice are the *intent*, not
an error.

Exploration confirmed the block is **purely cosmetic client-side JS** — the whole
server path already sums duplicates correctly:

- No DB / model / form / formset uniqueness constraint on `(movement, product)`
  (`MovementLine.Meta.constraints` has only `quantity_kg > 0`; the formsets have
  no `clean`).
- `_compute_overdraw` (`inventory/views/movements/vydej.py`) **aggregates
  requested qty per product** before comparing to stock (per
  [`0042`](./0042-overdraw-warning-card.md)).
- `apply_movement` (`inventory/services/movement.py`) deducts **per line**, so two
  lines of one product each deduct → the sum.
- The dodák has **no line-item model** — the PDF renders directly from
  `Movement.lines`, so duplicates already show as **two separate numbered rows**;
  `DodaciList.total_quantity_kg` sums all lines.
- The výdej live over-stock JS **already** sums per product
  (`sumByProduct[...] += qty`), so the browser warning stays duplicate-safe.
- `movement_edit.html` has **no dedup** already, so editing a výdej already allows
  duplicates — nothing changes there.

## Options considered

1. **Leave the dedup on výdej (repeats blocked).** Zero work, but it refuses a
   legitimate, requested workflow that the server already handles arithmetically.
2. **Merge duplicate lines into one on the dodák.** A server change to a document
   the owner is happy with — and it would erase the per-package detail the worker
   wants to see. Rejected.
3. **Stop running the dedup IIFE on výdej; keep it on příjem.** The same spice can
   be listed on several výdej lines and the server sums it; the dodák shows one
   row per line. **Chosen.**

## Choice

**Option 3.** The `refreshProductOptions()` client-side dedup now runs on
**příjem only**. Výdej allows the same product on multiple lines; the server sums
them (overdraw aggregation 0042, per-line stock deduction) and the dodák renders
one row per line, `total_quantity_kg` summing all rows.

Mechanism: a template include flag **`allow_duplicate_products`** on the shared
`inventory/_movement_form_lines.html` partial, parallel to `show_stock_warn`. The
dedup IIFE is wrapped in `{% if not allow_duplicate_products %}`. `vydej_form.html`
includes with `allow_duplicate_products=True`; `prijem_form.html` passes it
explicitly `False` (self-documenting — an undefined flag is already falsy). No
view/model/service/form change.

This **supersedes in part** [`0071`](./0071-prijem-dedup-products.md): 0071's
"runs on both movement forms" becomes "runs on příjem only".

## Rationale

- **The server already sums correctly.** The dedup was cosmetic; removing it on
  výdej introduces no data risk — overdraw aggregation and per-line deduction both
  handle duplicates, and the dodák already renders per line.
- **Real requested workflow.** A worker wants to record physical package sizes as
  separate lines. Mass-only means the catalogue can't model packaging, so
  multi-line entry is the pragmatic way to keep that detail visible on the dodák.
- **Příjem stays blocked (0071 intent preserved).** Receiving the same spice twice
  on one doklad is still far more often an error; only výdej opts out.

## Date & by-whom

2026-08-20 — Matej (branch-worker request; confirmed with Petr that the dodák
shows two separate rows, no merging, and the scope is výdej only).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Multi-line entry of the same product on one výdej doklad (e.g. different package
  sizes), summed by the server and shown as one row per line on the dodák.
- The dedup IIFE in `kasia/templates/inventory/_movement_form_lines.html` is
  wrapped in `{% if not allow_duplicate_products %}`; `vydej_form.html` sets the
  flag `True`, `prijem_form.html` `False`.
- `.claude/rules/design-system.md` records the flag + the příjem-only scope.

**No change to:**

- Server, models, services, or forms — the change is a pure template include flag.
- Příjem — its 0071 dedup is unchanged (`allow_duplicate_products=False`).
- The výdej over-stock check (`show_stock_warn`) — it already aggregates per
  product, so the live warning stays correct with duplicates.
- `movement_edit.html` — it already allowed duplicates (no dedup).

**Forecloses (without follow-on decision):**

- Renaming the `allow_duplicate_products` include flag is a new decision.
