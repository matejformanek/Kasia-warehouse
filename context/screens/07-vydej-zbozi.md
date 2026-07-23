# Výdej zboží / Issue goods

> **Per [0095](../decisions/0095-hotovy-vyrobek-finished-product-type.md):**
> finished products („hotový výrobek") are selectable on výdej and land on the
> dodací list. They are **unlimited** — the per-row unit shows **„ks"**, the
> live over-stock check treats them as „neomezeno" (never over, never blocks
> submit), and no stock is deducted.

## Purpose
Record that goods are leaving a branch — to a B2B customer, or
internally to Říčany (per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)
Říčany is just an odběratel with default-selected status, not a
distinct movement kind). This is the central act of the system:
saving a confirmed výdej decrements branch stock, writes a movement
record, **generates a dodací list PDF**, and **e-mails that PDF to
Petr and Karolína** (per
[`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md);
never to the customer). The conversation that *led* to the order
(phone, e-mail) happens outside the system; the výdej screen is
where that conversation becomes a record.

## Who uses it
- Branch staff at the moment the order is being prepared for handover
  to the carrier or the customer. Mostly desktop in the branch office;
  phone usable for emergencies.
- Owner and Karolína occasionally, for either branch.

## What it shows
- Header "Nový výdej z pobočky <branch name>". Branch fixed for branch
  staff; chooser for owner-level users.
- An **odběratel** picker (customer) — searchable from existing
  customers, with inline "přidat odběratele" available. **Default
  selection is Říčany** per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md);
  switching to another customer is one click. A customer record
  carries: name, IČO, DIČ, billing/delivery address, optional email
  / phone for contact-record use (the email is **not** read by the
  dodák-send code per
  [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md)).
  (There is no standalone customer-management screen in MVP; customers
  live as rows inside this picker — see the reconciliation note in
  [`README.md`](README.md).)
- Issue **date**, defaulting to today, editable.
- A **lines** area, each line:
  - **Product picker** (per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md))
    — searches by Czech name; the line shows "Oregano".
  - Quantity in **kg** (3 dp per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md)).
  - Optional **šarže** field (per
    [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md))
    — recorded when known, skipped otherwise. The dodací list line
    renders the šarže when present.
  - Optional per-line note (will appear on the dodací list).
  - No price column anywhere on this screen or on the dodací list per
    [`decisions/0029-no-prices-supersedes-0011.md`](../decisions/0029-no-prices-supersedes-0011.md).
- An "Přidat řádek" action.
- A **dodací list preview block** that updates live as lines change:
  - Document header (Kasia vera identity).
  - Odběratel block.
  - Lines as they will print.
  - Date.
- A **recipients block** — read-only display of the fixed pair
  `[Petr, Karolína]` from
  [`14-nastaveni.md`](14-nastaveni.md) per
  [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md).
  No "Přidat příjemce" affordance. No per-customer remembered list.
  No "uložit pro tohoto odběratele" checkbox.
- Primary action "Vystavit dodací list a uložit výdej".
- Secondary action "Zrušit".

## What you can do here
- Pick an odběratel (default = Říčany; switch with one click).
- Inline-add a new odběratel (name, IČO, DIČ, address; optional email
  / phone as contact data — not used by the dodák-send code).
- Set the date.
- Add and remove lines, with products and quantities in kg.
- Optionally record šarže per line (per
  [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md)).
- Submit — which atomically:
  1. Decrements branch stock.
  2. Writes a výdej movement record.
  3. Renders a dodací list PDF.
  4. Sends the PDF by e-mail to Petr + Karolína per
     [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md).
  5. Lands the user on
     [Detail dodacího listu](09-detail-dodaciho-listu.md).
- Cancel and discard the in-progress výdej.

## What it links to / from
- Reached from:
  - "Nový výdej" quick action on
    [Přehled pobočky](03-prehled-pobocky.md).
  - Main navigation.
- Goes to:
  - [Detail dodacího listu](09-detail-dodaciho-listu.md) on success.
  - [Přehled pobočky](03-prehled-pobocky.md) on cancel.

## Business rules & validation
- Branch is fixed by operator scope. Branch staff cannot issue from the
  other branch.
- Odběratel is required (defaulted to Říčany per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)).
- At least one line is required.
- Each line must have an item and a positive quantity not exceeding
  current on-hand at this branch. The screen visibly warns and blocks
  submission when a quantity exceeds on-hand. (Negative stock is never
  allowed via this flow — corrections that overdraw must go through
  [Úprava pohybu](11-uprava-pohybu.md).)
- Issue date cannot be in the future; significantly past dates produce
  a soft confirmation.
- Customer IČO is required when inline-adding a new odběratel. DIČ is
  strongly encouraged; whether it is strictly required on every
  customer is an open detail (glossary).
- Saving is atomic: stock decrement, movement record, PDF render, and
  e-mail send are treated as one act. **If the e-mail fails**, the
  výdej and the dodací list still exist; the failure is surfaced as a
  "K vyřešení" item for the owner and the dodací list is flagged as
  "e-mail nedoručen" on [09](09-detail-dodaciho-listu.md), where it can
  be re-sent. The accountant must not lose a sale because of a
  transient SMTP problem.
- Dodací list **číslo** is generated atomically on save per
  [`decisions/0008-dodaci-list-numbering.md`](../decisions/0008-dodaci-list-numbering.md):
  per-branch annual sequence `<BRANCH>-<YYYY>-<NNNN>` (e.g.
  `TYN-2026-0042`). The year segment is the **issue date's** year, not
  the system clock at save time (so a 30-Dec-2026 dodák saved on
  3-Jan-2027 stays `TYN-2026-NNNN`).
- The dodací list is the customer-facing artefact; the výdejka is the
  internal record. In MVP these are the same data, two views (per
  [`../domain-glossary.md`](../domain-glossary.md)).

## States
- **Empty (just opened):** branch fixed, odběratel = Říčany (default
  per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)),
  one empty line, date = today, recipients = fixed pair from
  [`14-nastaveni.md`](14-nastaveni.md).
- **Normal:** odběratel chosen, at least one line.
- **Validation error:** inline messages (missing odběratel, missing
  item, quantity > on-hand, future date).
- **Quantity exceeds on-hand:** explicit inline warning on the line
  showing current on-hand; submission blocked.
- **Inline-add open:** sub-form for adding an odběratel; rest of the
  screen disabled.
- **Submitting:** "Vystavuji a odesílám…" state, primary button
  disabled to prevent double-submit.
- **After successful action:** redirect to
  [Detail dodacího listu](09-detail-dodaciho-listu.md) showing the
  generated dodací list with the PDF preview and the e-mail status
  ("odesláno na: …").
- **E-mail send failed:** still redirect to
  [Detail dodacího listu](09-detail-dodaciho-listu.md) which shows the
  failure prominently and offers re-send.

## What this screen explicitly does NOT do
- Does not accept customer orders. There is no order intake here;
  orders arrive by phone or e-mail (per
  [`../workflows.md`](../workflows.md)).
- Does not produce a faktura. Invoicing is the účetní's job, on the
  basis of dodací listy.
- Does not send the dodák to the customer per
  [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md);
  recipients are the fixed Petr+Karolína pair from Nastavení.
- Does not allow split / partial deliveries on a single výdej. The
  established rule is: one výdej = one dodací list; partial deliveries
  are two výdeje (per [`../workflows.md`](../workflows.md)).
- Does not edit historical výdeje — for that, use
  [Úprava pohybu](11-uprava-pohybu.md).

## Open questions for this screen
- **PDF template** — logo placement, line table layout, signature
  line, footer — remains *Decide before MVP* and is resolved when
  Phase B reaches [`14-nastaveni.md`](14-nastaveni.md). The preview
  block on this screen will reflect whatever the template decides.
- **DIČ required-ness on customer** — small detail in
  [`../domain-glossary.md`](../domain-glossary.md); default current
  rule is "DIČ encouraged but not strictly required". Not blocking.
- **Customer-management screen** — currently folded into this picker;
  a standalone customer screen is deferred. Not blocking.
