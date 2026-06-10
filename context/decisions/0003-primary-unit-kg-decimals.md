# 0003 — Primary mass unit: kilograms with decimals (3 dp)

## Context

The catalogue holds products that, depending on the outcome of the
still-open Q6 (pack-size granularity, see
[`../open-questions.md`](../open-questions.md)), may be stocked either
**by mass** (raw spice in bulk) or **by count of pack** (e.g. 100 g
retail jars). This decision picks the canonical unit for the
**mass-stored** case. The count-stored case uses **ks** (piece /
kus), independent of this decision.

The owner-request names kilos, hundred-gram packs, and 25 kg sacks
side by side ("po kilech … po sto gramech … po pětadvacetikilových
pytlech"). Kilos are the lingua franca; grams and sacks are derived
display forms.

## Options considered

- **(a) kg with decimals.** Storage as exact decimal kilograms,
  NUMERIC(10, 3) — three decimal places gives 1 g precision.
- **(b) g as integers.** Storage as integer grams; no decimal
  arithmetic, no float-related surprises.
- **(c) Defer until Q6 decides pack-size.** Hold answer in case Q6
  reshapes the question.

## Choice

**(a) kilograms with decimals, NUMERIC(10, 3) — three decimal places
(1 g precision).** All mass-stored quantities — stock-on-hand,
movement-line quantities, recipe-derived amounts — are kilograms
with up to three decimal places. Display can render as grams (e.g.
`0.100 kg` shown as `100 g` on retail packs) or as sacks; storage is
always kilograms.

## Rationale

- **Owner voice.** Petr names kilos first
  ([`../owner-request.md`](../owner-request.md)). UI in kilograms
  reads naturally to the people using it; integer grams do not.
- **Bulk-trade alignment.** 25 kg sacks dominate the inbound side;
  saying "1 250 kg oregano on hand" reads cleanly, "1 250 000 g"
  does not.
- **Exact arithmetic.** NUMERIC(10, 3) gives exact decimal
  representation. Recipe percentages times mass amounts (e.g.
  `0.300 × 10.000 = 3.000`) round predictably. Float is explicitly
  not used.
- **1 g precision is sufficient.** The business does not trade
  spices by the milligram; 3 dp covers every operational case with
  room to spare.
- **Independent of pack-size choice.** Under Q6 option 1
  (mass-only) every product uses this unit. Under Q6 option 2
  (SKU-per-pack-size), packed products are stocked in **ks** but
  the underlying raw-spice pool is still mass. Under Q6 option 3
  (product-with-variants), the variant stores its mass-per-pack and
  the bulk product (if any) stores in kg. In all three outcomes the
  kg-decimal answer holds for the mass case.
- **Display is separable from storage.** UI components can render
  `0.100 kg` as `100 g` when the natural unit for a pack is grams,
  without changing the stored value.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Every quantity field across the schema can be specified: mass
  fields are NUMERIC(10, 3); count fields (for packed SKUs, if Q6
  goes that way) are INT.
- Recipe ratios can be stored as decimals (e.g. `0.300` for 30 %)
  and produce predictable mass quantities.
- Příjem / výdej / převod UI: quantity input is in kilograms by
  default, with optional grams-display for retail packs.
- Dodací list line format can carry a quantity-in-kg plus an
  optional human-readable rendering (`5 ks × 0.100 kg = 0.500 kg`).
- Catalogue (screens 04, 05) can show per-product stock in kg
  without unit ambiguity.

**Forecloses:**

- Storage in float or in milligrams. Both are off the table.
- Per-product primary-mass-unit choice. The mass unit is global; a
  product cannot opt to be stored in grams. A product can be
  *displayed* in grams via UI logic.
- Sub-gram precision in storage. Anything finer than 1 g is rounded
  on write.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  code* › "Primary unit of measure".

**Affects future decisions:**

- Q4 (Říčany transfer model) — transfer quantities use the same
  mass unit.
- Q5 (mixture recipes) — recipe arithmetic happens in kg with 3 dp;
  recipe ratios as decimals.
- Q6 (pack-size granularity) — orthogonal at the storage layer
  (mass-stored products use kg regardless; ks coexists for packed
  SKUs if Q6 introduces them).
