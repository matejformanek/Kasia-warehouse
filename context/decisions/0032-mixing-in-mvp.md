# 0032 — Míchání směsí in MVP

## Context

Petr's 2026-06-09 reply (Czech, relayed via Matej):

> "Míchání směsí — cca 25, do 15 surovin, řešit poměrně rychle."

The mixing-job screen was previously documented as `screens/future-misseni.md`
— sketched only to keep the data model honest, with the actual UI
deferred to "later". Petr's reply puts it on the critical path:
~25 mixtures, each with up to 15 components, and "řešit poměrně
rychle" (handle reasonably quickly) means MVP, not after.

The data model is already settled by
[`0005-mixture-recipe-model.md`](./0005-mixture-recipe-model.md):
recipe = first-class `(mixture, component, ratio)` rows; mixtures
and raw spices share the products table by `kind`; snapshot at
mixing-job start; actual consumed may differ from recipe target;
opt-in source-batch traceability. The variant-related guidance in
[`0005`](./0005-mixture-recipe-model.md) § Affects-future is
neutralised by
[`0028-mass-only-supersedes-0006.md`](./0028-mass-only-supersedes-0006.md)
— without variants, the produced mixture lands directly on the
mixture product's kg pool, full stop.

This decision is **new** — it does not supersede any prior entry.

## Options considered

- **(a) Keep deferred.** Status quo per `screens/future-misseni.md`.
  Contradicts Petr's stated priority.
- **(b) Promote the screen to MVP with the data model unchanged.**
  The sketch in `future-misseni.md` is structurally close enough
  that promoting it costs a rename and a sweep, not a rewrite.
- **(c) Promote with a richer model.** Add features beyond what
  Petr asked for (reserve-vs-consume semantics, multi-output jobs,
  yield-loss tracking). Rejected — Petr's "poměrně rychle" prefers
  the smallest workable version.

## Choice

**(b) Promote `future-misseni.md` to a real MVP screen.**

- File is renamed `screens/15-michani.md` (next free number after
  14-nastaveni). The body is structurally unchanged.
- Data model already settled by
  [`0005`](./0005-mixture-recipe-model.md) — no schema changes here.
- Constraints from Petr's reply, written into the screen:
  - ~**25 mixtures** maximum (informational, not enforced).
  - **≤ 15 components per mixture** (informational; the UI shows the
    recipe full; no hard cap enforced in MVP).
  - "Reserve vs consume at start" open question per
    `screens/future-misseni.md` stays open (operational UI choice,
    not data model). Default = **consume at start** so the ledger is
    simpler; reversible later.
- Mixture stock lands directly on the mixture product's `(product,
  branch)` row in kg per
  [`0028`](./0028-mass-only-supersedes-0006.md). No variant.
- The `Product.kind = mixture` discriminator and the
  `RecipeComponent (mixture_product, component_product, ratio)`
  table are added in the next models pass alongside `Product` and
  `Stock`.

## Rationale

- **Petr's priority is explicit** ("řešit poměrně rychle").
- **The data model was already designed for it.** Promoting the
  screen does not invalidate any prior decision — it just lifts the
  "future" qualifier.
- **Scale is modest.** ~25 mixtures × ~15 components = ~375
  recipe-component rows. Negligible.
- **Variants are out** (per
  [`0028`](./0028-mass-only-supersedes-0006.md)), which simplifies
  the mixing-job UX significantly: no "consume from which variant"
  picker, no "produce into which variant" choice. Everything is the
  product's kg pool.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `screens/15-michani.md` ships in the MVP cut. The screens index in
  [`screens/README.md`](../screens/README.md) lists it under "Daily
  movements" or its own "Production" section.
- The next models pass writes `Product (kind=mixture)` rows and a
  `RecipeComponent` table per
  [`0005`](./0005-mixture-recipe-model.md).
- The future `MixingJob` table (job header + per-component snapshot
  + per-component actual consumption) lands in a follow-on pass when
  the screen is implemented.

**Forecloses (without follow-on decisions):**

- A "no míchání in MVP" reading. The previous `future-misseni.md`
  hedging is gone.

**Resolves:**

- No prior open question is fully closed by this; the operational
  "reserve vs consume" sub-question on the míchání screen stays
  open in `screens/15-michani.md` § Open questions.

**Affects future decisions:**

- The "after-the-fact recording" and "yield-loss as separate field"
  sub-questions in `screens/15-michani.md` § Open questions remain
  open. Defer until first real míchání use.
