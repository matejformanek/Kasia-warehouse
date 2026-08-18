# 0100 — Míchání: single „Namícháno" quantity + unified edit

**Date & by-whom:** 2026-08-18 — Matej (relaying Petr's ask; owner-confirmed
wording on the checkbox default, the data-fix policy, and the single create field)

**Status:** Active

**Supersedes (in part):**
- [`0060-michani-immediate-only.md`](./0060-michani-immediate-only.md) — the
  two-input create form (target + optional „Skutečně vyrobeno") is dropped;
  míchání is one number. 0060's **immediate-action model is kept** (one atomic
  consume+produce, no modes) — only the second input goes.
- [`0039-mixing-job-shape.md`](./0039-mixing-job-shape.md) — only §(3)'s
  target-vs-actual "yield as delta" framing is retired **for new jobs**:
  `target_qty` is now set equal to the produced amount, so a fresh job has no
  yield delta. §§(1)+(2) and legacy jobs are untouched.

## Context

Míchání was built (0039) around a two-step mental model: a **target** batch
(`target_qty`, which drives ingredient consumption) plus a separately-recorded
**actual produced** amount (`actual_produced_qty`, which adds finished stock).
0060 collapsed the *flow* to one immediate action but kept **both inputs** on
the form.

The workers do not use it that way. Their real workflow is a **Friday
reconciliation**: at week's end they look at everything mixed over the week and
want to record **one number** — the total kg made („Namícháno") — and have the
system add that finished-mixture stock and deduct the source spices in recipe
proportion. It is effectively a "clever inventura" for mixtures.

Because the two-input model didn't match, everyone since **13 Aug 2026**
mis-entered on prod (all TYN): they left the recipe's default batch in the
consumption-driving field (`target_qty`) and typed the week's total into
`actual_produced_qty`. Production therefore added the full weekly total to stock
(e.g. job 9 added **2700 kg**) while consumption deducted only **one batch**
(107 kg) — a large, silent stock discrepancy across jobs 8–12. One job (#12) has
both movements present but with **zero lines** — nothing consumed or produced.

This is the moment to make the model match the workflow, add a way to repair the
five bad jobs, and close the class of "two numbers that disagree" errors.

## Options considered

- **Keep two inputs, better labels/help.** Rejected — the mismatch is
  conceptual, not cosmetic; a second field is a second thing to get wrong, and
  the Friday-reconciliation flow has exactly one number.
- **Add a new model column for "week total" + a reconciliation screen.**
  Rejected — new schema + new screen for a ~6-user shop violates
  right-sized-for-small-business; the existing `target_qty`/`actual_produced_qty`
  pair + `record_completed_mixing_job` already do consume+produce atomically.
- **Single „Namícháno (kg)" quantity; consumption = namícháno × ratio; reuse the
  existing two columns set equal; add one unified edit built on
  `edit_movement`.** Chosen.

For the data repair specifically:
- **Zero out the over-added production and re-mix at the recipe default.**
  Rejected — throws away the real produced totals the workers actually made.
- **Keep the produced totals, scale consumption up to `produced × ratio`.**
  Chosen — the produced numbers are the trustworthy figure; consumption was the
  part left wrong.

## Choice

- **Create is one field.** The míchání create screen shows a single
  **„Namícháno (kg)"** input (the former `target_qty` input, relabelled — same
  `id_target_qty` / POST name / `#mixture-defaults` hook). Consumption is always
  recipe-proportional (`namícháno × ratio`). The view calls
  `record_completed_mixing_job(target_qty=<namícháno>,
  actual_produced_qty=<namícháno>)` — both columns get the one value. The
  optional „Skutečně vyrobeno" input and its parse/echo path are removed.
- **Unified edit on the DONE detail page.** The read-only „Položky" card becomes
  an edit form (`mixing_job_edit`, POST `michani/<pk>/upravit/`) showing the
  made-amount („Namícháno") **and** per-ingredient consumption, with a checkbox
  **„Přepočítat spotřebu podle receptury"**, **checked by default**. Checked →
  per-line inputs are read-only and recompute live as `produced × ratio`;
  unchecked → the operator overrides consumption per line. Save routes the stock
  delta through a new service `edit_completed_mixing_job`, built on the existing
  `edit_movement` (audited, atomic, rolls back on overdraw).
- **Data repair (jobs 8–12, 13–18 Aug, TYN):** an idempotent scratchpad ORM
  script calls `edit_completed_mixing_job(produced_qty=job.actual_produced_qty,
  recompute_consumption=True)` per job — **keeps the produced totals**, scales
  consumption up to `produced × ratio`, sets `target_qty = produced`, and
  rebuilds job 12's two empty movements. Dry-run first (writes nothing), then
  apply.
- **Recipe PDF is kept, out of the primary flow.** The „Stáhnout recepturu
  (PDF)" link stays on the detail page; it is no longer part of the create/edit
  path.

No model migration: `target_qty`/`actual_produced_qty` are reused (set equal for
new jobs) and the edit rides the existing `edit_movement` machinery. Internal
Míchárna counterparties mean no dodák/e-mail is ever re-sent on an edit.

## Rationale

- **Matches the workflow.** One number is what the workers reconcile to; the
  system does the proportional deduction they were doing by hand (badly).
- **No new schema, no new screen.** Reusing the two columns set-equal plus
  `edit_movement` means zero migration and no new stock logic — the atomic
  consume+produce+edit paths already exist and are tested.
- **Kills a whole error class.** With one input there is no "two numbers that
  disagree" failure, and the 1-dp ROUND_HALF_UP prefill contract on the edit
  inputs removes the phantom-`.x5`-correction trap.
- **Repair keeps the truth.** The produced totals are what was physically made;
  consumption was the wrong leg. Scaling consumption up (not zeroing production)
  preserves the real figures and restores ledger consistency. Dry-run-first is
  the durability instinct from right-sized-for-small-business.

## Consequences — things this now blocks or unblocks

**Unblocks:**
- `edit_completed_mixing_job` lands in `inventory/services/mixing.py` (exported
  from `services/__init__.py`), powering both the unified edit and the repair.
- New view `mixing_job_edit` + route `michani/<pk>/upravit/` (POST-only → no
  `EXCLUDED_URL_NAMES` entry). Branch-scoped like `mixing_job_finish` (obsluha
  edit their own branch; other branch → 403).
- The five mis-entered prod jobs (8–12) get repaired to consistent stock.

**Forecloses (without a follow-on decision):**
- A separate "week total" column or a dedicated reconciliation screen.
- Re-introducing a second produced-vs-target input on the create form.

**Kept / unchanged:**
- 0060's immediate-action, no-modes create; the shortage → inventura jump; the
  `#mixture-defaults` (0089) prefill; the recipe PDF (0055).
- The legacy PLANNED/RUNNING lifecycle services (`plan_/start_/finish_/
  cancel_mixing_job`) for any in-flight job — retired from creation only.
- Admin shows both `target_qty` + `actual_produced_qty` (dev-facing; legacy jobs
  genuinely differ) — deliberately left as-is.

## Cross-references

- [`0060-michani-immediate-only.md`](./0060-michani-immediate-only.md) — the
  immediate-action model this keeps.
- [`0039-mixing-job-shape.md`](./0039-mixing-job-shape.md) — the original
  two-input shape this narrows.
- [`0061-display-1dp-comma.md`](./0061-display-1dp-comma.md) — the ROUND_HALF_UP
  1-dp prefill contract the edit inputs follow.
