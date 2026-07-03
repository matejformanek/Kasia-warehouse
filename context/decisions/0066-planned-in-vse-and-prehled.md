# 0066 — Planned příjmy surface in Historie "Vše" + Přehled; history pagination

**Date:** 2026-07-03
**Decider:** Matej (live walkthrough)
**Status:** Active
**Amends:** [`0059-merge-objednavka-into-prijem.md`](./0059-merge-objednavka-into-prijem.md)
(its "PLANNED are NOT history — only in the Plánované tab" presentation rule).

## Context

Per 0059, planned příjmy (objednávky) were reachable **only** via the Historie
"Plánované" tab. In the live walkthrough Matej found this wrong on two counts:

1. **Historie "Vše" felt broken** — "Vše" (all) omitted planned rows, so it
   didn't actually show everything.
2. **A due planned příjem was invisible where it matters** — once its promised
   arrival date passes, nothing on the **Přehled** surfaces "this order was due,
   confirm receipt." Planned rows were only findable by opening Historie.

Also, Historie was hard-capped at the newest 200 rows with no paging.

## Choice

- **Historie "Vše" unions DONE + PLANNED.** Planned rows sort first (soonest
  `expected_on`), then done rows (newest `date_issued`). The dedicated
  **Plánované** tab stays (worklist). The "Vše" tab count becomes done + planned.
- **Historie is paginated at 50 rows/page** (`?page=N`), replacing the 200 cap.
  The out-of-table planned-cancel forms render for **any** planned row on the
  page (not only the Plánované tab), so the in-row "Zrušit" works in "Vše" too.
- **Přehled "K vyřešení" gains due planned příjmy** — PLANNED příjmy with
  `expected_on <= today` appear as a task ("Očekávaný příjem" → **Přijmout**,
  linking to `prijem_confirm`) and count toward the K-vyřešení KPI.

## Rationale

"Vše" should mean all. Surfacing a *due* order on the landing page is the whole
point of recording an expected arrival — the operator confirms receipt from the
dashboard instead of hunting in Historie. Pagination keeps the now-larger
combined list manageable. All of this reuses existing rows/actions
(`prijem_confirm`, `prijem_plan_cancel`) — no new model or view.

## Consequences

- The 0063/0064 client filter now searches only the **current 50-row page**
  (it operates on rendered rows). "Nalezeno: N" is the full server total.
- A planned příjem can now appear in three places: Přehled (when due), Historie
  "Vše", and Historie "Plánované". All route to `prijem_confirm` (0059), never
  the DONE-movement editor.
- No schema/migration change. `movement_history` + `home` views + their
  templates change; `design-system.md` note updated.
