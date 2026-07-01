# 0057 — Objednávky: planned inbound orders from the low-stock panel

> **Superseded in part by 0059** — the `PlannedOrder` model, the
> `/sklad/objednavky/` write surface, and its nav entry are retired; planned
> inbound is now a `Movement` with `status=planned`. The informational-only
> invariant below is preserved.

**Date:** 2026-06-30
**Decider:** Matej (relaying Petr's ask)
**Status:** Active
**Relates to:**
- [`0040-operator-crud-scope.md`](./0040-operator-crud-scope.md) — all-users
  CRUD tier (objednávky follow planned-transfer access, not vlastník-only).
- [`0041-manual-stock-adjustment.md`](./0041-manual-stock-adjustment.md) —
  the `Upravit stav` action reuses `apply_stock_adjustment`; no new logic.
- [`0043-reorder-threshold.md`](./0043-reorder-threshold.md) — the
  `objednací bod` that makes a (product, branch) pair show in "Dochází zboží".
- [`0044-reservations-planned-states.md`](./0044-reservations-planned-states.md)
  — `PlannedTransfer` is the structural model `PlannedOrder` mirrors;
  reservations are informational, not stock-gating.
- [`0053-stock-row-is-branch-carry.md`](./0053-stock-row-is-branch-carry.md)
  — low-stock membership rule is unchanged.

## Context

The owner dashboard (screen 02) shows a **Dochází zboží** panel listing every
(product, branch) pair below its `objednací bod` (per 0043). It is the screen
Petr looks at most. Today it is **read-only** — he can see what is low but
cannot act on it from there.

Petr asked for each low row to become actionable with three choices:

1. **Ponechat** — keep as is. The null action; he simply does not touch the row.
2. **Upravit stav** — correct the current sklad amount (reality differs, or he
   just received something). This is exactly the existing manual stock
   correction (0041), so it reuses that page — no new logic.
3. **Objednat** — record a *planned order* ("objednávka") with a quantity and an
   expected arrival date. The order is **confirmed on arrival** by anyone logged
   in, writing one příjem that adds the received kg to that branch's sklad.

## Options considered

- **Auto-confirm via scheduler/cron on the expected date.** Rejected: deliveries
  slip, the quantity that arrives often differs from what was ordered, and a
  background scheduler is exactly the kind of moving part
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
  tells us to avoid for ~6 users. **Manual confirm** instead — anyone logged in
  presses "Přijmout", adjusting the received amount first if needed.
- **Make orders reduce the deficit / count as incoming stock.** Rejected: that
  reopens 0043 + 0044, which deliberately kept reservations *informational* and
  non-blocking. An order that hasn't physically arrived must not silently mask a
  low-stock alert. **Deficit math is unchanged**; the order surfaces only as a
  badge and sinks the row to the bottom of the panel.
- **Hide an ordered row from the panel entirely.** Rejected: it would diverge
  the panel from the daily `mail_low_stock_summary` digest (0045), which has no
  notion of orders. The row stays listed; only its *presentation* changes.

## Choice

Add a new model **`PlannedOrder`** ("objednávka"), modeled on `PlannedTransfer`
(0044):

- `product`, `branch` (arrival branch), optional `supplier`, `quantity_kg`
  (ordered), `received_qty` (actual, set on confirm), `expected_on`
  (*očekávaný příjezd*), `state` ∈ {`planned` "objednáno", `received` "přijato",
  `cancelled` "zrušeno"}, `notes`, `created_by`, `received_movement`.
- **PLANNED orders are informational only.** `reserved_kg`, `effective_kg`,
  low-stock membership, and the deficit are **unchanged**. The order appears as
  an `Objednáno: X kg, příjezd DD. MM.` badge on the low row, and the owner view
  sinks ordered rows below not-yet-handled ones. Membership + the service-level
  deficit-DESC sort are untouched, so the panel and the digest still agree on
  *contents*.
- **Confirm-on-arrival is manual.** `receive_planned_order` writes **one příjem**
  via `apply_movement` (the established single path for every stock delta),
  flips state to RECEIVED, and records `received_qty` + `received_movement`.
  `quantity_kg` (the ordered amount) is left intact so planned-vs-actual stays
  auditable. No scheduler, no cron.
- **Supplier is optional.** If set, the arrival příjem is a real receipt from
  that supplier. If not, it uses a seeded internal **"Objednávka"** counterparty
  (`is_internal=True`), exactly like the "Inventura / ruční úprava" supplier
  (0041). PRIJEM never issues a dodák or e-mail (that path is výdej-only), so
  either counterparty is fine.
- **Access: all logged-in users** for the Objednávky page itself (CRUD +
  receive follow the planned-transfer tier per 0040 + 0044). The order-creation
  surface is **folded into inventura** (vlastník-only, because inventura does
  stock corrections per 0041).

### How it surfaces (UX) — folded into inventura

The "Dochází zboží" panel stays a read-only list (with an `Objednáno` badge on
rows that already have an open order, sunk to the bottom). It gains a single
owner-only **Opravit →** button that opens **inventura** on a new cross-branch
filter.

The inventura editor (`/sklad/katalog/inventura/<code>/`) is extended two ways:

1. **Two new cross-branch options** in the branch picker (alongside TYN / SEZ),
   reached as reserved codes:
   - `dochazi` ("Dochází zboží") — only below-threshold rows, across all
     branches (one row per product+branch, fields blank by default). The
     dashboard **Upravit →** button opens this.
   - `vse` ("Vše") — every active product × every active branch, prefilled with
     current stock. The katalog inventura button (always shown for vlastník)
     opens `vse` when no branch is selected, or that branch's inventura when one
     is. Rows that already have an open objednávka show it inline with the full
     **příjezd date (incl. year)** plus **upravit / zrušit** controls (the cancel
     posts an out-of-form `<form>` referenced by the button's `form=` attribute,
     so the single big inventura form is never nested; both carry a `next` back
     to the screen).
2. **An optional "Příjezd" date column on every inventura row** (per-branch and
   the dochazi view alike). The single value field is reinterpreted by whether
   a date is set:
   - **date empty** → the value is the *absolute new stock level*; a non-zero
     delta becomes one `[STAV]` adjustment (shared batch reason, exactly as
     inventura already worked).
   - **date set** → the value is the *ordered amount* (kg, not a new level —
     stated on-screen); a PLANNED objednávka is created with that expected
     arrival date, no stock change now.

One **Uložit vše** commits the mix; the reason field is required only when at
least one immediate adjustment is present. This replaces an earlier
per-row-action-links design (and a short-lived standalone resolve screen) —
folding into inventura reuses the editor Petr already walks row-by-row.
Confirming the *arrival* of an order still happens on the Objednávky page
(anyone logged in). Hidden-id tampering is moot: the view iterates the
server-side row set (active products for a branch, or `low_stock_rows()` for
`dochazi`) and reads each row's posted fields by name.

## Czech ↔ code mapping

- Model `PlannedOrder`; UI verb **Objednat**, status **Objednáno** / **Přijato**
  / **Zrušeno**; glossary headword **objednávka** (see
  [`domain-glossary.md`](../domain-glossary.md) § Movements). Expected arrival is
  **očekávaný příjezd** (`expected_on`).

## Consequences

- Commits us to a second informational planned-state model alongside
  `PlannedTransfer`. The two share shape but not counterparty semantics
  (transfer = `is_internal=False` so a dodák fires; order = optional real
  supplier or internal "Objednávka", PRIJEM-only so no dodák either way).
- The low-stock panel becomes interactive but its *contents* and the service
  `low_stock_rows()` sort are deliberately frozen — the sink-to-bottom reorder
  happens in the owner `home` view, not in the service, so the digest e-mail and
  `test_low_stock_rows_sorted_by_deficit` stay correct.
- A new seeded internal Supplier "Objednávka" joins the Míchárna / Inventura /
  Převod counterparties — four separate internal pairs, kept distinct so a
  future Historie filter can split each.
- Receiving is idempotent-guarded: only a PLANNED order can be received or
  cancelled; `received_qty` must be > 0.
