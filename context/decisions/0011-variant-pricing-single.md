# 0011 — Variant pricing: single nullable price per variant

> **Superseded 2026-06-09 by [`0029-no-prices-supersedes-0011.md`](./0029-no-prices-supersedes-0011.md).**

## Context

[`0006-pack-size-product-variant.md`](./0006-pack-size-product-variant.md)
introduced the variant layer and explicitly left the variant pricing
model open as a *Decide before MVP* item. The same open shows up on
[`screens/05-detail-produktu.md`](../screens/05-detail-produktu.md)
and [`screens/14-nastaveni.md`](../screens/14-nastaveni.md) under
their § Open questions.

[`0010-prices-on-dodaci-list.md`](./0010-prices-on-dodaci-list.md)
already settled that **prices do not appear on the dodací list in
MVP** — the variant's price is an internal field only. The question
remaining is the *shape* of that internal field: a single price per
variant, or a richer pricing structure (price-list rows with
effective dates, per-customer prices, etc.).

Kasia's actual operation is a single-tier B2B distribution. Pricing
across customers is handled externally by the účetní (per
[`../people-and-roles.md`](../people-and-roles.md)); fakturace lives
outside this system. The first tech decision (`0014+`) cannot land
until the pricing slot is settled, because it changes the variant
schema.

Matej is acting as Petr's stand-in for this close-out (per the
2026-06-04 design-phase sign-off; Petr is hard to reach
asynchronously, so Matej accepts the residual rework risk).

## Options considered

- **(a) Single nullable `cena` column on the variant.** One price
  per variant, optional. No history. No per-customer pricing. No
  effective dates. Internal use only. Smallest possible schema.
- **(b) Separate price-list table** with `(variant, effective_from,
  cena)` rows. Historical prices kept; "what was this priced at on
  date X" is answerable. No per-customer split.
- **(c) Full price-list with per-customer overrides** —
  `(variant, customer NULL, effective_from, cena)`. Per-customer
  contract pricing. Heaviest schema, biggest UI surface.

## Choice

**(a) Single nullable `cena` column on the variant.** One price
per variant. Nullable — a variant with no price set simply has no
internal reference price. No history table, no per-customer
override, no effective dates.

Per [`0010`](./0010-prices-on-dodaci-list.md), the field is
**internal-only** in MVP: it does not appear on the dodací list,
on the výdej preview, on the seznam dodacích listů, or on the PDF
template. It can inform an accountant export (per
[`../screens/future-export-uctarne.md`](../screens/future-export-uctarne.md))
if the účetní asks for it, but that's a separate decision.

## Rationale

- **Matches the operation.** Kasia's pricing is one-tier; the účetní
  manages customer-specific pricing externally. Building (b) or (c)
  to model what doesn't happen would be over-engineering.
- **Cheapest schema.** One nullable column on the variant table. No
  join, no history maintenance, no UI for price changes.
- **Schema can grow.** If a future requirement makes per-customer or
  time-varying pricing real, we add a `variant_price` table without
  touching the variant row — the existing `variant.cena` becomes the
  "default" feeding the new table. No data migration of historical
  movements.
- **(b) was tempting** but adds a UI surface (history of price
  changes) that nobody asked for. Defer until somebody does.
- **(c) is enterprise-shaped** and contradicts
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md).

## Date & by-whom

2026-06-04 — Matej (acting as Petr's stand-in for the design-phase
close-out).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Variant schema: `variant.cena NUMERIC(…, 2) NULL` (precision /
  scale follows from the tech-stack decision in `0014+`; the
  decimals choice is unrelated to the kg precision in
  [`0003`](./0003-primary-unit-kg-decimals.md)).
- `screens/05-detail-produktu.md` — the per-variant `cena` field is
  a single editable input on the variant row. No "history" or
  "effective from" controls.
- `screens/14-nastaveni.md` — the *Variant pricing model* open
  question is closed; the only remaining Settings open is logo
  files (closed below).
- The first tech decision (`0014+`) can proceed without ambiguity
  on the variant schema shape.

**Forecloses (without follow-on decisions):**

- Per-customer pricing on the dodací list.
- Price history / "what was oregano 100 g priced at last September".
- Effective-dated price changes.
- Time-varying price reports.

All of the above remain reachable via a future decision plus a new
table; none require rewriting the variant row.

**Resolves:**

- The *Variant pricing model* open from
  [`0006`](./0006-pack-size-product-variant.md) § New opens.
- The *Variant pricing model* open on
  [`../screens/05-detail-produktu.md`](../screens/05-detail-produktu.md)
  § Open questions for this screen.
- The *Variant pricing model* open on
  [`../screens/14-nastaveni.md`](../screens/14-nastaveni.md)
  § Open questions for this screen.

**Affects future decisions:**

- Accountant export format (deferred 2026-06-03) — if the účetní
  wants prices on the export, `variant.cena` is the source.
- Any future *priced dodací list* decision would supersede
  [`0010`](./0010-prices-on-dodaci-list.md), not this one — the
  variant schema set here is forward-compatible.
