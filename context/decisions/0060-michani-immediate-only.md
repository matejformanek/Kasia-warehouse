# 0060 — Míchání is a single immediate action

**Date:** 2026-07-01
**Decider:** Matej (relaying Petr's ask via the live-app Podpora review)
**Status:** Active
**Supersedes (in part):**
- [`0039-mixing-in-mvp.md`](./0039-mixing-in-mvp.md) — the two-step
  start → finish workflow (and the "record completed batch" second mode)
  are dropped from the UI; míchání is now one immediate action.
- [`0044-reservations-planned-states.md`](./0044-reservations-planned-states.md)
  — the PLANNED míchání job state is no longer created from the UI. The
  `reserved_kg()` mixing source is retained for any legacy in-flight job.
- [`0055-recipe-pdf-and-mixing-notes.md`](./0055-recipe-pdf-and-mixing-notes.md)
  — the "Zahájit míchání →" entry point that opened the mode picker is
  gone; the recipe PDF export + mixing notes are unchanged.

## Context

`admin@kasia.cz` walked the live app (91.98.47.1) on 2026-07-01 and filed
Podpora feedback: míchání is over-complicated. Today the operator picks a
směs + target, then chooses a **režim** (Zahájit dávku → later Dokončit, or
Zaznamenat dokončenou dávku), which creates a RUNNING or DONE `MixingJob`
through a two-step flow inherited from 0039/0044/0055. For a ~6-user spice
distributor this modality is friction with no payoff — a míchání always
consumes the recipe inputs and produces the blend in the same session.

The owner asked for three things:

1. **No modes.** Creating a míchání is one immediate action — consume the
   recipe inputs and add the blend at once, exactly like an immediate příjem.
2. **On failure, keep the typed values.** A shortage today re-renders the
   form having lost everything except the selected směs.
3. **A way to jump into inventura** — pre-filtered to *this blend's inputs* —
   to set current stock, then come back and mix.

## Options considered

- **Keep the modes, just default to "record."** Rejected — the radio card
  stays on screen and the two-step machinery stays reachable; doesn't address
  the "over-complicated" complaint.
- **Delete the PLANNED/RUNNING job machinery outright.** Rejected — a legacy
  in-flight job may exist on prod; deleting the finish/cancel paths would
  strand it. Retire it from *creation* only.
- **One immediate DONE action, reuse `record_completed_mixing_job()`.**
  Chosen.

## Choice

- **Míchání create is one immediate DONE action.** `mixing_job_create` always
  calls the existing `record_completed_mixing_job()` service (services.py) —
  which already does consume + produce in one atomic transaction and returns a
  DONE `MixingJob`. `actual_produced_qty` defaults to `target_qty` when the
  optional **"Skutečně vyrobeno (kg)"** override is left blank. A shortage
  raises `ValidationError` inside the atomic block (detected at consume) and
  rolls back cleanly — no partial stock mutation.
- **Form state is preserved on error.** On `ValidationError` the create view
  re-renders with `selected_branch_id`, `selected_mixture_id`, `target_qty`,
  `actual_produced_qty`, and `note` repopulated from POST (mirrors
  `inventura_edit`'s repopulation).
- **Inventura component pre-filter + `next` round-trip.** `inventura_edit`
  accepts an optional `?products=<pk,pk,…>` that, **in per-branch mode only**,
  restricts the editable rows to those products (intersected with active
  products); `is_low`/`is_all` ignore it. On a successful per-branch save the
  view redirects via `_safe_next(...)` so a `next=` back to the míchání form is
  honoured. The míchání screen links to
  `inventura_edit(<branch>) + "?products=<component pks>&next=<michani url>"`,
  surfaced prominently in `_mixing_preview.html` when any component overdraws.
- **No new PLANNED/RUNNING jobs from the UI.** The `mixing_plan_create`,
  `mixing_job_start`, `mixing_job_finish`, and `cancel_mixing_job`
  views/services and the detail-page PLANNED/RUNNING branches are **retained
  only to finish or cancel a legacy in-flight job** — nothing in the UI creates
  a new planned/running job. The "Naplánovat dávku" entry is removed from the
  míchání index.
- **`reserved_kg()` is unchanged.** It keeps summing PLANNED `MixingJobLine`
  (+ PLANNED `PlannedTransfer`) so any legacy in-flight job still reserves; it
  degrades to zero mixing reservations once no new PLANNED míchání exists.

## Rationale

Reusing `record_completed_mixing_job()` means no new stock logic and no new
model state — the atomic consume+produce path already exists and is tested.
Retaining (not deleting) the legacy job machinery honours the append-only /
don't-strand-prod-data instinct while removing the friction from the common
path. The inventura pre-filter gives the operator the exact "set the inputs,
then mix" loop they asked for without inventing a new screen.

## Consequences

- The míchání create screen loses its "Režim" card; the button reads
  "Namíchat"; a shortage keeps every typed value and offers an "Upravit stav
  surovin" jump into a component-filtered inventura.
- `inventura_edit` gains a `?products=` query contract (per-branch only) and a
  `next=` round-trip on successful per-branch save.
- No migration. `MixingJob`/`MixingJobLine` keep all states; only the *paths
  that create* PLANNED/RUNNING jobs are removed from the UI.
- Tests that asserted the two-mode create flow are rewritten to assert an
  immediate DONE job with both consume + produce movements; the finish/cancel
  tests build a RUNNING job directly via `start_mixing_job()` and are marked as
  the legacy path.
