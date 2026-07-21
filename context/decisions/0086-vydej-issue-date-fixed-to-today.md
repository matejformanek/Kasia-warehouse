# 0086 — Výdej issue date is fixed to today; the field is removed

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, live-app review)
**Status:** Accepted
**Relates to:**
- [`0044-transfer-issues-dodak.md`](./0044-transfer-issues-dodak.md) +
  [`0059-merge-objednavka-into-prijem.md`](./0059-merge-objednavka-into-prijem.md)
  — příjem keeps `date_issued` + `expected_on` (future date → planned příjem),
  unchanged by this decision.

## Context

The výdej (issue) form offered an editable **„Datum vystavení"** with a
`date.today()` initial and an `assert_no_future_date` guard. In practice stock
leaves the warehouse the day it is typed; a back- or forward-dated výdej has no
real use and the future-date rejection was one more way the form could refuse to
save. Removing the field removes a decision the operator never needs to make.

## Options considered

- **Keep the editable date.** Rejected: no real workflow back-dates a výdej, and
  the future-date guard is a save-blocker with no upside.
- **Fix the date to today, keep the (disabled) field visible.** Rejected: a
  greyed-out field the operator can't change is just clutter.
- **Fix the date to `date.today()` and remove the field entirely** (create *and*
  edit). Chosen.

## Choice

Výdej's issue date is always `date.today()`, set in the view when the Movement
is built. The **„Datum vystavení" field is removed** from both the výdej create
form (`VydejForm`) and the výdej edit form (`VydejEditForm`), and from their
templates; the `assert_no_future_date` call is dropped from the výdej create/edit
paths (the helper stays — příjem still uses it). Příjem is **unchanged**: it
keeps `date_issued` + `expected_on`, and a future `date_issued` is still
rejected.

## Rationale

Right-sized: stock leaves the day it's typed, so a per-výdej date is a choice
with no business value that could only cause errors (wrong date, future-date
rejection). Příjem genuinely needs a date (goods can arrive on a known past day,
and a future date is the planned-order mechanism per 0059), so it is left alone.

## Consequences — things this now blocks or unblocks

- **Unblocks:** the výdej form can never be refused for a future/invalid date.
- **Changes:** a saved výdej is always dated today; the výdej edit screen no
  longer shows or audits a date change (příjem edit still does).
- **Leaves intact:** `assert_no_future_date` (imported/used by příjem create +
  příjem edit), příjem's `date_issued` + `expected_on` fields and the planned
  příjem future-date path.
