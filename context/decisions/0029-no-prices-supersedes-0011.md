# 0029 — No prices anywhere (supersedes 0011)

## Context

Petr's 2026-06-09 reply (Czech, relayed via Matej):

> "Ceny nikde nechci."

[`0011-variant-pricing-single.md`](./0011-variant-pricing-single.md)
landed a single nullable `cena` column per variant, kept internal-only
per [`0010-prices-on-dodaci-list.md`](./0010-prices-on-dodaci-list.md).
The reasoning was that storage was cheap (one nullable column) and
the účetní might later want it on an export. Petr's reply removes
even that optionality: he does not want prices in the system at all.

Reinforced by Petr's other line in the same reply:

> "Apku potřebuji primárně pro svůj přehled o stavech zásob, nemá
> žádný účetní význam."

The app is not an accounting tool; prices belong to the účetní's
software, not to ours.

This decision supersedes
[`0011`](./0011-variant-pricing-single.md).

## Options considered

- **(a) Keep a single nullable `cena`** per
  [`0011`](./0011-variant-pricing-single.md). Defaults to null;
  invisible in UI; internal-use only. Petr's "nikde nechci" rules
  this out — even invisible storage counts as "in the system".
- **(b) Remove the column entirely.** No `cena` field on any model
  (Product, Stock, MovementLine, DodaciList). Prices never appear in
  UI, PDF, e-mail, audit, or export.

## Choice

**(b) No price field anywhere.** No `cena` column on `Product`, no
`unit_price` on `MovementLine`, no `total` on `DodaciList`. The PDF
dodací list shows lines as `(product, quantity_kg, optional šarže,
optional note)`, no price column and no document total. The
accountant gets price information from her own systems on the basis
of dodací listy (which she already does — per
[`workflows.md`](../workflows.md), Karolína forwards dodáky to the
účetní and the účetní issues fakturu separately).

## Rationale

- **Petr's instruction is unambiguous.** "Ceny nikde nechci" — no
  hedge, no exception.
- **No operation requires it.** Per
  [`0028`](./0028-mass-only-supersedes-0006.md) the catalogue is one
  row per product in kg; there is no per-pack pricing question. Per
  [`0010`](./0010-prices-on-dodaci-list.md) the dodací list already
  carries no prices. Per
  [`workflows.md`](../workflows.md) the účetní handles fakturace
  outside the system.
- **Cheapest schema.** No nullable column to keep migrating, no UI
  field to keep hidden, no export decision to defer.
- **Reversible cheaply.** If Petr ever changes his mind, a future
  decision adds `Product.cena` as a nullable column without
  back-filling history. The cost is bounded.
- **(a) is tempting** because zero-cost storage is cheap, but it
  contradicts Petr's instruction and re-opens the export question
  that [`0011`](./0011-variant-pricing-single.md)'s Affects-future
  section left dangling.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The next models pass writes `Product` without a `cena` field.
- Screens 04 (catalogue) and 05 (detail) drop all price columns and
  inputs.
- The PDF dodací list and screen 09 line table have no price column,
  no line total, no document total.
- The accountant export (if/when ever scoped — see
  [`open-questions.md`](../open-questions.md) § Accountant export
  format) carries no price field.

**Forecloses (without follow-on decisions):**

- Any UI showing a unit price, line total, or dodák total.
- Any export including price columns.
- Any future "per-customer price" or "price history" feature — these
  remain reachable but require a fresh decision plus schema work,
  not a flip of an existing column.

**Supersedes:**

- [`0011-variant-pricing-single.md`](./0011-variant-pricing-single.md).
  The "Variant pricing model" open from
  [`0006`](./0006-pack-size-product-variant.md) is now resolved by
  *not having one* — Petr does not want prices at all, separately
  from the variant question handled by
  [`0028`](./0028-mass-only-supersedes-0006.md).

**Affects future decisions:**

- The accountant export deferral (2026-06-03) is unaffected — when
  the export ships, it carries no prices.
- [`0010-prices-on-dodaci-list.md`](./0010-prices-on-dodaci-list.md)
  remains in force; this decision strengthens it by removing the
  underlying field, not just hiding it.
