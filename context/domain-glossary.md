# Domain glossary (CZ ↔ EN)

Authoritative list of domain terms and their spellings. Every Czech word
that appears on a screen, on a generated document, or in a code
identifier-disambiguating comment is defined here. If a term you need is
not in this glossary, add it here before using it.

User-facing surface is Czech. Code identifiers are English. The glossary
is the bridge.

## Documents

### dodací list

**EN:** delivery note.
A document accompanying goods on outbound issue. It lists the items,
quantities, unit prices (or not), batches if recorded, the
buyer/odběratel, and references back to an originating order if any.
In Czech practice the dodací list is **not the same as a faktura
(invoice)**: it is the proof-of-handover, the document that travels
with the goods, and the basis on which the accountant later issues
the invoice. Generating the dodací list is the central act of the
outbound workflow in this system.
*Plural / colloquial:* **dodáky** (used by the owner).
*Synonyms:* delivery note, packing list (loosely; not exactly the same).

### faktura

**EN:** invoice.
The tax document issued by the accountant on the basis of one or more
dodací listy. **Out of scope** for this system — the system feeds the
accountant, it does not invoice.

### výdejka

**EN:** issue note / goods-issue record.
The internal record of a goods issue (výdej). In Czech accounting
parlance, the výdejka is the warehouse-side document; the dodací list
is the customer-side document. Often the same data, two views. In this
system, "výdej" is the verb / event, "výdejka" is the internal record,
"dodací list" is the printable customer-facing artefact.

### příjemka

**EN:** receipt note / goods-receipt record.
The internal record of a goods receipt (příjem). Counterpart to výdejka.

## Inventory mechanics

### skladová evidence

**EN:** stock records / inventory ledger.
The body of records that says what is on hand, where, and how it got
there. The system *is* the skladová evidence for the two branches.

### sklad

**EN:** warehouse / store.
A physical location holding stock. In this system: Týniště nad Orlicí,
Sezimovo Ústí. Říčany is referred to but does not hold tracked stock.
*Synonyms:* pobočka (when the warehouse is also a branch office).

### pobočka

**EN:** branch.
An operating site that is both a warehouse and a workplace. Used
interchangeably with "sklad" for Týniště and Sezimovo Ústí in
day-to-day speech.

### hlavní sklad

**EN:** main warehouse / central warehouse.
Generic Czech term. In Kasia's case there is no central warehouse in
the operational sense — Říčany is HQ but not a stocked main warehouse.
Avoid using this term in the UI to prevent confusion; if used in
documentation, qualify clearly.

### mezisklad

**EN:** intermediate / transit warehouse.
A storage location goods pass through on their way somewhere else.
Not currently modelled in this system; included here so that future
agents recognise the term if the owner uses it.

### drží / nedrží

**EN:** carries / does not carry.
A pobočka **drží** a product iff a `Stock` row exists for that
`(product, branch)` pair; existence of the row IS the carry-flag, per
[`decisions/0053-stock-row-is-branch-carry.md`](./decisions/0053-stock-row-is-branch-carry.md).
Branches that *nedrží* a product do not appear in the catalogue chips,
the per-product detail table, or the daily *Dochází zboží* e-mail.
Vlastník toggles carry-state via Přidat / Odebrat buttons on the
product edit screen; obsluha sees the state read-only.

## Goods

### zboží

**EN:** goods / merchandise.
Generic term for anything the company holds for sale. Covers both raw
spices and finished products.

### koření

**EN:** spice.
A raw single-ingredient spice (e.g. oregano, pepř, paprika).

### směs

**EN:** mixture / blend.
A branded composite product made by combining several raw spices in a
fixed recipe (e.g. *Zlaté Kuře*). Produced by a **mixing job**
(see [`product-ideology.md`](./product-ideology.md)).

### šarže

**EN:** batch / lot.
A traceable production or receipt batch. Used for traceability,
expiry, and recall. Per
[`decisions/0001-sarze-tracking.md`](./decisions/0001-sarze-tracking.md)
the šarže field is **optional** on every movement line and on stock:
operators record when known (typically when the supplier-printed
batch is on the inbound sack) and skip otherwise.

### balení

**EN:** pack / packaging unit.
The physical pack a quantity is sold in: 25 kg sack, 1 kg bag, 100 g
jar. Physical packaging is real but **not modelled in MVP** per
[`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md):
the catalogue is one row per product, stock in kg only. Petr's
2026-06-09 brief: "neřeším druh balení, zajímá mne jen celková
hmotnost".

### varianta

**EN:** variant (pack variant).
**Not modelled in MVP** per
[`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md);
every product is one row, stock in kg. The term is retained here so
readers recognise it if a future decision reintroduces pack-level
modelling. The earlier
[`decisions/0006-pack-size-product-variant.md`](./decisions/0006-pack-size-product-variant.md)
landed a `Variant` table; that decision is superseded by
[`0028`](./decisions/0028-mass-only-supersedes-0006.md).

### přebalení (přebal)

**EN:** repack.
The physical operation of decanting bulk into retail packs. **Out
of scope** per
[`decisions/0033-prebalovani-out-of-scope-supersedes-0013.md`](./decisions/0033-prebalovani-out-of-scope-supersedes-0013.md):
Petr's 2026-06-09 brief — "přebalování vůbec nemusíme řešit". Not
modelled (Kasia still physically repacks; the system simply does
not record the act, and per
[`0028`](./decisions/0028-mass-only-supersedes-0006.md) total kg is
unchanged before and after a repack anyway).

### recepturní složka

**EN:** recipe component / formula ingredient.
A line of a mixture's recipe: (raw spice, ratio). E.g. "Zlaté Kuře
contains paprika 30 %, sůl 20 %, …".

### výrobní dávka

**EN:** production batch / mixing batch.
One execution of a mixing job: consumed N kg of source spices to
produce M kg of mixture, on date D, at branch B.

## Movements

### příjem

**EN:** goods receipt (verb / event).
Stock arrives at a branch from a supplier (or, in future, from a
transfer). Records a positive movement against branch stock.

### výdej

**EN:** goods issue (verb / event).
Stock leaves a branch — to a customer (with dodací list) or to
Říčany (transfer). Records a negative movement against branch stock.

### naskladnění

**EN:** stocking in / putting away.
Common informal term for příjem; sometimes used to emphasise the
physical act of placing goods on the shelf as distinct from the
paperwork of příjem. In this system, treat as a synonym for příjem
unless context demands otherwise.

### vyskladnění

**EN:** stocking out / picking.
Common informal term for výdej. Same caveat as naskladnění.

### převod

**EN:** transfer.
**Narrowed in MVP** per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md):
not a distinct movement type. An internal převod is just a **výdej
where the odběratel is Říčany** (the seeded default-selected
`Customer` row). The dodací list and the internal Petr+Karolína
e-mail per
[`0031`](./decisions/0031-emails-internal-only-supersedes-0009.md)
still fire on a Říčany výdej. There is no paired inbound (Říčany
is not a tracked location per
[`warehouses.md`](./warehouses.md)). Whether branch ↔ branch
převody exist is tabled.

### rezervace

**EN:** reservation / allocation.
Earmarking stock for a pending issue. **In MVP via
[`decisions/0044-reservations-planned-states.md`](./decisions/0044-reservations-planned-states.md)**
for two specific sources: PLANNED míchací dávka (a recipe queued to be
mixed later — raw spices count as reserved at the source branch) and
PLANNED *převod mezi pobočkami* (an inter-branch transfer scheduled for
a future date — quantity counts as reserved at the source branch).
Reservations are **outgoing-only**: incoming planned transfers do NOT
add to the target branch's effective stock. They are informational —
they surface in `effective_kg = Stock.quantity − reserved_kg` on the
dashboard, product detail, and daily summary e-mail (per 0045), but
do not gate the existing overdraw check on výdej. (Spelling note:
glossary uses **rezervace**; the brief uses "reservace" — treat that as
a typo and prefer "rezervace" as the standard Czech spelling.)

### objednávka

**EN:** (planned) order. *Verb:* **objednat** (to order). *Status:*
**objednáno** (ordered).
A recorded intention to receive an inbound delivery of goods to one branch,
with an **očekávaný příjezd** (expected arrival date). Per
[`decisions/0059-merge-objednavka-into-prijem.md`](./decisions/0059-merge-objednavka-into-prijem.md)
an objednávka is now a **plánovaný příjem** — a `Movement` with
`status=planned, kind=prijem` (multi-line, like any příjem), **not** a
separate model. It is created from the *příjem* form by entering a future
**Příjezd** date (supersedes the standalone `/sklad/objednavky/` page of 0057).
A PLANNED příjem is **informational only** — like **rezervace** above, it does
NOT change effective stock or the deficit; it surfaces as an `Objednáno` badge
on the low row. Confirming arrival ("Přijmout", from **Historie → Plánované**)
adjusts per-line quantities to what actually arrived (a 0-qty line is dropped),
flips the Movement to `status=done`, and adds the received kilograms to the
branch's sklad. (Legacy note: the retired 0057 `PlannedOrder` model is kept
read-only for historical rows.)

### očekávaný příjezd

**EN:** expected arrival (date).
The date an **objednávka** (plánovaný příjem) is expected to arrive at the
branch. Stored on `Movement.expected_on` (NULL on ordinary DONE movements;
required on a PLANNED příjem). Purely informational — arrival is confirmed
manually (anyone logged in), never auto-applied on this date.

### objednací bod

**EN:** reorder point / reorder threshold.
Per-product (and optionally per-branch) kilogram quantity below which
the system flags the (product, branch) pair as "dochází" on the
dashboard and on the daily summary e-mail to Petr. Stored on
`Product.reorder_threshold_kg` with optional `StockThresholdOverride`
rows for branch-specific values per
[`decisions/0043-reorder-threshold.md`](./decisions/0043-reorder-threshold.md).
`NULL` means "no threshold set, do not alert"; `0` means "alert at
literal empty". Comparison is against *effective* stock, not raw
`Stock.quantity` — see **rezervace** above.

## Stock-take and reconciliation

### inventura

**EN:** stock-take / physical inventory.
Periodic physical count of what's on the shelf, compared against the
ledger. Workflow shape (full inventura? rolling? per-shelf?) is open.

### manko

**EN:** shortage.
Negative reconciliation: ledger says N, shelf has less than N.

### přebytek

**EN:** surplus / overage.
Positive reconciliation: ledger says N, shelf has more than N.

### hlášení

**EN:** feedback / report.
A user-submitted report on the `/podpora/` support page —
typically a bug, question, or feature wish. Stored as
`inventory.Feedback` per
[`decisions/0046-support-page.md`](./decisions/0046-support-page.md).
Visible to all logged-in users; vlastník can mark resolved /
re-open. Free-form Czech text with an optional `page_url` hint.

### odpis

**EN:** write-off.
Removing stock from the ledger because it is unsellable
(damaged, expired, spilled). Whether to make this a first-class
movement type is an open question.

*Synonym:* **skartace** is used colloquially for destruction of
unsellable goods; in this system treat as an instance of odpis with
reason = "destroyed".

## Units

### jednotka, MJ (měrná jednotka)

**EN:** unit of measure (UoM).
The unit in which a quantity is expressed. The candidate units in
this domain are:

- **kg** — kilogram (bulk-trade default)
- **g** — gram (retail and recipe-component default)
- **ks** — kus / piece (used for fully packaged goods sold by count,
  e.g. "12 ks dóziček 100 g")

Per
[`decisions/0003-primary-unit-kg-decimals.md`](./decisions/0003-primary-unit-kg-decimals.md)
the **primary mass unit** is **kg with three decimal places**
(NUMERIC(10,3), 1 g precision). Per
[`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md)
every product's stock is in **kg only** in MVP — there is no `ks`
storage. `ks` is **reserved** for possible future use (if a Variant
layer is ever reintroduced); nothing in MVP uses it.

## Pricing

### cena

**EN:** price (unit price).
The unit price of a product. **Not stored** in this system per
[`decisions/0029-no-prices-supersedes-0011.md`](./decisions/0029-no-prices-supersedes-0011.md):
Petr's 2026-06-09 brief — "ceny nikde nechci". The headword is kept
in the glossary because readers will encounter the term in everyday
Czech and need to know the system deliberately doesn't track it.
Prices live in the účetní's software, on the basis of dodací listy
the system produces.

## Parties

### odběratel

**EN:** customer / buyer / off-taker.
The B2B reseller to whom goods are issued on a dodací list. Has name,
IČO, DIČ, billing/delivery address.

### dodavatel

**EN:** supplier.
The upstream party from whom raw spice is received on příjem.

### IČO

**EN:** business identification number (Czech, 8 digits).
Required on dodací list for the odběratel. Kasia vera's own IČO:
25756729.

### DIČ

**EN:** tax identification number / VAT number (Czech, "CZ" + IČO
for most domestic entities, but not always).
Required on dodací list. Whether DIČ is mandatory on every line of
the system or only on the printed PDF is an open detail.
