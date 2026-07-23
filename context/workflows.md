# Workflows

End-to-end narrative description of how work flows through the system.
Each workflow names the screens it touches; the screen files live under
[`screens/`](./screens/) and are written in parallel — forward references
are intentional.

Workflows here are descriptive of intent, not normative on UI sequencing.
The screens are authoritative on what is on each page.

## Inbound — goods arrive at a branch

A truck pulls up at Týniště nad Orlicí or Sezimovo Ústí carrying spice
from a supplier. Branch staff unload, check the delivery against the
supplier's paperwork, and open the system to record a **příjem**.

In the system, the operator selects the receiving branch (in practice
fixed to "their" branch by their account scope), picks the dodavatel,
chooses one or more items from the catalogue, enters the received
quantity per item (in the item's unit of measure), and saves. Stock at
that branch goes up; a příjem movement record is written.

Screens involved: `screens/06-prijem-zbozi.md` (the receipt form),
`screens/04-katalog-produktu.md` (item picker), `screens/10-historie-pohybu.md`
(where the resulting movement appears).

Edge cases noted but not yet specified:

- Receipt where the supplier paperwork lists different quantities than
  what was actually delivered. Default expectation: record what was
  delivered, not what was on paper, and rely on the correction
  workflow if needed afterwards.
- Receipt of a brand-new spice not yet in the catalogue. The operator
  must be able to add it inline, or the workflow stalls.
- **Šarže** (batch) is optional per
  [`decisions/0001-sarze-tracking.md`](./decisions/0001-sarze-tracking.md):
  the operator records šarže (and optional expiry) per line when the
  supplier-printed batch is available, skips otherwise.
- Receipt is recorded for a specific **product** per
  [`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md),
  in **kg only**. Pack format is not tracked in MVP.

## Outbound — issue, dodací list, email

The trigger for this workflow is external: a B2B customer phones or
emails the branch with an order. That conversation is **outside the
system** — the system does not accept customer orders, does not have a
sales-order screen, does not have a customer login. Order intake stays
on phone/email as today.

Once the order is agreed, branch staff open the system, start a
**výdej** at their branch, pick the **odběratel** from the customer
list, add one or more items with quantities, and confirm. On
confirmation the system:

1. Decrements branch stock for each line.
2. Writes a výdej movement record (the internal výdejka).
3. Creates the **dodací list** in state **"čeká na odeslání"**
   (`send_state=WAITING`) — but **sends no e-mail yet** (per
   [`decisions/0096-manual-first-send-of-dodaky.md`](./decisions/0096-manual-first-send-of-dodaky.md)).
   The operator lands on the dodák detail with a "Čeká na odeslání"
   banner.

The operator reviews (and if needed edits) the dodák — **no e-mails go
out while it is WAITING; edits just re-generate the PDF, no version
bump**. When they are sure, they click **"Odeslat e-mail zákazníkovi"**.
Only that click renders the PDF and e-mails it to the dodák recipients +
the issuer, flipping the dodák to **"odesláno"** (`SENT`). A prominent
**"Čeká na odeslání"** list on the dodák index, the owner Přehled, and
the branch dashboard makes sure a pending send is never forgotten.

Karolína then forwards the email to the external accountant, who
issues the faktura. Invoicing is **not** part of this system.

Screens involved: `screens/07-vydej-zbozi.md` (the issue form, which
folds the customer picker inline for MVP — no standalone customer
screen yet), `screens/08-seznam-dodacich-listu.md` (delivery notes
list), `screens/09-detail-dodaciho-listu.md` (delivery note detail
with PDF preview and re-send), `screens/10-historie-pohybu.md`
(history).

Edge cases:

- The customer wants partial delivery or split shipments. Default
  expectation: one výdej = one dodací list; partial deliveries
  generate two výdeje and two dodáky.
- The first send fails. The dodák stays **WAITING** (not SENT) so it
  remains in the "Čeká na odeslání" list and the operator simply clicks
  Odeslat again. (Only an *already-sent* dodák whose later [OPRAVA]
  re-send fails is surfaced on
  [`02-prehled-vlastnik.md`](./screens/02-prehled-vlastnik.md) under
  "K vyřešení" — a WAITING+failed dodák lives in "Čeká na odeslání"
  instead.) Either way the dodací list exists and is re-emailable from
  the detail screen.
- Dodací list shows **no prices** per
  [`decisions/0029-no-prices-supersedes-0011.md`](./decisions/0029-no-prices-supersedes-0011.md):
  no `cena` field anywhere on the product, no unit price on the
  line, no line total, no dodák total. Per
  [`decisions/0031-emails-internal-only-supersedes-0009.md`](./decisions/0031-emails-internal-only-supersedes-0009.md)
  the dodák e-mail goes only to Petr + Karolína from Nastavení —
  never to the customer.

## Branch → Říčany transfer (internal výdej)

The owner asks for material at HQ — a sample, office consumption,
something to dispatch from Říčany. A branch operator opens
[`screens/07-vydej-zbozi.md`](./screens/07-vydej-zbozi.md) and
records a normal výdej. Per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)
**Říčany is the default-selected odběratel** — the operator
typically does nothing in the picker. The výdej decrements branch
stock just like any other; the dodák PDF and the internal
Petr+Karolína e-mail per
[`decisions/0031-emails-internal-only-supersedes-0009.md`](./decisions/0031-emails-internal-only-supersedes-0009.md)
fire as on every výdej. There is **no paired inbound** at Říčany
per [`warehouses.md`](./warehouses.md).

Screens involved: `screens/07-vydej-zbozi.md` (the issue form),
`screens/03-prehled-pobocky.md` (entry point),
`screens/10-historie-pohybu.md` (the movement shows as `výdej`
with odběratel = Říčany).

Edge cases:

- Branch ↔ branch transfers: tabled per
  [`open-questions.md`](./open-questions.md) — Petr's brief did
  not mention them. Operationally handled today as a pair of
  manual výdej + příjem rows.

## Owner correcting a historical entry

The owner (or Karolína) discovers that a movement is wrong — wrong
quantity, wrong item, wrong customer, wrong date. They open the
movement history, find the entry, and edit it.

The system must **not** silently overwrite. Instead it writes an
**audit-trail record** capturing: the original field values, the new
field values, who made the change, the timestamp, and a short
free-text **reason** the editor is required to enter. The corrected
movement then reflects the new values; the history shows that it was
edited; an audit log lists all corrections.

Where the corrected movement is a výdej whose dodací list **has already
been sent** (`SENT`), the system **auto-regenerates the PDF and
auto-emails the updated version** to the recipients per
[`decisions/0007-auto-reissue-corrected-dodaky.md`](./decisions/0007-auto-reissue-corrected-dodaky.md).
The subject is prefixed `[OPRAVA]`; the body names the change reason. If
the dodák is **still WAITING** (never sent), the edit only re-generates
the PDF — **no version bump, no e-mail** — because the operator's first
"Odeslat" click will issue the finished v1 (per
[`decisions/0096-manual-first-send-of-dodaky.md`](./decisions/0096-manual-first-send-of-dodaky.md)).
A per-dodák version+send audit table on
[`09-detail-dodaciho-listu.md`](./screens/09-detail-dodaciho-listu.md)
records every PDF version emitted and when it was sent.

Screens involved: `screens/10-historie-pohybu.md` (history list),
`screens/11-uprava-pohybu.md` (movement detail + edit + per-movement
audit trail — the audit log is surfaced inline rather than on a
separate screen for MVP),
`screens/09-detail-dodaciho-listu.md` (the version/send audit when a
correction affects a previously-sent dodák).

## Míchání směsi (mixing job)

In MVP per
[`decisions/0032-mixing-in-mvp.md`](./decisions/0032-mixing-in-mvp.md)
(Petr's 2026-06-09 brief: ~25 mixtures, ≤15 components each).
Branch staff (or owner-level users) open
[`screens/15-michani.md`](./screens/15-michani.md), pick a mixture
product (`kind = mixture`), set a target produced quantity in kg,
and run the job. The job consumes the component products in the
ratios from the recipe per
[`decisions/0005-mixture-recipe-model.md`](./decisions/0005-mixture-recipe-model.md)
(snapshot at job start; actual consumed may differ from target;
opt-in source-batch traceability per
[`decisions/0001-sarze-tracking.md`](./decisions/0001-sarze-tracking.md))
and produces mixture stock on the mixture product's
`(product, branch)` row in kg per
[`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md).

**Recipe creation:** a mixture's recipe (the RecipeComponent rows
that govern míchání consumption) can be created two ways:
manually at `/katalog/novy/` + inline recipe editor on the product
form, **or** by uploading an Excel recipe at `/katalog/import-xls/`
per [`decisions/0048-xls-recipe-importer.md`](./decisions/0048-xls-recipe-importer.md)
([`screens/17-xls-import.md`](./screens/17-xls-import.md)). The
XLS importer is vlastník-only and writes the new mixture Product
plus its components in one atomic transaction.

## Not in MVP, but documented for the future

- **Accountant export.** Periodic export of dodací listy and/or
  movements in a format the účetní can ingest (CSV, Pohoda XML,
  or other). Today the manual email-forwarding chain is the bridge.
  See `screens/future-export-uctarne.md`.
- **Odpis / shrinkage.** First-class write-off as a movement type
  with reason codes, distinct from a correction. See
  `screens/future-skart-skarty.md`.
- **Inventura.** Structured physical stock-take with discrepancy
  resolution against the ledger.
