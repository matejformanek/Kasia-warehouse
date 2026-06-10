# 0006 — Pack-size granularity: product + variant

> **Superseded 2026-06-09 by [`0028-mass-only-supersedes-0006.md`](./0028-mass-only-supersedes-0006.md).**

## Context

This is the most cascading data-model decision in the project, and the
last *Decide before code* item in
[`../open-questions.md`](../open-questions.md). The catalogue
contains the same ingredient (e.g. oregano) presented at several
pack formats — 25 kg bulk sack, ~5 kg / ~10 kg gastro packs, 1 kg
packs, ~100 g retail jars
([`../product-ideology.md`](../product-ideology.md),
[`../company-profile.md`](../company-profile.md)). The system has to
model these without either erasing the ingredient-level identity or
exploding the catalogue into a flat SKU list.

Kasia is described in [`../company-profile.md`](../company-profile.md)
as "an importer, processor, blender, **and packer**" — they take 25
kg bulk and repack into 100 g jars themselves. The schema therefore
has to record **repacking** as a real operation, not as a no-op.

Prior Phase A decisions feed into this one:

- **Q2 (one catalogue across branches)** — product identity is
  global; stock is keyed by `(stock-bearing-row, branch)`.
- **Q3 (kg with 3 dp)** — mass storage is kilograms; counted-by-pack
  storage is `ks`. Both coexist depending on the variant.
- **Q5 (recipes at product level)** — a recipe component references
  a product, not a specific variant.

## Options considered

- **(1) Mass-only.** One catalogue row per ingredient; stock in kg;
  pack format is a free-text annotation on the dodací list line.
  Smallest schema. **Structurally insufficient for Kasia**: cannot
  record repacking (bulk → jars), cannot distinguish a 12-jar sale
  from a 1.2 kg loose sale.
- **(2) SKU-per-pack-size.** Every `(ingredient × pack-format)` is
  its own flat row. ~1500–2000 catalogue entries. Dodací list lines
  map literally; repacking is a movement between two SKUs.
  Catalogue management heavy; product-level identity dissolved.
- **(3) Product + variant.** One product per ingredient; one or
  more variants per pack format; stock lives on the variant. ~600
  product cards, ~1500 variants. Catalogue browses by product;
  expands to variants for stock and pricing.

## Choice

**(3) Product + variant.** The catalogue is structured as:

- **Product** — one row per ingredient (raw spice) or per mixture.
  Holds the ingredient identity: Czech name, `kind`
  (`raw_spice` or `mixture` per Q5), recipe relationship for
  mixtures.
- **Variant** — one row per pack format the product is stocked in.
  At minimum every product has one "bulk / loose" variant
  (`unit = kg`, no pack mass), plus zero-or-more retail or gastro
  pack variants (`unit = ks`, with a `pack_mass_kg` recording the
  mass each pack represents).
- **Stock** — keyed by `(variant, branch)`. There is no stock at
  the product level directly; product-level stock figures are
  aggregates across variants (mass-normalised via the variant's
  `pack_mass_kg`).
- **Movements** (příjem, výdej, převod, future repack, future
  mixing-job consume / produce) — reference a variant. Quantity is
  in the variant's storage unit (kg or ks).
- **Recipes** (per Q5) — recipe components reference a **product**,
  not a variant. The mixing job decides which variant of the
  component to consume from (typically the bulk variant at the
  branch where the job runs).

## Rationale

- **Catalogue ergonomics.** ~600 product cards is digestible; ~2000
  flat SKUs is a list to search through. The "bez školení" line in
  [`../owner-request.md`](../owner-request.md) argues for the
  structure that's easier to browse.
- **Physical reality.** Oregano-the-ingredient is one concept; the
  four packs it ships in are presentations of that concept. The
  variant layer captures presentation without erasing identity.
- **Repacking has a home.** A repack is a single branch-local
  operation that decrements one variant's stock (e.g. bulk) and
  increments another's (e.g. 100 g jar). The movement type can
  ship later — see the open items below — but the schema supports
  it now.
- **Pricing.** Per-variant pricing is the natural model: a 100 g
  retail jar and a 25 kg bulk sack have different per-kg prices.
  Pricing rows attach to variants.
- **Reporting flexibility.** "Top-selling products" sums across
  variants; "stock-out variants" filters at variant level. Both
  reports are reachable.
- **Forward fit with recipes.** Recipes at product level (per Q5)
  remain clean. *Zlaté Kuře* contains "30 % paprika" — meaning the
  paprika product, materialised from whichever variant the mixing
  job draws from.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Catalogue schema:
  - `product` — `(id, kind, name_cs, ...)` with `kind ∈ {raw_spice,
    mixture}`.
  - `variant` — `(id, product_id, label_cs, unit ∈ {kg, ks},
    pack_mass_kg NULL, ...)`. Exactly one bulk variant per stocked
    product is allowed; pack variants have `unit = ks` and a non-null
    `pack_mass_kg`.
  - `stock` — `(variant_id, branch_id, quantity)` with quantity in
    the variant's unit. Mass quantities are NUMERIC(10,3) per Q3;
    count quantities are INT.
- Movement schema: every movement line references a variant and
  carries a quantity in that variant's unit. Šarže (per Q1) is an
  optional column on the movement line.
- `screens/04-katalog-produktu.md` browses by product card; clicking a
  card reveals variants and per-variant stock at each branch.
- `screens/05-detail-produktu.md` shows product-level metadata and a
  variants table with per-variant stock, pricing, and pack details.
- `screens/06-prijem-zbozi.md` — operator picks a variant per line;
  units displayed match the variant.
- `screens/07-vydej-zbozi.md` — same; dodací list line text is
  "12 ks oregano 100 g dóza" via variant label.
- `screens/09-detail-dodaciho-listu.md` — line table shows variant
  label, quantity, unit.
- `screens/12-prevod-do-rican.md` — variant-aware.
- Recipes per [`0005`](./0005-mixture-recipe-model.md) remain
  product-level; the mixing-job logic resolves variant at consume
  time.

**Forecloses (without follow-on decisions):**

- Stock at the product level directly. All stock is on variants.
  Product-level totals are aggregates.
- Mass-only modelling for any product. Even a product that ships
  only in bulk has a bulk variant — the variant layer is universal,
  not opt-in.
- Multiple bulk variants per product. Exactly one bulk variant
  (`unit = kg`, no pack mass). If a product has different bulk
  forms (whole vs ground), those are *separate products*, not
  separate bulk variants of one product.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  code* › "Pack-size granularity model".

**New opens this introduces:**

- **Repack as first-class movement type.** Variants enable
  repacking conceptually; the operational screen and the
  movement-kind enum entry are not designed yet. Add to
  *Decide before MVP* if Phase B confirms the operation is common
  enough to need a dedicated screen, otherwise it can be handled
  via two paired correction movements on `screens/11-uprava-pohybu.md`.
- **Variant pricing model.** Per-variant pricing as a column on the
  variant vs as a separate pricing table with effective dates — not
  decided here. Belongs in the *Decide before MVP* tier; revisit when
  Phase B reaches `screens/05-detail-produktu.md` and `screens/14-nastaveni.md`.
- **Bulk-variant for mixtures.** Mixtures produced by mixing jobs
  enter stock at which variant? Default: the mixture's bulk variant
  (`unit = kg`). If a mixture is sold in a 100 g jar, the jar variant
  is filled by a repack from the bulk variant of the same mixture.
  Confirm in Phase B when revisiting `future-misseni.md`.

**Affects future decisions:**

- All Phase B screen reviews now apply this model. Several screens
  (04, 05, 06, 07, 09, 12) will need light edits to match
  product-vs-variant language.
- Tech-stack selection (post-Phase-C round) — the variant layer
  argues mildly for a relational store with foreign-key constraints
  rather than a document store, but this is not load-bearing for
  the choice.
