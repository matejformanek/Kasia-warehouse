# 0010 — Prices on dodací list (MVP)

## Context

The brief in [`../owner-request.md`](../owner-request.md) **does not
mention prices**. It describes the dodací list as the
goods-issued-with document that the accountant turns into a faktura.
The accountant (external) is the entity that calculates and issues
the priced invoice.

[`decisions/0006-pack-size-product-variant.md`](./0006-pack-size-product-variant.md)
provides for an optional unit price on the variant.

The pricing-on-dodací-list question was open in
[`../open-questions.md`](../open-questions.md) as a *Decide before
MVP* item.

## Options considered

- **(a) Dodací list does NOT show prices in MVP.** Variant has an
  optional `unit_price` field for future use (internal cost tracking,
  later opt-in to priced dodáky), but the PDF template renders only
  quantity, unit, variant label, and optional šarže / note. The
  accountant works from a separate price list as today.
- **(b) Dodací list shows prices when the variant has them set.**
  Lines with priced variants render quantity × unit price = line
  total; lines without prices render qty + unit only. The PDF shows
  a money column when any line has a price.
- **(c) Dodací list shows prices mandatorily.** Every variant must
  have a unit price; výdej is blocked for any variant without a price.
  Full priced dodáky from day one.

## Choice

**(a) Dodací list does NOT show prices in MVP.** The variant schema
carries an optional `unit_price` field (for internal use and future
expansion), but the PDF template renders dodací list lines as:

- Variant label (e.g. "Oregano · 100 g dóza" or "Oregano · sypké").
- Quantity in the variant's unit.
- Optional šarže.
- Optional per-line note.

No money column. No line totals. No dodák total. The accountant
calculates the faktura from their existing price list / contract with
the customer.

This is **reversible by a template change, not a schema change**: if
Petr decides the dodací list should show prices, the template gains a
"Cena" column that reads from `variant.unit_price`, and that's it.

## Rationale

- **Brief is silent on prices.** Adding a price column requires
  assumptions about which prices, how they update, whether they
  differ by customer, whether VAT shows, etc. — none of which Petr
  asked for.
- **Karolína's existing pipeline already feeds the accountant.** The
  accountant already manages pricing. Doubling pricing into the
  dodací list creates a synchronisation burden and a new source of
  truth conflict.
- **Schema preserves optionality.** The optional `unit_price` on the
  variant per
  [`decisions/0006`](./0006-pack-size-product-variant.md) is kept;
  this decision only governs the PDF rendering.
- **(b) is reasonable but adds a UX surface** (price entry on every
  variant, exception handling on existing variants without prices)
  that the brief does not call for.
- **(c) is over-reach** and would block výdeje until every variant is
  priced, which is a setup task Petr has not been asked to do.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The PDF template can be drafted without a price column. The
  template is otherwise governed by a separate *Decide before MVP*
  decision when `screens/14-nastaveni.md` is reviewed.
- `screens/07-vydej-zbozi.md` — the dodací list preview block does
  not render prices; lines show variant + qty + unit + optional
  šarže + optional note.
- `screens/08-seznam-dodacich-listu.md` — no per-row money figure.
  The open question about "small per-row money figure" is closed: no.
- `screens/09-detail-dodaciho-listu.md` — PDF and the on-screen
  lines block are pricless. The "Editováno" banner remains, audit
  for re-sends remains.
- `screens/05-detail-produktu.md` — the per-variant `unit_price`
  field remains optional and is for internal use only in MVP. Its
  purpose can be revisited when the broader pricing model question
  comes up.

**Forecloses (without follow-on decisions):**

- Customer-specific dodací list pricing.
- VAT / DPH columns on the dodací list.
- Discount lines on the dodací list.

All of the above remain reachable via a future decision and template
change; none are in MVP.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  MVP* › the implicit pricing slot mentioned under "PDF template"
  and on `screens/07-vydej-zbozi.md` / `screens/08-seznam-dodacich-listu.md`.
- The pricing-on-dodací-list paragraph in
  [`../workflows.md`](../workflows.md).

**Affects future decisions:**

- PDF template (still open) — drafted *without* a price column.
- Variant pricing model (still open per
  [`decisions/0006`](./0006-pack-size-product-variant.md)) —
  becomes purely internal (catalogue / future repricing UI) in MVP.
- Accountant export (still open) — the export can still carry the
  internal `unit_price` if useful for the accountant's own price-list
  reconciliation; that decision is on
  `screens/future-export-uctarne.md`.
