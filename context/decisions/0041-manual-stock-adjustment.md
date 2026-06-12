# 0041 — Manual stock adjustment via Movement, never raw UPDATE

**Date:** 2026-06-12
**Decider:** Matej (relaying Karolína/Petr operational reality)
**Status:** Active

## Context

Decision [`0040`](./0040-operator-crud-tiering.md) lists "Stock
direct edit" as a vlastník-only CRUD operation that must land in the
operator app. Matej's walkthrough feedback was explicit:

> "We need to be able to add a new surovina, change how many of it
> is on the branch, etc."

The naive implementation would be a form on `/katalog/<id>/upravit-stav/`
that issues an `UPDATE inventory_stock SET quantity = ?` and returns.
That bypasses every audit invariant the system has built so far.

Two existing decisions already constrain this:

- [`0012-inventura-via-correction.md`](./0012-inventura-via-correction.md)
  established that **inventura** (stocktake reconciliation) is
  performed by recording a movement with a "při inventuře" reason
  convention, not by overwriting Stock directly.
- [`0021-audit-hand-rolled.md`](./0021-audit-hand-rolled.md) +
  [`0035-audit-line-events.md`](./0035-audit-line-events.md) require
  every Stock-affecting change to be reflected in `MovementAudit`.

The new operator-facing affordance must respect both.

## Options considered

1. **Direct UPDATE on Stock with a Settings-style audit log.**
   New `StockAdjustmentLog` table. Rejected: introduces a parallel
   audit track distinct from `MovementAudit`; the auditor would have
   to read two tables to reconstruct a product's history.
2. **One synthetic `Movement` per adjustment (kind=prijem or vydej
   depending on direction).** Routes through `apply_movement`, lands
   in `MovementAudit` via the standard create path, surfaces in
   Historie automatically. **Chosen.**
3. **A new `kind=adjustment` Movement type.**
   Cleaner semantically, but introduces a third value to enum +
   migration + every downstream filter has to handle it. Rejected
   on YAGNI grounds — the existing prijem/výdej kinds + a marker on
   `Movement.note` (or a new `is_adjustment` flag) covers the need.

## Choice

**Option 2: each manual stock adjustment becomes a synthetic
Movement with a fixed note prefix.**

### Mechanics

When Karolína opens `/katalog/<id>/upravit-stav/` and changes
"Skladem v TYN" from `25.000` to `23.000` with reason
"inventura — vážil jsem 23 kg":

1. The view computes the delta: `target - current = -2.000` (= 2 kg
   shortfall).
2. The sign determines the Movement kind:
   - `delta > 0` → `Movement.Kind.PRIJEM` with a synthetic internal
     supplier (re-using the existing **Míchárna** internal pair per
     [`0039`](./0039-mixing-job-shape.md) would conflate concerns;
     a new `is_internal=True` *adjustment* counterparty is created
     lazily on first use).
   - `delta < 0` → `Movement.Kind.VYDEJ` with the synthetic
     adjustment customer.
   - `delta == 0` → noop, no movement written.
3. One `MovementLine` is created: the product + `abs(delta)`.
4. `Movement.note` is prefixed with `"[STAV] "` followed by the
   operator-supplied reason. The bracketed prefix lets dashboard /
   history queries surface manual adjustments separately.
5. `apply_movement` runs as normal — Stock is mutated, the Movement
   row is the audit-creation record, dodáks are not generated
   (adjustment counterparty has `is_internal=True`, same skip path
   as Míchárna per `apply_movement` in `inventory/services.py`).

### New counterparty seed (migration)

`inventory/0008_seed_adjustment_counterparty.py`:

- `Customer.objects.get_or_create(name="Inventura / ruční úprava",
  is_internal=True, defaults={"address": "interní úprava stavu"})`.
- `Supplier.objects.get_or_create(name="Inventura / ruční úprava",
  is_internal=True, defaults={"address": "interní úprava stavu"})`.

These are distinct from Míchárna (which is for míchání-job
consume/produce). Two separate internal pairs keep concerns separated
in Historie filters.

### Reason field

Free-text, required, persisted in `Movement.note` after the
`"[STAV] "` prefix. The standard Historie filter on `q` (note
icontains) finds them; a future Historie tabs split per H1/H2 in the
walkthrough feedback can add a "Inventura / úpravy stavu" tab that
filters on this prefix.

### Why not a separate kind

Future-compatibility: if shadow-run reveals operators want a
dedicated "inventura" workflow distinct from prijem/výdej, that's a
follow-up decision that supersedes this one. The current shape keeps
the Movement kind set at two (prijem, vydej) which keeps
`apply_movement`, audit, dodák, and history queries unchanged.

### Tier

Per [`0040`](./0040-operator-crud-tiering.md): **vlastník-only**.
Workers don't directly write Stock; if they need to correct a
movement (e.g. wrong quantity on a real příjem), they edit that
specific movement via screen 11, which already routes through
`MovementAudit`.

### Per-branch scoping

The form lets the operator pick the branch (vlastník sees all). The
target product + branch pair must exist in `Stock`; if not, a Stock
row is implicitly created on first adjustment (Stock.quantity
defaults to 0).

## Rationale

- **One audit story.** Every Stock delta lives in `MovementAudit`
  via the standard create path. Auditor never has to know about a
  second log.
- **Historie always shows reality.** Manual adjustments appear in
  Historie alongside real movements, just with the `[STAV]` prefix
  and the adjustment counterparty as protistrana. Karolína can
  search/filter the same way she does for everything else.
- **No new model, no new audit shape.** Re-uses Movement +
  MovementLine + MovementAudit + apply_movement. Smallest possible
  surface area.
- **Forward-compatible.** A dedicated `kind=adjustment` enum value
  or a separate `StockAdjustment` model can supersede this later
  without breaking existing rows — those would still parse as
  prijem/vydej movements with a [STAV] prefix.

## Consequences

### Code

- New `apply_stock_adjustment(...)` service in
  `inventory/services.py` that builds the synthetic Movement and
  delegates to `apply_movement`.
- New view `stock_adjust_edit(product, branch)` on the inventory
  views (vlastník-only).
- New migration seeding the "Inventura / ruční úprava" Customer +
  Supplier pair.
- New tests: positive delta → prijem; negative delta → výdej; zero
  delta → noop; obsluha 403; resulting movement appears in
  Historie with [STAV] prefix; resulting movement has
  `is_internal=True` counterparty so no dodák is generated.

### Dashboard / Historie

- `[STAV]` prefix becomes a soft sentinel for future filters /
  history-tab split (H2 in walkthrough feedback). No immediate
  template change beyond the prefix being visible in the existing
  history view.

### Forward references

- A future "Inventura" screen could surface these adjustments as
  their own list and provide bulk-correction tooling. Out of MVP.
- A future per-permission tiering (third tier in
  [`0040`](./0040-operator-crud-tiering.md)) could let
  branch-specific obsluha do small adjustments without vlastník.
  Not needed for the 6-active-user shadow run.
