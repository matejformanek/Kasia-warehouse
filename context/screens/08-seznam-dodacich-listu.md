# Seznam dodacích listů / Delivery notes list

## Purpose
A browsable record of every dodací list the system has issued. The
owner uses it to scan what has gone out, find a specific dodák for a
customer's question, and confirm that things were e-mailed. Branch
staff use it to find one of their own dodáky.

## Who uses it
- Petr and Karolína: across both branches; the canonical "what went
  out lately" view.
- Branch staff: scoped to their own branch's dodáky.
  Mostly desktop; occasionally phone when the customer is on the line.

## What it shows
- A header "Dodací listy".
- A filter strip:
  - Branch (owner-level only; branch staff see only their own).
  - Odběratel.
  - Date range.
  - E-mail status: "vše" / "odesláno" / "chyba odeslání" / "znovu
    odesláno".
  - "Pouze editované" — dodáky linked to a movement that has been
    corrected after issue (see
    [Úprava pohybu](11-uprava-pohybu.md)).
- A table of dodáky, latest first, each row:
  - Číslo dodacího listu in `<BRANCH>-<YYYY>-<NNNN>` format per
    [`decisions/0008-dodaci-list-numbering.md`](../decisions/0008-dodaci-list-numbering.md)
    (e.g. `TYN-2026-0042`).
  - Datum.
  - Pobočka.
  - Odběratel.
  - Počet řádků / hrubý objem in kg per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md)
    (sum of line `quantity_kg` per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md)).
  - Stav e-mailu (with a visible warning marker on failures).
  - "Editováno" marker if the underlying výdej was corrected after
    issue. The internal version counter is visible on
    [09](09-detail-dodaciho-listu.md), not in this list.
- A count of how many dodáky match the filters.
- A link to export the current filtered list — **future**, deferred
  to [Export pro účetní](future-export-uctarne.md).

## What you can do here
- Apply / clear filters.
- Click a row to open [Detail dodacího listu](09-detail-dodaciho-listu.md).
- (No bulk actions in MVP. No mass re-send, no mass edit.)

## What it links to / from
- Reached from:
  - Main navigation.
  - [Přehled vlastníka](02-prehled-vlastnik.md) — "Dodací listy k
    revizi" section.
- Goes to:
  - [Detail dodacího listu](09-detail-dodaciho-listu.md).

## Business rules & validation
- Branch staff are strictly scoped: they see only dodáky issued from
  their branch.
- Owner-level users see both branches and can filter by branch.
- The list reflects current numbering and metadata, including any
  re-sends or post-issue corrections.
- A dodací list is never deleted from this list. If its underlying
  výdej is corrected, the dodák stays but is marked "editováno" and
  the user can drill into [11](11-uprava-pohybu.md) for the trail.

## States
- **Empty (no dodáky ever issued):** "zatím nebyly vystaveny žádné
  dodací listy"; no filter strip needed.
- **Normal:** populated table.
- **Filtered to nothing:** "žádné dodací listy neodpovídají filtrům",
  with a "vymazat filtry" link.
- **Disallowed:** branch staff who try to manipulate the URL to view
  the other branch get a "nemáte oprávnění" placeholder.
- **After successful action:** opening a row navigates to the detail
  screen; no in-place actions to confirm here.

## What this screen explicitly does NOT do
- Does not generate a new dodací list (that happens on
  [Výdej zboží](07-vydej-zbozi.md)).
- Does not edit dodací listy (corrections go through
  [Úprava pohybu](11-uprava-pohybu.md), which then re-flags the dodák).
- Does not handle invoices; invoicing is the účetní's job.
- Does not export today; export is future
  (see [Export pro účetní](future-export-uctarne.md)).

## Open questions for this screen
- **Export shape and trigger** — handled on
  [`future-export-uctarne.md`](future-export-uctarne.md) in Phase B.
- Whether to surface "e-mail open / read" tracking — **out of scope**
  by default; raises GDPR and complexity questions disproportionate
  to the value. Confirmed: not in MVP.

> Per-row money figures are out per
> [`decisions/0029-no-prices-supersedes-0011.md`](../decisions/0029-no-prices-supersedes-0011.md)
> (no prices anywhere) and
> [`decisions/0010-prices-on-dodaci-list.md`](../decisions/0010-prices-on-dodaci-list.md):
> the dodací list does not carry prices, so no line totals to sum.
