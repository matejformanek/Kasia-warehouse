# 0039 — Mixing job shape: consume-at-start, snapshot recipe, yield as delta

## Context

[`0032`](./0032-mixing-in-mvp.md) promoted míchání to MVP and
[`0005`](./0005-mixture-recipe-model.md) settled the recipe data
model (first-class `(mixture, component, ratio)` rows; snapshot at
job start; actual consumed may differ from target). Three operational
questions were explicitly left open in
[`../screens/15-michani.md`](../screens/15-michani.md) § Open
questions for resolution "when this screen ships":

1. **Reserve at start vs. consume at start.** Whether the start
   step locks source quantities as "reserved" until finish, or
   commits the consume immediately.
2. **After-the-fact recording.** Whether an operator who forgot to
   open the screen at start can record a completed job in one go.
3. **Yield loss tracking.** Whether dust loss / rounding has its
   own field, or just surfaces as a delta on the produced movement.

All three need to be answered before the next pass writes the
`MixingJob` table + the start / finish / cancel services. This
decision answers them; the code pass that follows can land
without re-litigating the shape.

## Options considered

### (1) Reserve vs. consume at start

- **(a) Consume at start, produce at finish.** Start step writes
  the consume `Movement` rows immediately (one per recipe
  component); branch stock drops the moment the operator says
  "začínáme míchat". Finish step writes the produce `Movement`
  (one line, the mixture). Cancel becomes a *correction* — a
  fresh inverse Movement that restores the consumed quantities,
  audited like any other correction.
- **(b) Reserve at start, consume at finish.** Start step records
  intent (no ledger writes); branch stock visibly shows
  "reserved N kg of pepř" until finish, at which point the
  consume + produce land together. Cancel is cheap — no audit
  trail entry, just drop the reservation. Adds the concept of
  *reserved stock* to the ledger, which doesn't exist today.
- **(c) All-at-once.** No start step; the whole job is a single
  atomic operation. Loses the ability to pause between
  weighing-out and blending — operators can't open the screen
  when they begin, then return at finish.

### (2) After-the-fact recording

- **(a) Allow.** UI exposes a "Zaznamenat dokončenou dávku"
  affordance that captures source quantities + produced quantity +
  timestamp(s) in one screen — used when the operator forgot to
  open the start step in real time. The timestamp on the consume
  movements is "now" by default but editable. Matches the ledger
  to reality.
- **(b) Forbid.** Every mixing job must go through start → finish.
  Forgetting to start means the job has to be recorded as a
  manual correction via screens 11 + the příjem/výdej path.

### (3) Yield-loss tracking

- **(a) Delta on produced movement.** Operator confirms actual
  produced kg at finish; if it differs from `target_qty`, the
  difference is implicit (`actual_produced - target_qty`). No
  separate field. The screen optionally displays the delta
  ("ztráta: -0,150 kg") read from the recorded actuals.
- **(b) Explicit `loss_kg` column.** A separate numeric field on
  the job, written at finish. Allows querying "total loss this
  month" without arithmetic on movements.
- **(c) Loss per source line.** Each consumed source carries an
  optional `loss_kg` capturing the share of total loss
  attributable to that ingredient.

## Choice

### (1) Consume at start, produce at finish.

Start step writes the consume `Movement` (kind=`vydej` to an
internal odběratel — see Implementation notes) atomically inside
a `transaction.atomic()` block; finish writes the produce
`Movement` (kind=`prijem` from an internal dodavatel). Cancel is
an audited correction that reverses the consume movements.

### (2) Allow after-the-fact recording.

The mixing-job create form accepts an optional `as_of` datetime
that defaults to "now"; the consume Movements use that timestamp,
and a finish-in-the-same-request path lets the operator submit
the consume + produce in one click. This unlocks the common
"forgot to open the screen" case without requiring a manual
correction. The default UX still does start → physically mix →
finish in two clicks; one-shot mode is just an extra button on
the create form ("Zaznamenat dokončenou dávku").

### (3) Yield loss surfaces as a delta on the produced movement.

No explicit `loss_kg` field. Operator enters `actual_produced_kg`
at finish; the screen shows the implicit delta against
`target_qty` for sanity but stores no separate column. Future
reporting can compute loss as `target - actual` over the job
history; if that proves operationally awkward, a numbered file
later can add the explicit field as an additive migration.

## Rationale

- **(1)** Reserving stock requires a new ledger concept (reserved
  vs. on-hand) that has zero current uses and costs every other
  screen that queries stock the burden of "is this number
  reserved-aware?". The "cancel is cheap" upside doesn't hold at
  Kasia scale — cancellation is rare (per `screens/15` "weighing
  tolerance or dust loss" — finish almost always happens), and an
  audited cancel correction is a *feature*, not a cost: "what did
  you mix last week" should show the cancel.
- **(2)** Petr's brief ("řešit poměrně rychle") + the realistic
  shop-floor pattern (operator weighs out, blends, then sits down)
  both point to allowing after-the-fact. Forbidding it forces a
  manual two-step correction every time someone forgets to click
  "Zahájit", which would make the screen feel like a chore. The
  data model already supports it — start and finish are just two
  write paths on the same job header.
- **(3)** A separate `loss_kg` column is a third number for the
  operator to fill that's redundant with `target - actual`. The
  expected pattern: target 5,000 kg → actuals 1,500 / 1,750 /
  1,650 / 0,100 = 5,000 consumed, actual produced 4,950 → loss is
  derivable. If month-end reporting wants the loss column, add it
  later. KISS now per
  `.claude/rules/right-sized-for-small-business.md`.

## Implementation notes

These notes anchor the next code pass (not part of the decision per
se, but locked here so the code matches):

- **`MixingJob` table** (header):
  - `branch FK → Branch on_delete=PROTECT` (job is per-branch)
  - `mixture FK → Product on_delete=PROTECT` (kind=mixture)
  - `target_qty NUMERIC(10,3)` — the operator's stated target at
    start
  - `actual_produced_qty NUMERIC(10,3) NULL` — set on finish
  - `state TextChoices` ∈ {`running`, `done`, `cancelled`}
  - `started_at` (auto_now_add on start)
  - `finished_at NULL` (set on finish or cancel)
  - `created_by FK → User on_delete=PROTECT`
  - `cancel_reason TEXT default ""` — required iff state=cancelled
  - `consume_movement FK → Movement NULL on_delete=PROTECT` —
    the výdej Movement written at start; lets cancel locate the
    rows to reverse
  - `produce_movement FK → Movement NULL on_delete=PROTECT` —
    the příjem Movement written at finish
- **`MixingJobLine` table** (per-component snapshot, frozen at
  start per [`0005`](./0005-mixture-recipe-model.md)):
  - `mixing_job FK → MixingJob on_delete=CASCADE`
  - `component_product FK → Product on_delete=PROTECT`
  - `ratio_at_start NUMERIC(7,6)` — copied from the recipe row at
    start; future recipe edits don't touch in-flight jobs
  - `derived_qty NUMERIC(10,3)` — `target_qty * ratio_at_start`,
    computed and stored at start
  - `actual_qty NUMERIC(10,3) NULL` — set at finish if the
    operator records actuals; otherwise defaults to `derived_qty`
    (model = "ledger says actual; screen lets operator edit")
  - `sarze CharField(blank=True)` — opt-in per
    [`0001`](./0001-sarze-tracking.md), per consumption line
- **Internal counterparties.** The consume Movement is a `vydej`;
  it needs an `odberatel`. Same for produce → needs a `dodavatel`.
  Two seeded internal records:
  - `Customer(name="Míchárna", is_internal=True)` as the
    odběratel for mixing-job consume Movements (new boolean field
    `is_internal` on `Customer`, default False — surfaced
    explicitly so the dodák / e-mail path can skip these).
  - `Supplier(name="Míchárna", is_internal=True)` as the
    dodavatel for mixing-job produce Movements.
  Internal counterparties are excluded from the screen-07 odběratel
  picker and from any other surface that lists "real" partners.
  **Crucially, the screen-08/09 dodací-list path does NOT fire for
  mixing-job consume Movements** — the existing rule "vydej →
  create DodaciList + send e-mail" needs to gate on
  `not movement.odberatel.is_internal`. This is the only
  cross-cutting change to existing code.
- **Service shape.** Three new functions in `inventory/services.py`:
  - `start_mixing_job(*, branch, mixture, target_qty, user,
    as_of=None) -> MixingJob` — snapshot recipe → compute
    derived_qty per line → call `apply_movement(kind=vydej,
    odberatel=Míchárna, …)` for the consume → store
    `consume_movement_id` on the job → return `MixingJob(state=running)`.
  - `finish_mixing_job(*, mixing_job, actual_produced_qty, line_actuals,
    user) -> MixingJob` — write the produce `apply_movement(kind=prijem,
    dodavatel=Míchárna, …)` → set `actual_produced_qty`,
    `produce_movement_id`, `state=done`, `finished_at`.
  - `cancel_mixing_job(*, mixing_job, reason, user) -> MixingJob`
    — call `edit_movement` on `consume_movement` to zero out every
    line with a "míchání zrušeno: <reason>" reason → set
    `state=cancelled`, `cancel_reason`, `finished_at`. (Uses the
    existing audit trail; no new audit code.)
- **One-shot mode.** A combined `record_completed_mixing_job(...)`
  helper for the after-the-fact path — it calls `start` then
  immediately `finish` in the same transaction with the operator-
  supplied `as_of` propagated as the `date_issued` on both
  Movements.
- **Stock-overdraw refusal** still hits the operator at start
  (existing `_apply_line_to_stock` invariant catches it). The
  screen renders the "this component would overdraw" warning per
  `screens/15-michani.md`.

## Date & by-whom

2026-06-12 — Matej (acting as Petr's stand-in per
[`memory/user_role_kasia.md`](../../.claude/projects/-Users-matej-Work-Kasia-warehouse/memory/user_role_kasia.md)).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory.MixingJob` + `inventory.MixingJobLine` ship in the
  next migration; the `is_internal` boolean lands on
  `Customer` + `Supplier` in the same migration. Two seed rows
  ("Míchárna" internal customer + supplier) land alongside.
- `inventory/services.py` gains `start_mixing_job`,
  `finish_mixing_job`, `cancel_mixing_job`, and
  `record_completed_mixing_job`.
- `apply_movement` for kind=vydej gains a guard:
  `not movement.odberatel.is_internal` before invoking the dodák
  PDF + e-mail hook (per the "internal counterparties" note above).
- Screen 15 ships at `/michani/novy/` and `/michani/<pk>/`.

**Forecloses (without follow-on decision):**

- Reserve-style locking on stock for the mixing flow. To switch,
  a numbered file naming the concrete use case (e.g. multi-day
  blending with parallel jobs competing for the same source)
  is required.
- Forbidding after-the-fact recording. To restrict, a file
  naming the failure mode (e.g. operator backdating to cover up
  shrinkage).
- A standalone `loss_kg` column. To add, a file naming the
  reporting need that derivation can't satisfy.

**Resolves:**

- Three open questions in
  [`../screens/15-michani.md`](../screens/15-michani.md) §
  Open questions: reserve-vs-consume, after-the-fact recording,
  dust-loss tracking. Screen text gets a banner pointing here
  once the code pass lands.

**Cross-cutting:**

- Mixing-job consume Movements bypass the dodák PDF + e-mail
  hook because their odberatel has `is_internal=True`. The
  Movement still appears in history (screen 10) under its own
  filterable type so the operator can scroll past mixing-job
  consumes without conflating them with customer výdeje. A future
  decision can introduce a dedicated `Movement.kind` value
  (`michani_konzum` / `michani_produkt`) — for MVP they reuse the
  existing prijem/vydej kinds with the internal-counterparty flag
  doing the discrimination.
