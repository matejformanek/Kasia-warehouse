# Detail dodacího listu / Delivery note detail

## Purpose
The full view of one dodací list: its rendered PDF, its metadata, who it
was e-mailed to and whether that succeeded, the underlying výdej it came
from, and the controls to re-send the e-mail or download the PDF again.
This is the screen the owner opens when the customer says "můžeš mi to
poslat ještě jednou?".

## Who uses it
- Petr and Karolína: routinely. They are the people the customer calls.
- Branch staff: for their own branch's dodáky, for the same reasons.
  Desktop primarily. Phone for re-send on the move.

## What it shows
- Header "Dodací list <číslo>".
- Metadata block:
  - Číslo dodacího listu.
  - Datum vystavení.
  - Pobočka, ze které byl výdej.
  - Odběratel — name, IČO, DIČ, address.
  - Vystavil (operator).
- A **PDF preview** of the rendered dodací list, large and prominent.
  Per
  [`decisions/0029-no-prices-supersedes-0011.md`](../decisions/0029-no-prices-supersedes-0011.md)
  and
  [`decisions/0010-prices-on-dodaci-list.md`](../decisions/0010-prices-on-dodaci-list.md)
  the PDF carries no prices, no line totals, no dodák total.
- A **lines** section (the same content as on the PDF, but in a
  scrollable web layout for quick scanning), each line: product name,
  quantity in kg per
  [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md),
  optional šarže, optional per-line note.
- A **verze a odeslání** audit table per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md):
  one row per PDF version (the monotonic internal version counter,
  starting at 1), with the send timestamp, the actual recipient list
  for that send, the trigger reason ("vystavení" for v1, "oprava: …"
  for subsequent versions), and the delivery status per recipient.
- An **e-mail status** block (current state derived from the audit
  table above):
  - Recipients per
    [`decisions/0031-emails-internal-only-supersedes-0009.md`](../decisions/0031-emails-internal-only-supersedes-0009.md):
    the fixed pair `[Petr, Karolína]` from
    [`14-nastaveni.md`](14-nastaveni.md), read-only.
  - A "Znovu odeslat" action that re-sends the **current** PDF to
    the fixed pair.
- A link to the underlying výdej movement on
  [Úprava pohybu](11-uprava-pohybu.md), labelled "Otevřít výdej". For
  branch staff this opens read-only on
  [Historie pohybů](10-historie-pohybu.md) anchored to that movement
  (since they cannot edit movements).
- An "Editováno" warning banner if the underlying výdej has been
  corrected after issue, with a link to the audit detail on
  [Úprava pohybu](11-uprava-pohybu.md). The banner also surfaces the
  fact that an `[OPRAVA]` e-mail was auto-sent per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md);
  the verze a odeslání table above shows when and to whom.
- A "Stáhnout PDF" action.

## What you can do here
- Read the PDF preview.
- Download the PDF.
- Re-send the e-mail to the fixed pair via "Znovu odeslat".
- Navigate to the underlying výdej (edit or read-only depending on
  role).
- Navigate back to [Seznam dodacích listů](08-seznam-dodacich-listu.md).

## What it links to / from
- Reached from:
  - [Výdej zboží](07-vydej-zbozi.md) on successful save (this is the
    post-issue landing).
  - [Seznam dodacích listů](08-seznam-dodacich-listu.md).
  - [Přehled vlastníka](02-prehled-vlastnik.md) — "Dodací listy k revizi"
    and "K vyřešení" sections.
  - [Historie pohybů](10-historie-pohybu.md) when a výdej row links
    out to its dodák.
- Goes to:
  - [Úprava pohybu](11-uprava-pohybu.md) (owner-level) or
    [Historie pohybů](10-historie-pohybu.md) (branch staff).
  - [Seznam dodacích listů](08-seznam-dodacich-listu.md).

## Business rules & validation
- The PDF preview reflects the current state of the dodací list. If the
  underlying výdej was corrected, the PDF is re-rendered to match the
  corrected data; the "Editováno" banner tells the reader.
- Re-send sends the **current** PDF, not the original. (The audit trail
  on [Úprava pohybu](11-uprava-pohybu.md) preserves the original line
  values.)
- Branch staff can re-send their own branch's dodáky but cannot reach
  the underlying movement edit screen.
- A dodací list is never deleted from this screen.

## States
- **Normal:** PDF preview rendered, metadata populated, e-mail status
  shows "odesláno <datetime> na: …".
- **E-mail failed:** prominent warning banner "e-mail se neodeslal",
  reason if available, "Znovu odeslat" highlighted. The dodák also
  appears in "K vyřešení" on
  [Přehled vlastníka](02-prehled-vlastnik.md).
- **E-mail in progress (after a re-send click):** "Odesílám…" state on
  the action; success or failure updates the status block.
- **Editováno (corrected after issue):** banner visible, links to the
  audit detail. The verze a odeslání table shows the auto-generated
  `[OPRAVA]` send per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md).
  No manual decision needed for the re-send.
- **Disallowed:** branch staff trying to open a dodák from the other
  branch see a "nemáte oprávnění" placeholder.
- **After successful action:** stay on this screen; transient confirmations
  for "PDF staženo", "E-mail odeslán", etc.

## What this screen explicitly does NOT do
- Does not invoice. Invoicing is the accountant's job downstream.
- Does not edit line content. To change what was issued, correct the
  underlying movement on [Úprava pohybu](11-uprava-pohybu.md); the
  dodák will reflect the change automatically.
- Does not delete dodáky. Ever.
- Does not push to customer portals or external systems in MVP.
- Does not redirect the original e-mail (i.e. no "forwarding" by
  modifying the recipient list retroactively); the audit shows who
  received what when.

## Open questions for this screen
- Whether a "Storno" status for a dodák is needed (the customer
  refused delivery, or the order was cancelled before pickup) —
  defer; in MVP, treat as a correction with appropriate reason text.
  The číslo is retained per
  [`decisions/0008`](../decisions/0008-dodaci-list-numbering.md);
  no number is ever reused.
- **PDF template specifics** (logo, layout, signature line, footer)
  — remains *Decide before MVP*, resolved when Phase B reaches
  [`14-nastaveni.md`](14-nastaveni.md).
