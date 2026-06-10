# Export pro účetní / Accountant export

**Not in MVP. Documented now to keep the data model honest.**

This screen does not ship with the first usable release. The current
hand-off to the external accountant runs on Karolína forwarding dodací
list e-mails (per [`../workflows.md`](../workflows.md)). This screen is
documented so the data model, the dodací list, and movement history are
shaped from the start to support a future structured export.

## Purpose
Produce a structured export of dodací listy and / or movements for a
chosen period in a format the accountant can ingest. The shipping
question — CSV, Pohoda XML, Money S3 import, or something else — is
open and depends on the accountant. The screen exists in this document
so the rest of the design does not preclude any of those answers.

## Who uses it
- Petr and Karolína. Desktop. Cadence likely monthly.

## What it shows
- Header "Export pro účetní".
- A **rozsah / range** filter: date range (from, to).
- A **co exportovat / what to export** chooser:
  - Dodací listy.
  - Pohyby (movements).
  - Both, if the chosen format supports it.
- A **formát** chooser populated with whichever formats the
  implementation supports — to be decided. Examples that may appear:
  - CSV (UTF-8, sloupce per dodací list line / per movement).
  - Pohoda XML.
  - Plain PDF bundle (zip of per-list PDFs).
- An optional **pobočka** filter (owner-level only; default = both).
- A **náhled / preview** area: a small summary of what the export will
  contain — counts, totals — before the file is generated.
- A primary action "Vygenerovat export" producing a download.
- A **historie exportů** strip — past exports with timestamp, range,
  format, who triggered, and a re-download link. Helps the accountant's
  conversations ("ten z minulého týdne") and prevents accidental
  duplicates.

## What you can do here
- Choose range, content, format.
- Preview the count of records.
- Generate and download the export.
- Re-download a previously generated export.

## What it links to / from
- Reached from:
  - Main navigation (admin section), owner-level only.
  - "Exportovat" affordance (if added) on
    [Seznam dodacích listů](08-seznam-dodacich-listu.md) or
    [Historie pohybů](10-historie-pohybu.md).
- Goes to:
  - Stays within this screen.

## Business rules & validation
- Owner-level only.
- Range required; "from" must be on or before "to".
- An export is a **snapshot** of the data at generation time. If a
  movement is corrected later, a re-generated export for the same
  range will differ — the historie exportů preserves the original.
- The export must reflect any audited corrections that were in effect
  at the moment of generation; nothing is silently filtered out.
- Whether to include a per-record marker for "edited after issue" so
  the accountant can spot retroactive changes is an open design
  detail — likely yes.

## States
- **Empty:** no export ever generated; historie exportů empty;
  preview empty until a range is chosen.
- **Range chosen:** preview populated with counts and headline totals;
  "Vygenerovat export" enabled.
- **Generating:** "Generuji…" state, disabling the action button.
- **Error:** if the chosen format has constraints the data violates
  (e.g. a required field empty on some record), the screen explains
  per-record what is missing.
- **After successful action:** the file is offered as a download and a
  row is added to historie exportů; the screen stays.

## What this screen explicitly does NOT do
- Does not push to the accountant's software automatically in MVP-of-the
  -future-feature (and possibly never; pushing changes the integration
  shape).
- Does not produce **faktury** — invoicing remains the accountant's
  responsibility.
- Does not alter the underlying data; export is read-only.

## Open questions for this screen
- **Format** — the central open question (see
  [`../open-questions.md`](../open-questions.md), *Accountant export
  format*). Needs the external accountant directly.
- Whether export rows should reflect **corrections** explicitly (a
  separate "edited" column) or implicitly (corrected values silently).
- Whether to support **scheduled** automatic exports (monthly e-mail to
  the accountant) — defer until manual export is established.
- Whether to mark exported records as "exportováno" so they are not
  exported again — risky given that corrections may re-warrant export;
  default is no.
