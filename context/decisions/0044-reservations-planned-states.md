# 0044 — Reservations: planned mixing + planned inter-branch transfers

**Date:** 2026-06-14
**Decider:** Matej (relaying Petr's 2026-06-14 ask)
**Status:** Active
**Supersedes (in part):**
[`0039-mixing-job-shape.md`](./0039-mixing-job-shape.md) § (1)
*Reserve vs. consume at start*.
**Relates to:**
[`0030-vydej-default-ricany-supersedes-0004.md`](./0030-vydej-default-ricany-supersedes-0004.md)
§ Affects future decisions — branch↔branch transfers materialise *now*.

## Context

Petr (via Matej, 2026-06-14): every flow today decrements stock the
instant the operator clicks "vystavit / spustit", so the dashboard
shows reality only *after the fact*. The threshold half of advance
warning is settled by [`0043`](./0043-reorder-threshold.md). The other
half is **reservations** — known commitments that haven't physically
left the branch yet. Two concrete sources surfaced in the same brief:

1. **Planned mixing job** — Karolína queues a směs to be mixed later
   today / tomorrow. The raw spices the job will consume should
   already count against effective stock.
2. **Planned inter-branch transfer** — *"při příjem/výdej se dá
   vystavit prostě že se má něco převézt z jedné pobočky do druhé
   s nějakým datumem"*. Branch↔branch transfers were explicitly
   deferred in
   [`0030`](./0030-vydej-default-ricany-supersedes-0004.md)
   § Affects future decisions — *"if they ever materialise, the
   natural fit is a new `prevod` kind then, when the case is
   concrete. Not now."* They materialise now.

[`0039`](./0039-mixing-job-shape.md) § (1) explicitly rejected
reserve-at-start in 2026-06-12 on the grounds that reservations
"have zero current uses" and would burden every stock query. That
objection is no longer load-bearing: this decision introduces concrete
uses (advance warning panel, daily e-mail, planned transfers) and
makes "reserved-aware" a first-class concept via the `effective_kg`
helper from [`0043`](./0043-reorder-threshold.md).

## Options considered

### Reservation source #1 — planned mixing

- **(a)** Keep 0039's consume-at-start; no PLANNED state. Operator
  who "knows we'll mix tomorrow" has to wait. Rejected — defeats the
  advance-warning purpose.
- **(b)** Add a PLANNED state before RUNNING. PLANNED jobs do not
  touch stock; transitioning to RUNNING consumes stock exactly as
  0039 already does. **Chosen.**

### Reservation source #2 — planned inter-branch transfer

- **(a)** Add a new `Movement.kind = "prevod"` value. The "natural
  fit" 0030 flagged. Each transfer is one Movement row with both
  source + target branches. **Rejected** — a transfer is one business
  event but **two** ledger entries (the výdej at source and the
  příjem at target). `apply_movement` + Stock invariants assume one
  branch per Movement. Pinning the pair on a `Movement.kind=prevod`
  would require duplicating the kind for both legs and inventing a
  new "is this the source leg or target leg" sub-field.
- **(b)** New `PlannedTransfer` header model with a back-FK on both
  paired Movements. Header owns `scheduled_for` + PLANNED state;
  execution writes a pair of Movements via the existing
  `apply_movement` path with a seeded `is_internal=False` "Převod
  mezi pobočkami" counterparty pair. **Chosen.**

### Reservation effect — block vs. inform

- **(a)** Block competing výdej when reservation > current. Adds a
  parallel "over-reservation" UX with two error paths and a forced
  cancellation flow.
- **(b)** Informational — reservations show up in `effective_kg`
  + the dashboard but don't gate the existing overdraw check.
  **Chosen.** Race at ~6 users is rare and is caught at apply time
  by the existing Stock `CHECK quantity >= 0`; guided-correction
  per [`0042`](./0042-overdraw-guided-correction.md) covers the
  recovery path.

## Choice

### (1) MixingJob gains a PLANNED state

- `MixingJob.State` extended with `PLANNED = "planned"` **before**
  `RUNNING`.
- Allowed transitions: `PLANNED → RUNNING (consume stock) → DONE`
  or `PLANNED → CANCELLED`. Encoded in service functions, not at
  DB level (Django doesn't model state machines cleanly there).
- New `MixingJob.planned_for: DateField(null=True, blank=True)` —
  operator's intended start date.
- Existing `start_mixing_job` is split into two service entry
  points:
  - `plan_mixing_job(*, recipe, branch, output_kg, planned_for,
    created_by)` — creates a PLANNED MixingJob with derived lines.
    **Does not touch Stock.**
  - `start_mixing_job(...)` (existing) — signature gains optional
    `job=` parameter. When provided, asserts `job.state == PLANNED`,
    transitions to RUNNING, and runs the existing consume path.
- One-shot "spustit hned" stays as a wrapper calling `plan_mixing_job`
  + `start_mixing_job` in one `transaction.atomic()`.

### (2) New `PlannedTransfer` model

One row = one scheduled branch↔branch transfer.

- `source_branch FK → Branch on_delete=PROTECT`
- `target_branch FK → Branch on_delete=PROTECT`
  - `source ≠ target` enforced in `clean()` and via
    `CheckConstraint(~Q(source_branch=F("target_branch")))`.
- `product FK → Product on_delete=PROTECT`
- `quantity_kg DecimalField(max_digits=10, decimal_places=3)` with
  `CheckConstraint(quantity_kg > 0)`.
- `scheduled_for DateField`
- `state TextChoices` ∈ {`PLANNED`, `DONE`, `CANCELLED`}
- `notes`, `created_by FK → User`, `created_at DateTimeField(auto_now_add=True)`

`execute_planned_transfer(transfer)` (in `inventory/services.py`)
runs inside `transaction.atomic()`:

1. Assert `state == PLANNED`.
2. Build a výdej Movement from `source_branch` to the seeded
   "Převod mezi pobočkami" Customer (one line: product +
   quantity_kg). `apply_movement`. Set `transfer` FK.
3. Build a příjem Movement at `target_branch` from the seeded
   "Převod mezi pobočkami" Supplier (one line, same product +
   qty). `apply_movement`. Set `transfer` FK.
4. Mark `transfer.state = DONE`. Save.

Counterparty pair is `is_internal=False` so the existing
0007/0030/0031 hooks fire on the výdej leg: dodák PDF
auto-issued, Petr+Karolína e-mail sent, dodák counter advances.
The dodák is the physical paper for the driver. Same flow as a
výdej to Říčany.

`cancel_planned_transfer(transfer)` flips `state=CANCELLED`. No
stock touched.

A new `Movement.transfer: ForeignKey(PlannedTransfer,
on_delete=PROTECT, null=True, blank=True, related_name="movements")`
lets the audit trail link both executed Movements back to their
originating transfer.

### (3) `reserved_kg(product, branch)` helper

Sums two sources at a single branch:

- **`MixingJobLine.derived_qty`** for jobs in `state=PLANNED` whose
  `branch == branch` AND `component_product == product`.
- `PlannedTransfer.quantity_kg` for rows in `state=PLANNED` with
  `source_branch=branch` AND `product=product`.

Does **NOT** subtract incoming planned transfers on `target_branch`
— reservations are *outgoing commitments only* in MVP. Promised
inbound is a different concept and is explicitly deferred.

### (4) Overdraw check is unchanged

`apply_movement` and `_compute_overdraw` keep operating on raw
`Stock.quantity` per
[`0042`](./0042-overdraw-guided-correction.md). Reservations are
**informational** on the dashboard; they do not block competing
výdejs. Rationale above.

## Rationale

- **Two separate use cases, one shared `reserved_kg` formula.** The
  dashboard, product detail page, and e-mail summary all read one
  number; planned mixings and planned transfers both feed it.
- **Separate `PlannedTransfer` table** keeps `Movement.kind` binary
  (`{prijem, vydej}`) and gives the pairing (scheduled_for, PLANNED
  state, both Movement legs) a first-class home. The shape change
  is contained — see § "Append-only protocol" below.
- **Counterparty pair `is_internal=False`** confirmed by Matej
  2026-06-14: the dodák is the physical paper for the driver. Re-uses
  the existing dodák auto-issue + e-mail path verbatim. No new
  cross-cutting code in `apply_movement`.
- **All authenticated users may create / view / execute / cancel
  PlannedTransfers** (Matej 2026-06-14 confirmation). Symmetric with
  the all-users create permission; no tier gate beyond
  `LoginRequiredMiddleware`. Different from 0043's vlastník-only
  threshold edit — a transfer is execution, not planning data.
- **Informational reservations (not blocking)** — at ~6 users the
  race is rare; the existing CHECK constraint + guided correction
  (0042) is sufficient. Blocking would add a parallel error UX.

## Date & by-whom

2026-06-14 — Matej (relaying Petr's ask).

## Append-only protocol

Per [`.claude/rules/decision-log-discipline.md`](../../.claude/rules/decision-log-discipline.md),
when this decision lands, the **only** permitted edit to
[`0039-mixing-job-shape.md`](./0039-mixing-job-shape.md) is a
one-line note at the top, immediately under the title:

> *Superseded by [0044](./0044-reservations-planned-states.md) in
> part — see § (1) Reserve vs. consume at start. §§ (2) and (3)
> remain in force.*

§§ (2) (after-the-fact recording) and (3) (yield-loss tracking)
from 0039 are unchanged. The already-RUNNING phase's
consume-at-start behaviour is preserved verbatim — only the
preceding PLANNED state is new.

[`0030`](./0030-vydej-default-ricany-supersedes-0004.md) is **not
modified**; 0044 simply closes the open question it flagged.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory.MixingJob` gains a PLANNED state + `planned_for` field.
- `inventory.PlannedTransfer` ships in the next migration.
- `inventory.Movement` gains a nullable `transfer` FK.
- `inventory/services.py` gains `plan_mixing_job`,
  `execute_planned_transfer`, `cancel_planned_transfer`, and the
  shared `reserved_kg` helper. `start_mixing_job` gains an
  optional `job=` argument for PLANNED→RUNNING.
- A data migration seeds the "Převod mezi pobočkami" `Customer` +
  `Supplier` pair (`is_internal=False`), mirroring the pattern from
  `inventory/0008_seed_adjustment_counterparty` for the "Inventura
  / ruční úprava" pair (per
  [`0041`](./0041-manual-stock-adjustment.md)).
- A new `/prevody/` CRUD surface lands (index, create, detail,
  execute, cancel) — all authenticated users.
- A new `/michani/planovat/` surface lands for PLANNED mixings;
  the existing one-shot stays as a wrapper.

**Forecloses (without follow-on decision):**

- Reservations on a `Movement.kind=prevod`. To switch shapes, a
  numbered file naming the concrete reporting need that a single
  Movement row solves better than a paired-Movements header.
- Incoming planned transfers counting as inbound effective stock.
  Promised-inbound is explicitly deferred; a future decision can
  add `target_branch` to `reserved_kg` (as a positive contribution)
  if shadow run reveals the need.
- Blocking overdraw on over-reservation. To switch, supersede this
  decision; the current rule is informational reservations only.

**Resolves:**

- 0030's "Affects future decisions" — branch↔branch transfers
  materialise via PlannedTransfer (not via `Movement.kind=prevod`).
- 0039 § (1) reserve-vs-consume — *partially* superseded; PLANNED
  state adds a reserve-style step before the existing consume-at-
  RUNNING flow.

**Cross-cutting:**

- `Movement.transfer` is **nullable**. No backfill needed; new
  field is populated going forward by `execute_planned_transfer`.
- `reserved_kg` is read on every dashboard / product-detail render;
  the queries are small (few dozen rows × 2 sources) and acceptable
  at ~6 users without indexing or denormalisation.
