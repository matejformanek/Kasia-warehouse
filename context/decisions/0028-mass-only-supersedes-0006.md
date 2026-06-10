# 0028 — Mass-only catalogue (supersedes 0006)

## Context

Petr replied directly on **2026-06-09** (Czech, relayed via Matej) and
materially narrowed the design from where the residual close-out had
landed it. Verbatim:

> "Apku potřebuji primárně pro svůj přehled o stavech zásob, nemá
> žádný účetní význam. Neřeším druh balení, zajímá mne jen celková
> hmotnost. Katalog cca 20–30 položek na pobočku."

[`0006-pack-size-product-variant.md`](./0006-pack-size-product-variant.md)
chose **product + variant** on the assumption Kasia actively repacks
at schema grain and needs to distinguish 25 kg sacks from 100 g jars
in the ledger. Petr's reply explicitly removes that assumption: pack
format is not interesting for *his* visibility need, and the catalogue
is far smaller than the ~600 products the variant model was sized for.
Combined with [`0029`](./0029-no-prices-supersedes-0011.md) (no prices)
and [`0033`](./0033-prebalovani-out-of-scope-supersedes-0013.md)
(no přebalování), the entire variant layer's reason to exist
disappears.

This decision supersedes
[`0006`](./0006-pack-size-product-variant.md).

## Options considered

- **(1) Keep product + variant.** Status quo per
  [`0006`](./0006-pack-size-product-variant.md). Costs: ~3× the schema
  surface (Product + Variant + per-variant Stock + variant pickers on
  every movement screen), no current operation needs the variant
  distinction.
- **(2) Mass-only — one row per product, stock in kg.** Smallest
  possible schema. Petr's stated need ("celková hmotnost") maps 1:1.
  Loses the ability to record "12 ks dóziček 100 g" as 12 jars; only
  records 1.2 kg.
- **(3) Mass-only with optional `pack_note` free-text on movement
  line.** Same as (2) plus a free-text annotation if the operator
  wants to record the pack format informally. Costs almost nothing
  more than (2).

## Choice

**(2) Mass-only.** The catalogue is **one row per product, stock in
kg only**. There is no `Variant` table, no `pack_mass_kg`, no `ks`
unit in MVP. Every quantity field — stock, movement line, recipe
component, future mixing job — is in kilograms with the precision
established in
[`0003-primary-unit-kg-decimals.md`](./0003-primary-unit-kg-decimals.md)
(`NUMERIC(10,3)`).

The `jednotka` glossary entry retains `ks` as a *reserved* unit
label for possible future use; nothing in MVP uses it.

## Rationale

- **Matches Petr's stated need.** "Zajímá mne jen celková hmotnost" is
  unambiguous. Building variant infrastructure to record what Petr
  does not want to see is over-engineering against the brief.
- **Catalogue scale is small.** ~20–30 items per branch (Petr's
  number) means a flat product table is trivially browsable; the
  variant model's ergonomic gains over a flat list don't apply.
- **Cascading simplifications.** Removes variant pickers from screens
  06, 07, 09, 10, 11. Removes the bulk-vs-pack rule from screen 05.
  Removes the mass-normalisation logic from screens 02, 03, 04.
  Removes the variant-aware filtering from screen 04. Each was
  cheap individually; together they're a meaningful surface cut.
- **Aligns with [`0029`](./0029-no-prices-supersedes-0011.md) and
  [`0033`](./0033-prebalovani-out-of-scope-supersedes-0013.md).** With
  no prices and no přebalování, the operations the variant layer was
  designed to support — per-pack pricing and source→target repacks —
  do not exist in MVP.
- **Forward path is clean.** If Petr later wants to track pack
  formats, a `Variant` table can be introduced as an additive layer:
  existing `(product, branch)` stock becomes the "bulk variant" stock,
  new pack variants attach to the product. No destructive migration
  of historical movements. The cost of being wrong here is bounded.
- **Kasia still physically repacks** ([`company-profile.md`](../company-profile.md)
  describes Kasia as a packer). That stays true in the warehouse; we
  just don't model it. The accountant doesn't need the model and
  Petr's stock-visibility need doesn't either.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Simpler catalogue schema:
  - `product (id, kind, name_cs, is_active, ...)` — `kind ∈ {raw_spice,
    mixture}` per
    [`0005`](./0005-mixture-recipe-model.md), unchanged.
  - `stock (product_id, branch_id, quantity)` — quantity in kg,
    `NUMERIC(10,3)` per
    [`0003`](./0003-primary-unit-kg-decimals.md).
- Movement lines reference a **product** directly:
  `(product_id, quantity_kg, sarze NULL, expiry NULL, note NULL)`.
- Screens 02, 03, 04, 05, 06, 07, 09, 10, 11 drop variant pickers,
  variant labels, variant counts, mass-normalisation aggregates.
- The recipe model
  ([`0005-mixture-recipe-model.md`](./0005-mixture-recipe-model.md))
  is unchanged structurally — components were already at product
  grain. The "consumed variant at mixing-job time" question goes
  away (there is only the product's kg pool).

**Forecloses (without follow-on decisions):**

- Recording stock at pack grain (e.g. "12 ks dóza 100 g"). Until a
  future decision reintroduces a Variant layer, this information is
  not in the system.
- Per-pack pricing (already foreclosed by
  [`0029`](./0029-no-prices-supersedes-0011.md), which removes
  prices entirely).
- The "one bulk variant per product" invariant from
  [`0006`](./0006-pack-size-product-variant.md) — no longer needed
  because there are no variants.

**Supersedes:**

- [`0006-pack-size-product-variant.md`](./0006-pack-size-product-variant.md).
  All variant-layer language in
  [`0006`](./0006-pack-size-product-variant.md)'s Consequences and
  Affects-future sections becomes inapplicable. The historical
  reasoning in [`0006`](./0006-pack-size-product-variant.md) (Kasia
  repacks; we want product-level identity preserved) is preserved
  for the trail — what changed is that Petr does not want repacking
  modelled in MVP.

**Affects future decisions:**

- The next models pass writes `Product` + `Stock` directly; no
  `Variant`.
- [`0005`](./0005-mixture-recipe-model.md) § Affects-future ("variants
  attach to mixture") becomes inapplicable; the recipe model itself
  (component product + ratio rows, snapshot at job start) is
  unchanged.
- A future decision can reintroduce a Variant layer as additive
  without rewriting `stock` — the existing `(product, branch)` row
  becomes "bulk".
