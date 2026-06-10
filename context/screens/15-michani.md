# Míchání směsi / Mixing job

**In MVP** per
[`../decisions/0032-mixing-in-mvp.md`](../decisions/0032-mixing-in-mvp.md)
(Petr's 2026-06-09 brief: ~25 mixtures, ≤15 components each, "řešit
poměrně rychle"). The data model is settled by
[`../decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md)
(recipe = first-class `(mixture, component, ratio)` rows; snapshot
at job start; actual consumed may differ from target). Variants
are not in MVP per
[`../decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md),
so produced mixture stock lands directly on the mixture product's
kg pool — no "produce into which variant" choice.

## Purpose
Record a **výrobní dávka** — one execution of a mixture recipe at a
branch. The mixing job takes specified quantities of raw spices from
branch stock, combines them per the receptura attached to the mixture,
and produces mixture stock at the same branch. The flow is in three
beats: **reserve → consume → produce**. The screen is the place a
branch operator opens at the start of mixing and returns to at the end.

## Who uses it
- Branch staff at the branch where the mixing happens — they actually
  weigh, blend, and pack.
- Owner and Karolína for any branch, for oversight or to record a job
  in retrospect.

## What it shows
- Header "Nová výrobní dávka na pobočce <branch name>".
- A **mixture** picker — only catalogue entries of type "směs" with an
  attached receptura appear.
- The chosen mixture's **receptura** rendered read-only beneath the
  picker: each recepturní složka (component product, ratio) per
  [`../decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md).
  Ratios are stored as decimals (0.000–1.000) and rendered as
  percentages. Component is a product reference. Up to **15 components
  per mixture** per
  [`../decisions/0032-mixing-in-mvp.md`](../decisions/0032-mixing-in-mvp.md).
- **Cílové množství** — how many kg of mixture to produce (in kg with
  3 dp per
  [`../decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md)).
  Produced mixture lands directly on the mixture product's
  `(product, branch)` stock row per
  [`../decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md).
- A **derived consumption preview**: for each recepturní složka, the
  quantity that will be consumed to produce the target, alongside
  current on-hand at this branch. Components with insufficient stock
  are flagged in red.
- A **stav dávky** marker:
  - "Připraveno" — nothing has been written to the ledger yet.
  - "Zahájeno" — sources are reserved (or consumed; see open
    question) and the mixture has not yet appeared.
  - "Dokončeno" — sources are consumed and mixture stock has appeared.
  - "Zrušeno" — job abandoned.
- An optional **šarže** field for the produced mixture batch per
  [`../decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md).
  Per-source-šarže (which batches of the components were consumed)
  is also opt-in, captured per consumption line, not required.
- An **operátor** display.
- Optional free-text note.
- Primary actions appropriate to the current stav:
  - "Zahájit dávku" (from Připraveno).
  - "Dokončit dávku" (from Zahájeno) — requires confirming actual
    produced quantity, which may differ from the target due to
    rounding or dust loss.
  - "Zrušit dávku" (from Zahájeno).

## What you can do here
- Pick a mixture.
- Set the target quantity.
- Start the job (reserve / consume sources).
- Finish the job (confirm produced quantity, write mixture stock).
- Cancel an in-progress job (release reservation, return any
  reservation to free stock — exact semantics depend on whether the
  start step reserves or consumes; see open questions).
- View the receptura and the derived consumption.

## What it links to / from
- Reached from:
  - Future "Nová výrobní dávka" affordance on
    [Přehled pobočky](03-prehled-pobocky.md) — does not exist in MVP.
  - Main navigation (future).
- Goes to:
  - [Přehled pobočky](03-prehled-pobocky.md) on completion or
    cancellation.
  - [Historie pohybů](10-historie-pohybu.md) where the resulting
    consume and produce movements appear (under a "mixing job" type).
  - [Detail produktu](05-detail-produktu.md) for the produced mixture.

## Business rules & validation
- The receptura is consulted at the moment of start and **snapshotted
  onto the job** per
  [`../decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md):
  future recipe edits affect future jobs only; this job retains the
  recipe ratios it used.
- Starting a job is allowed only if every recepturní složka has
  sufficient on-hand at the branch (per
  [`../decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md)
  this is the product's single `(product, branch)` stock row in kg).
- Produced quantity at finish may differ from the target; the
  difference is recorded as a quantity delta on the produced movement
  and is not itself treated as an error.
- **Actual consumed quantities** per component are recorded
  separately from the recipe-derived target per
  [`../decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md);
  the operator confirms actuals at finish, which may differ from the
  derived target due to weighing tolerance or dust loss.
- The reserve-vs-consume question:
  - **Reserve at start, consume at finish:** intermediate state where
    sources are locked but still visible on the branch ledger as
    "reserved". Lets the operator cancel cheaply. Adds the concept of
    reservation to the ledger, which MVP does not have.
  - **Consume at start, produce at finish:** sources leave the ledger
    immediately; the produced mixture appears at finish; cancelling
    becomes a correction. Simpler ledger model.
  This screen is drawn to support either; the answer is deferred.
- The job writes movements visible in
  [Historie pohybů](10-historie-pohybu.md) under a "mixing job" type.
  At minimum: N consume movements (one per source spice) and one
  produce movement.
- Editing a mixing job after completion follows the correction model
  on [Úprava pohybu](11-uprava-pohybu.md).
- Only the branch staff at the branch can run a mixing job for that
  branch. Owner-level users may run it for either branch.

## States
- **Empty:** no mixture chosen yet; the consumption preview is hidden.
- **Připraveno:** mixture chosen, target set, consumption preview
  visible. "Zahájit dávku" available if sources sufficient; otherwise
  the action is disabled with an explanatory message.
- **Zahájeno:** sources reserved or consumed (per the open question);
  the screen shows "Dokončit dávku" and "Zrušit dávku".
- **Dokončeno:** read-only summary of consumed quantities and produced
  quantity. A link to [Historie pohybů](10-historie-pohybu.md) shows
  the resulting movements.
- **Zrušeno:** read-only summary stating the job was cancelled.
- **Validation error:** insufficient source on hand, missing target
  quantity, missing mixture, attempt to finish a job that was not
  started.
- **After successful action:**
  - Start → screen transitions to Zahájeno; operator goes physically to
    do the mixing.
  - Finish → screen transitions to Dokončeno; transient confirmation;
    return to branch view available.

## What this screen explicitly does NOT do
- Does not generate any external document — there is no internal
  výrobní list PDF in MVP-of-the-future-feature (defer to a later
  conversation).
- Does not record per-source-batch traceability into the produced
  mixture batch in MVP-of-the-future-feature, unless and until the
  batch-traceability question is decided in favour (see
  [`../product-ideology.md`](../product-ideology.md)).
- Does not handle multi-batch mixing in a single job (one job =
  one produced batch).
- Does not allow editing the receptura from here — that lives on
  [Detail produktu](05-detail-produktu.md) for the mixture.

## Open questions for this screen
- **Reserve vs consume** at the start step — sketched above; defer to
  when this screen actually ships. Operational UI choice; not a data
  model question (the underlying consume movement happens either way).
- Whether to allow recording a mixing job **after the fact** (an
  operator who forgot to open the screen at start). Likely yes — the
  ledger should reflect reality — but introduces an "as-of" timestamp
  divergence between when sources left and when the mixture appeared.
- Whether dust loss / rounding should be tracked separately or just
  surface as a quantity delta on the produced movement. Current
  default: surface as delta on the produced movement.

> Recipe versioning is closed by
> [`../decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md):
> snapshot at job start.
>
> Per-source-batch traceability is opt-in per
> [`../decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md):
> operator records source šarže per consumption line when known, skips
> otherwise; the mixture batch may itself have a šarže recorded.
