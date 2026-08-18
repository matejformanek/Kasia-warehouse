# 0101 — Míchání „Smazat": hard-delete a completed dávka, returning stock

**Date & by-whom:** 2026-08-18 — Matej (owner-confirmed: hard delete, fully gone)

**Status:** Active

## Context

[`0100`](./0100-michani-single-quantity-and-unified-edit.md) made míchání a
single „Namícháno" quantity with a unified edit on the DONE dávka detail. The
missing operation is **removal**: an operator who recorded a míchání by mistake
(wrong směs, wrong branch, a duplicate of the Friday reconciliation) wants to
**delete the record and get the stock back** — the ingredients returned and the
produced směs removed.

A míchání is a **self-contained internal operation**: its consume movement is a
*výdej* to the internal *Míchárna* odběratel and its produce movement is a
*příjem* from the internal *Míchárna* dodavatel (per 0039). It has **no dodací
list, no external counterparty, no e-mail** — so unwinding it leaves nothing
external dangling.

## Options considered

- **Audited storno (mark CANCELLED).** Reverse stock via an audited
  `edit_movement` correction and set `state = cancelled` with a reason; the row
  stays in the list as „zrušeno" and the reversal shows in Historie. Consistent
  with how every other stock change is audited; nothing is truly erased.
- **Hard delete.** Reverse stock, then permanently delete the `MixingJob` (+
  its lines) **and** its two internal movements (+ their audit rows) — as if the
  míchání never happened. Chosen.

## Choice

**„Smazat" on a DONE dávka hard-deletes it.** A new service
`delete_completed_mixing_job(*, mixing_job, user)`:

1. Guards `state == DONE`. One `transaction.atomic()`.
2. **Returns the stock** via the `_apply_line_to_stock` primitive (which enforces
   the `stock_non_negative` CHECK): the produce line(s) are removed first
   (`direction=-1` — fail-fast if the směs has since been sold below what this
   míchání added → `ValidationError`, whole delete rolls back), then each consume
   line is returned (`direction=+1`).
3. **Deletes the record and its internal movements outright**:
   `mixing_job.delete()` (cascades `MixingJobLine`), then deletes the consume and
   produce `Movement` rows (cascading their `MovementLine`s and `MovementAudit`
   rows). Nothing remains in the míchání list or in Historie.

A red **„Smazat dávku"** button sits on the DONE dávka detail (a
non-`recompute`-form `.js-confirm`, danger). The view `mixing_job_delete`
(`michani/<pk>/smazat/`, POST-only) is **branch-scoped** like the rest of míchání
(obsluha delete only their own branch; other branch → 403), catches
`ValidationError` (the sold-down case) and redirects to the míchání index with a
friendly message.

Stock is reversed with the primitive (not `edit_movement`) **on purpose**: the
audit rows would be cascade-deleted with the movements anyway, and going through
`edit_movement` would also schedule a spurious low-stock „Dochází" e-mail on
commit when the produced-mixture removal drops that stock — noise for a record
being erased.

## Rationale

- **Matches the ask** („absolutely remove the record and return the values") for
  a self-contained internal operation with no external artifact to reconcile.
- **Right-sized:** at ~6 users a mistaken míchání should just vanish; a lingering
  „zrušeno" row is clutter the owner explicitly did not want.
- **Safe:** the non-negative guard means a delete that would drive the produced
  směs below zero (already sold) is refused, not forced; the whole thing is
  atomic.

## Consequences

- New service `delete_completed_mixing_job` (exported from
  `services/__init__.py`); new view `mixing_job_delete` + route
  `michani/<pk>/smazat/` (POST-only → no `EXCLUDED_URL_NAMES` entry); a
  „Smazat dávku" button on the DONE detail.
- **Deletion is irreversible and leaves no trace** — no audit, no Historie row.
  This is a deliberate departure from the app's audit-everything default,
  justified by the internal, no-external-artifact nature of a míchání. Extending
  hard delete to any non-internal movement is a **new decision**.
- No migration. The legacy PLANNED/RUNNING `cancel_mixing_job` (audited storno)
  is unchanged — cancel still applies to in-flight jobs; delete applies to DONE.

## Cross-references

- [`0100`](./0100-michani-single-quantity-and-unified-edit.md) — single quantity + unified edit.
- [`0039`](./0039-mixing-job-shape.md) — internal Míchárna counterparties (why no external artifact dangles).
- [`0042`](./0042-overdraw-guided-correction.md) — the `stock_non_negative` guard the reversal relies on.
