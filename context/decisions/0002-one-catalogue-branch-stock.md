# 0002 — One catalogue across branches, branch-specific stock

## Context

Both operating branches — Týniště nad Orlicí and Sezimovo Ústí — run
the full receive → process / blend / pack → issue cycle, with
substantially the same product mix (per
[`../company-profile.md`](../company-profile.md): ~369 raw spices +
~236 VERA GURMET finished goods). The catalogue screens (04, 05) and
the příjem / výdej flows in the round-one scaffold implicitly assumed
one shared catalogue, but the question had not been recorded.

Some ERP modelling treats each warehouse's stock list as its own
catalogue. Listed in [`../open-questions.md`](../open-questions.md)
to make sure the alternative was nodded at, not silently skipped.

## Options considered

- **(a) One catalogue, branch-specific stock.** One row per product
  in the catalogue. Stock figures attach to (product × branch) pairs.
  Catalogue identity is shared; only stock diverges.
- **(b) Separate catalogue per branch.** Each branch curates its own
  list of products. A product carried at both branches exists twice,
  potentially with diverging names, prices, or coding.

## Choice

**(a) One catalogue, branch-specific stock.** The product table is
global; stock is keyed by `(product, branch)`. Catalogue management
is an owner / Karolína responsibility (per
[`../people-and-roles.md`](../people-and-roles.md)), not branch-staff
work.

## Rationale

- The two branches have substantially the same product mix; (b)
  would mean duplicating ~600 catalogue entries with no benefit.
- Pricing, naming, and SKU changes happen in one place under (a).
  Drift between branches is structurally prevented.
- Cross-branch reporting ("total oregano on hand") is a straight
  sum, not a fuzzy reconciliation between two SKU lists.
- Catalogue management belongs to the owner / Karolína in Říčany.
  Per-branch catalogues would force that work into branch staff
  hands, which the access model rejects.
- It is the universal ERP default; the brief gives no reason to
  diverge.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Catalogue screens 04 (`katalog-produktu`) and 05 (`detail-produktu`)
  treat product identity as global. The stock column on 04 and the
  per-branch stock breakdown on 05 are derived from `(product ×
  branch)` lookups.
- Branch view (screen 03) shows the same product names as the other
  branch; only the stock column differs.
- Owner dashboard (screen 02) can sum across branches without
  reconciliation.
- "Filter to products held at this branch" on screen 04 is a
  view-layer concern, not a schema concern. May be added later if
  the catalogue feels noisy at a branch.

**Forecloses:**

- Branch-specific product names, codes, or pricing. If a branch ever
  needs to label a product differently for internal reasons, that is
  a per-branch field added to the global product, not a separate
  catalogue entry.
- "This branch sells X, that branch sells Y, do not show them to each
  other" — there is no catalogue-level segregation between branches.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  code* › "One product across branches, or one per branch?"

**Affects future decisions:**

- Primary unit (Q3) — unit-of-measure lives on the product, applied
  uniformly across both branches.
- Říčany transfer model (Q4) — converging on first-class převod is
  cleaner under shared catalogue: the same product moves from
  branch A to Říčany without identity translation.
- Mixture recipe data model (Q5) — recipes live on the global
  product; both branches share the same recipe for *Zlaté Kuře*.
- Pack-size granularity (Q6) — orthogonal at the catalogue level
  (pack-size is a property of the product or its variants, either
  way shared across branches).
