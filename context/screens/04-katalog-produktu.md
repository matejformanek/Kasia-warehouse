# Katalog produktů / Product catalogue

## Purpose
The single browsable list of everything Kasia handles — raw spices
(koření), branded single-ingredient packs, and house mixtures (směsi).
This is where an operator finds an item to receive or issue, where the
owner curates the assortment, and where a future mixing job will source
its recipe definition.

## Who uses it
- Branch staff use it constantly as a lookup ("does this spice exist
  yet?", "what's the exact name we use for it?") and as a launchpad into
  product detail. Mostly desktop, sometimes phone.
- Owner and Karolína use it to add, rename, retire products and to
  manage mixture recipes. Desktop.

## What it shows
- A search box at the top, the dominant control on this screen.
- A filter strip with at least:
  - Type: "koření" / "směs" / "vše".
  - Status: "aktivní" / "archivované" / "vše" (so a retired product is
    not lost forever, just hidden by default).
  - Branch presence (optional): only show items currently on hand at a
    chosen branch.
  - Stav skladu (optional): "Dochází" / "Prázdné" — narrows the list to
    rows whose Stav column already shows the orange "dochází" or red
    "prázdné" badge. Single-select; combines with the other filters.
- A scrollable list of catalogue **products** (per
  [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md):
  one row per product, stock in kg only — no variants), each row
  showing:
  - Czech name.
  - Type marker (koření / směs).
  - On-hand in kg across all active branches (visible to owner-level
    users); per-branch on-hand (visible to branch staff for their own
    branch only) per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md).
  - Rezervováno + Efektivně + Práh columns per
    [`decisions/0043-reorder-threshold.md`](../decisions/0043-reorder-threshold.md)
    + [`decisions/0044-reservations-planned-states.md`](../decisions/0044-reservations-planned-states.md).
  - A "Nízký na" column rendering one branch-code chip per branch where
    `effective < threshold` for this product. Only shown when no branch
    filter is in scope (`?branch=` empty AND user is not obsluha-locked);
    the existing "dochází / prázdné" badge already covers the single-
    branch case. Per
    [`decisions/0053-stock-row-is-branch-carry.md`](../decisions/0053-stock-row-is-branch-carry.md)
    the chip + the daily *Dochází zboží* mail only consider branches that
    **drží** the product (a `Stock` row exists). Branches that *nedrží*
    the product never appear, even with `effective = 0`.
  - For mixtures, a small marker indicating "má recepturu".
- A count of how many items match the current filters.
- For owner-level users: a "Přidat položku" action.

## What you can do here
- Type to search by Czech name. Matching is forgiving of diacritics
  and case.
- Apply / clear filters.
- Click a row to open [Detail produktu](05-detail-produktu.md).
- (Owner-level only) Click "Přidat položku" to create a new catalogue
  entry — taken to a fresh [Detail produktu](05-detail-produktu.md) in
  create mode.
- (Owner-level only) Archive / unarchive an item from its detail screen
  (action lives on [05](05-detail-produktu.md), not inline here, to keep
  this screen as a browser).

## What it links to / from
- Reached from:
  - Main navigation, available from every authenticated screen.
  - [Příjem zboží](06-prijem-zbozi.md) and
    [Výdej zboží](07-vydej-zbozi.md) — those screens embed a picker
    that is functionally the same list; the standalone catalogue is for
    browsing without committing to a movement.
  - [Přehled pobočky](03-prehled-pobocky.md) and
    [Přehled vlastníka](02-prehled-vlastnik.md) — stock rows link in.
- Goes to:
  - [Detail produktu](05-detail-produktu.md).

## Business rules & validation
- Both koření and směsi live in the same catalogue. The "type" marker
  distinguishes them; the user does not switch between two catalogues.
- Item names are Czech-first and must be unique within the active set
  (an archived item with the same name is acceptable so historical
  movements still resolve).
- Branch staff see all catalogue entries (so they can name and request
  things) but stock numbers are scoped to their branch.
- Archived items remain visible in historical movements and dodací
  listy; they just don't show up by default in pickers or in this
  list.

## States
- **Empty:** at first install, "katalog je zatím prázdný" with a primary
  call-to-action "Přidat první položku" for owner-level users; branch
  staff see the same message without the action.
- **Normal:** populated list with filters applied.
- **Search yields nothing:** "nic neodpovídá hledání" with a "vymazat
  filtr" link.
- **Disallowed:** branch staff who reach this screen do not see the
  "Přidat položku" action; no error, just absence.
- **After successful action:** creating a new item lands the user on
  the new [Detail produktu](05-detail-produktu.md); returning to the
  catalogue shows the new item at the top with a transient confirmation.

## What this screen explicitly does NOT do
- Does not record movements. It is the encyclopedia, not the ledger.
- Does not show prices anywhere per
  [`decisions/0029-no-prices-supersedes-0011.md`](../decisions/0029-no-prices-supersedes-0011.md)
  — no price list, no margin, no `cena` field on the product.
- Does not show mixture recipes inline; recipes live on
  [Detail produktu](05-detail-produktu.md) for the mixture in question.
- Does not allow bulk import of products in MVP; items are added one at
  a time on [Detail produktu](05-detail-produktu.md).

## Open questions for this screen
- Whether to add a "naposledy pohyb" column to help the owner spot
  dormant items — defer until there is operating history.

## UX refresh — Phase 2 (2026-07-03)

Katalog ported to mockup `01b`: **grouped by stock state** into three tables
(Prázdné / Dochází / V pořádku) under `.sub-head` headers + a KPI strip; the
view groups rows server-side and renders only non-empty groups. Rows are
**whole-row `row-link` with no per-row buttons**. The 0063 live filter is
extended to span all three group tbodies and hide an emptied group section
(decision [`0064`](../decisions/0064-grouped-catalogue-client-filter.md)).
