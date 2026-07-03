# Historie pohybů / Movement history

## Purpose
A chronological, filterable record of every stock movement at a branch
— příjem, výdej (per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)
this includes internal výdeje to Říčany — they show as výdej with
odběratel = Říčany), and (in the future) odpis and mixing job. The
owner uses it to investigate, audit, and as the jumping-off point
for corrections. Branch staff use it to look up what they or a
colleague did yesterday.

## Who uses it
- Petr and Karolína: across both branches; primary tool for
  understanding what happened and for initiating corrections.
- Branch staff: scoped to their own branch; read-only.
  Desktop primarily.

## What it shows
- Header "Historie pohybů".
- A filter strip:
  - Branch (owner-level only).
  - Type: vše / příjem / výdej / (future) odpis / (future) výrobní
    dávka.
  - Item (catalogue picker).
  - Counterparty: dodavatel / odběratel (Říčany shows here as one of
    the odběratele per
    [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)).
  - Date range.
  - Operator (who recorded it).
  - "Pouze editované" — show only movements that have been corrected
    after the original entry. This is the surrogate for a standalone
    audit-log screen — see the reconciliation note in
    [`README.md`](README.md).
- A table of movements, latest first, each row:
  - Datum a čas.
  - Typ — `příjem` / `výdej` per
    [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)
    (no `převod` kind — internal výdeje to Říčany show as výdej) /
    (future) `odpis` / (future) `výrobní dávka` — with a visual
    marker per type.
  - Položka(y) — a short summary at product grain (per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md)),
    e.g. "Oregano" + "+N dalších" for multi-line movements.
  - Množství — in kg with 3 dp per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md).
  - Šarže — visible inline when the movement line has one recorded
    (per [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md)
    šarže is optional, so this column is sparse).
  - Protistrana (supplier on příjem; odběratel on výdej — Říčany
    shows in this cell for internal výdeje per
    [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)).
  - Operátor.
  - Marker "editováno" if this movement has any audit-trail entry.
  - For a výdej, a link to its dodací list on
    [Detail dodacího listu](09-detail-dodaciho-listu.md).
- A count of how many movements match the filters.
- A "Zobrazit detail" link on each row leading to
  [Úprava pohybu](11-uprava-pohybu.md) (owner-level) or to a read-only
  detail (branch staff land on the same screen in read-only mode).

## What you can do here
- Filter and search.
- Click a row to open the movement detail / edit on
  [Úprava pohybu](11-uprava-pohybu.md).
- Click the dodací list link on a výdej row to open the dodák on
  [Detail dodacího listu](09-detail-dodaciho-listu.md).
- Toggle "Pouze editované" to see the system's correction history at a
  glance — the proxy for "audit log".

## What it links to / from
- Reached from:
  - Main navigation.
  - [Přehled vlastníka](02-prehled-vlastnik.md) — recent movements
    rows, "K vyřešení" items.
  - [Přehled pobočky](03-prehled-pobocky.md) — recent movements rows,
    "celá historie" link.
  - [Detail produktu](05-detail-produktu.md) — embedded history strip
    link.
- Goes to:
  - [Úprava pohybu](11-uprava-pohybu.md).
  - [Detail dodacího listu](09-detail-dodaciho-listu.md).

## Business rules & validation
- Branch staff see strictly their own branch's movements.
- Owner-level users see both branches, can filter by branch.
- A movement that has been edited shows the **current** values in the
  table; the original values are preserved in the audit trail and
  visible on [Úprava pohybu](11-uprava-pohybu.md).
- A movement is **never deleted**. The closest equivalent is an edit
  that reduces a quantity to zero with an explanatory reason, which is
  itself an audited correction.
- Sort defaults to newest first. Filter state is preserved while
  navigating in and out of detail.

## States
- **Empty:** "zatím žádné pohyby"; no rows.
- **Normal:** populated table.
- **Filtered to nothing:** "žádné pohyby neodpovídají filtrům" with
  "vymazat filtry".
- **Disallowed:** branch staff who try to load the other branch get a
  "nemáte oprávnění" placeholder.
- **After successful action:** the screen is mostly a launcher;
  returning here after a correction shows the updated row at the top
  of the list (or in place, if sort is by date), with the "editováno"
  marker.

## What this screen explicitly does NOT do
- Does not record new movements. Use příjem / výdej.
- Does not edit movements directly in the table; edits happen on
  [Úprava pohybu](11-uprava-pohybu.md).
- Does not export today (export is future — see
  [Export pro účetní](future-export-uctarne.md)).
- Does not delete rows.
- Is not the audit log per se; it surfaces the audit footprint via
  the "editováno" marker and the per-movement detail.

## Open questions for this screen
- Whether a dedicated **audit log** screen (a flat list of every
  correction across all movements, with original-vs-new field
  comparisons) is worth its own screen, or whether the "Pouze
  editované" filter here plus the audit detail on
  [Úprava pohybu](11-uprava-pohybu.md) is enough. MVP keeps it folded
  in here. See the reconciliation note in [`README.md`](README.md).
- Export shape and trigger — defer to
  [Export pro účetní](future-export-uctarne.md).
- Whether to show "celkové množství podle filtru" as a sum at the
  bottom of the table — useful for spot reconciliation but only
  meaningful per-unit; defer.

## UX refresh — Phase 2 (2026-07-03)

Historie ported to mockup `09`: compact table with columns **Datum · Druh ·
Pob. · Položky · Protistrana · Množství · Doklad**, colour-coded `.druh`
badges, operator folded into a Protistrana sub-line, merged Doklad cell
(`.dl-link` + `.tag-edit`), and `.btn-mini` accept/cancel for PLANNED rows
(Přijmout -> `prijem_confirm`, out-of-form Zrušit per 0059). New per-movement
**Množství** total (summed in the view). `#history-table` 0063 filter kept.
