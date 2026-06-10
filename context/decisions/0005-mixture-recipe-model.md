# 0005 — Mixture recipe data model

## Context

VERA GURMET mixtures (e.g. *Zlaté Kuře*) are produced by combining
raw spices in fixed ratios — see
[`../product-ideology.md`](../product-ideology.md). The catalogue
contains both raw single-ingredient spices and mixtures (and
single-ingredient packed retail goods). A future "míchání směsi"
screen, sketched in
[`screens/future-misseni.md`](../screens/future-misseni.md), will
record one execution of a mixture (a **výrobní dávka**).

The data model for recipes has to land now — even though the screen
is not in MVP — to prevent the catalogue, příjem, výdej, and movement
schemas from being painted into a corner. The open-question entry in
[`../open-questions.md`](../open-questions.md) named several
sub-questions: recipe shape, drift over time, traceability of mixture
batch to source-spice batches.

Several sub-questions are settled by prior Phase A decisions:

- **Q1 (šarže optional)** → per-source-batch traceability on mixing
  jobs is opt-in, not required.
- **Q2 (one catalogue, branch-specific stock)** → mixtures and raw
  spices live in the same products table; they share stock
  partitioning by `(product, branch)`.
- **Q3 (primary unit kg with 3 dp)** → recipe arithmetic and
  consumption / produced quantities are in kilograms with 1 g
  precision; ratios stored as exact decimals.

The remaining real choice is whether a recipe edit retroactively
changes past mixing jobs.

## Options considered (for the recipe-versioning sub-question)

- **(i) Snapshot at job start.** The current recipe is copied onto
  the výrobní dávka record at the moment it transitions from
  Připraveno to Zahájeno. Recipe edits thereafter affect future jobs
  only.
- **(ii) Live recipe.** Jobs reference the current recipe by
  pointer. Editing a recipe retroactively changes what past jobs
  "claim" to have used. Smaller schema (no per-job snapshot), at the
  cost of historical accuracy and audit clarity.

## Choice

The mixture-recipe model is:

1. **Recipe shape.** A recipe is a set of rows attached to a
   mixture-kind product: `(mixture_product, component_product,
   ratio_decimal)`. Component products are raw-spice (or mixture)
   products from the same global catalogue. Ratios are exact decimals
   summing to `1.000` (i.e. percentages stored as 0.300, not 30).
   Recipes are not embedded as JSON on the mixture product; they are
   first-class rows.
2. **Catalogue.** Mixtures and raw spices share one **products**
   table, distinguished by a `kind` column (`raw_spice`, `mixture`,
   and any additional kinds Q6 introduces). A recipe exists only for
   `kind = mixture` rows.
3. **Recipe versioning — (i) snapshot at job start.** When a výrobní
   dávka transitions to Zahájeno, the current recipe is copied
   onto the job (one `recipe_snapshot` row per component, with the
   ratio and the component product reference frozen). Future recipe
   edits affect future jobs only; past jobs always reflect the recipe
   they actually used.
4. **Actual vs derived consumption.** The recipe is a *target*. A
   mixing job records **actual consumed quantities** per component,
   which need not equal `recipe_ratio × target_produced`. The job's
   produced quantity at finish may also differ from the target — that
   delta lives on the produced movement (already drafted in
   `future-misseni.md`).
5. **Per-source-batch traceability — opt-in.** A mixing job may
   record the source šarže per consumed component if the operator
   has it (per [`0001-sarze-tracking.md`](./0001-sarze-tracking.md)).
   Not required. The produced mixture batch likewise has an optional
   šarže. Future upgrade path: a per-mixture flag "requires source
   batch traceability" can flip individual mixtures to mandatory
   without changing the schema.

## Rationale

- **Snapshot beats live for historical accuracy.** Petr's audit
  requirement ("ať je vidět, kdo co změnil a kdy") demands that the
  past not change under your feet. A snapshot per job costs a few
  rows; the audit story is clean.
- **First-class recipe rows beat JSON-embedded recipes.** Joinable
  queries ("which mixtures use paprika?") are trivial with rows; with
  JSON they are awkward and slow. Validation ("ratios sum to 1.000")
  is enforced at write time on rows; with JSON it has to be enforced
  in application code. Foreign keys to component products give
  referential integrity for free.
- **Shared catalogue beats separated tables.** Per Q2 there is one
  products table; mixtures are a kind. This keeps catalogue browse,
  stock lookup, and movement records uniform regardless of whether
  the product is raw or a mixture.
- **Target vs actual matters in practice.** Real mixing has dust
  loss and minor weighing tolerance. Forcing recipe-exact
  consumption would make the operator falsify entries to clear
  validation. Recording actual is honest.
- **Opt-in traceability** keeps the schema light for the common
  case (no batch info recorded) while leaving the door open if Kasia
  ever takes on a customer or auditor that requires it.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Catalogue schema: a `kind` column on products with at least
  `raw_spice` and `mixture` (additional kinds from Q6 if relevant).
- A `recipe_component` table: `(mixture_product_id,
  component_product_id, ratio_decimal NUMERIC(7,6))`. Ratios at 6 dp
  to support recipes like 12.5 % cleanly. Sum-to-one is a write-time
  invariant.
- A future `mixing_job` table (when the screen ships): branch, date,
  operator, mixture, target produced quantity, status, optional
  produced šarže, optional note.
- A future `mixing_job_component_snapshot` table: `(job_id,
  component_product_id, ratio_decimal_at_start)` — the snapshot.
- A future `mixing_job_actual_consumption` table or per-component
  fields on the job: actual consumed quantity per component, optional
  source šarže per component.
- `screens/05-detail-produktu.md` for mixture-kind products: shows
  the recipe (component list with ratios). Editing recipes is owner
  / Karolína only.
- `screens/04-katalog-produktu.md`: can filter by kind (raw vs
  mixture).
- `screens/future-misseni.md`: the recipe-snapshot question is
  settled; the "reserve-vs-consume" question remains open (operational
  detail, not data-model).

**Forecloses (without follow-on decisions):**

- Mixtures-as-recipes-of-mixtures (nested mixtures) without an
  explicit decision. The schema permits it (component_product can be
  any product), but the operational semantics are not designed for it
  and `future-misseni.md` does not handle it. If nested mixtures ever
  arise, write a new decision.
- Multi-output mixing jobs (one job producing multiple mixture
  batches). One job = one produced mixture batch, per
  `future-misseni.md`.
- Live-edit of past job recipes. The snapshot is immutable; if a
  past job recipe needs correcting, the correction workflow on
  `screens/11-uprava-pohybu.md` is the path.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  code* › "Mixture recipe data model".

**Remains open (deferred):**

- **Reserve vs consume at mixing-job start** — an operational UI
  choice in `future-misseni.md`; doesn't affect catalogue / recipe
  schema. Defer to when the screen ships.
- **After-the-fact recording** of a mixing job — also operational;
  defer.
- **Dust-loss / rounding** as a separate field — current answer is
  "no, it surfaces as delta on the produced movement". Revisit only
  if Petr wants to track it explicitly.

**Affects future decisions:**

- Q6 (pack-size granularity) — orthogonal. A mixture is a product;
  if Q6 introduces variants for packed mixture SKUs, those variants
  attach to the mixture product the same way variants attach to raw
  spices.
