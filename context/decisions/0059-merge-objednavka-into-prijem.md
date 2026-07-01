# 0059 — Merge objednávka into příjem (planned goods receipt)

**Date:** 2026-07-01
**Decider:** Matej (relaying Petr's ask)
**Status:** Active
**Relates to / supersedes in part:**
- [`0040-operator-crud-scope.md`](./0040-operator-crud-scope.md) — planned
  receipts follow the all-logged-in-users tier (create + confirm + cancel).
- [`0041-manual-stock-adjustment.md`](./0041-manual-stock-adjustment.md) —
  the inventura date column still creates planned inbound; now a Movement.
- [`0043-reorder-threshold.md`](./0043-reorder-threshold.md) — the
  `objednací bod` that makes a (product, branch) pair show in "Dochází zboží".
- [`0044-reservations-planned-states.md`](./0044-reservations-planned-states.md)
  — reservations are informational, non-stock-gating; the same invariant
  now governs planned příjem.
- [`0053-stock-row-is-branch-carry.md`](./0053-stock-row-is-branch-carry.md)
  — low-stock membership rule is unchanged.
- **[`0057-planned-orders-objednavky.md`](./0057-planned-orders-objednavky.md)
  — superseded in part.** The `PlannedOrder` model, the `/sklad/objednavky/`
  write surface, and its nav entry are retired; planned inbound is now a
  `Movement` with `status=planned`.

## Context

The standalone objednávka system shipped in 0057 (model `PlannedOrder`,
page `/sklad/objednavky/`) is confusing next to *příjem*: both record an
inbound delivery of goods to a branch. Worse, objednávka is **one product at
a time**, while *příjem* is already multi-line. Having two near-identical
concepts costs the ~6 users clarity for no benefit.

## Options considered

- **Keep both, cross-link them.** Rejected: two models, two pages, two mental
  models for the same act. Does not remove the confusion.
- **Add a second `PlannedReceipt` model mirroring Movement.** Rejected: a
  parallel multi-line model duplicates `Movement`/`MovementLine`, the stock
  write path, and the history surface. Violates
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md).
- **Unify into the existing multi-line `Movement`.** Chosen (below).

## Choice

Unify planned inbound into the existing `Movement` via a new **`status`**
(`done` / `planned`) plus a nullable **`expected_on`** (*očekávaný příjezd*).
No second model.

- The **příjem create form gains one optional "Příjezd" date**. Empty, today,
  or a past date ⇒ an ordinary DONE příjem that hits stock immediately
  (today's behaviour). A **future date** ⇒ a **PLANNED** multi-line receipt
  that does **not** touch stock until its arrival is confirmed.
- A PLANNED Movement stores `expected_on` = promised arrival; `date_issued` =
  today (keeps the not-null field + `-date_issued,-id` ordering valid). On
  confirm, `date_issued` is rewritten to the actual arrival date.
- **Confirm-on-arrival is manual** (no scheduler, per 0057 rationale) via
  `confirm_planned_receipt`. Each line's quantity is editable to what actually
  arrived; a line set to 0 is dropped; the **whole receipt** is then marked
  DONE and applied to stock. **Partial arrivals = adjust & confirm whole** — no
  split/remainder. Negative stock is checked at confirm time, not plan time.
- **Access: all logged-in users** create, confirm, and cancel — same tier as
  planned transfers (0040 + 0044). No vlastník gate on the príjem paths.
- **Retire the objednávka write surface.** The `/sklad/objednavky/` routes,
  page, form, and nav entry are removed. Planned receipts surface in
  **Historie under a new "Plánované" tab** with **Přijmout** (confirm) +
  **Zrušit** actions. The `PlannedOrder` model class + migrations 0014/0015 are
  **kept read-only** (historical audit); its admin loses add permission. Open
  PLANNED `PlannedOrder` rows are migrated to PLANNED Movements (migration
  0017) and marked cancelled at source.

## Preserved invariant (from 0057)

Planned inbound remains **informational only** — it must never change
`effective_kg` / `reserved_kg` / low-stock membership or the deficit-DESC
sort. The low-stock **"Objednáno"** overlay now aggregates **PLANNED příjem
Movement lines** (per product+branch, `Sum(quantity_kg)` + `Min(expected_on)`)
instead of `PlannedOrder`, but stays badge-only. The service `low_stock_rows()`
sort and membership are untouched; the owner-view sink-to-bottom stays in the
view.

## Constraints

- The Movement counterparty CHECK is replaced with a three-branch condition so
  a DONE příjem still requires a supplier (no regression), a výdej still
  requires a customer, and a PLANNED příjem may omit the supplier. A second
  CHECK enforces `planned ⇒ příjem`. PLANNED príjem still **requires**
  `expected_on` (enforced in the príjem-planned view path + `PrijemForm`), so
  the overlay + badge always have a date. DONE rows keep `expected_on = NULL`.
- Every "what happened" surface (Historie all/příjmy/výdeje/inventura/editováno
  tabs + counts, home / branch / product-detail recent-movement panels, the
  under-form recent panel) filters `status=done`. PLANNED rows live only in the
  new Plánované tab. `Stock`-aggregating dashboards/KPIs are unaffected (PLANNED
  never touched stock).
- The seeded internal **"Objednávka"** supplier (migration 0015) becomes the
  confirm-time fallback counterparty when no real supplier is chosen.

## Czech ↔ code mapping

- *objednávka* is now a **plánovaný příjem** — a `Movement` with
  `status=planned, kind=prijem` — not a separate model. UI verb on confirm:
  **Přijmout**; cancel: **Zrušit**. Expected arrival is **očekávaný příjezd**
  (`Movement.expected_on`). See [`domain-glossary.md`](../domain-glossary.md).

## Consequences

- One inbound concept, one multi-line surface, one stock write path.
  `apply_movement` gains a single early PLANNED branch (skip stock + dodák +
  e-mail); every other caller passes the default DONE status and is unaffected.
- A new manual confirm service (`confirm_planned_receipt`) is the only path
  that turns a PLANNED receipt into stock; it is idempotent-guarded
  (`status==planned` at entry).
- `PlannedOrder` becomes a frozen historical table. A future cleanup could drop
  it once the shadow-run window closes; not dropped now to preserve the 0057
  audit trail.
- The daily low-stock digest (0045) and the panel continue to agree on
  contents — the overlay re-source is presentation-only.
