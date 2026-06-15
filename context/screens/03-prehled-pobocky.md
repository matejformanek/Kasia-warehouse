# Přehled pobočky / Branch stock view

## Purpose
The home screen for branch staff and the per-branch drill-down for the
owner. Shows what is on hand at this one branch, what has moved
recently, and gives quick access to the actions a branch operator
performs all day — record a příjem, record a výdej, look up a product.

## Who uses it
- Branch staff (Týniště or Sezimovo Ústí), scoped strictly to their own
  branch. Used on desktop in the office and on a phone in the warehouse.
  Many times per day.
- Owner and Karolína, when drilling into a specific branch from
  [Přehled vlastníka](02-prehled-vlastnik.md). Owner-level users can
  open either branch's view.

## What it shows
- Branch name and address.
- An "as of" timestamp making clear the data is live.
- A **stock list** for this branch — every **product** that has a
  non-zero or recently non-zero quantity, per
  [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md):
  - Product name (Czech).
  - On-hand mass in kg per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md).
  - A **threshold-aware status badge** per
    [`../decisions/0043-reorder-threshold.md`](../decisions/0043-reorder-threshold.md)
    + [`../decisions/0044-reservations-planned-states.md`](../decisions/0044-reservations-planned-states.md):
    three states — `prázdné` (effective stock ≤ 0), `dochází` (effective
    stock < per-(product, branch) threshold), normal (no badge).
    *Effective* = `Stock.quantity − reserved_kg` where `reserved_kg`
    sums PLANNED mixing job consumption and PLANNED outgoing transfers
    from this branch. Replaces the original hardcoded "near-zero"
    marker.
  - A search box to filter the list by product name.
- A **recent movements** strip for this branch, latest first, with
  type (příjem / výdej), date, item, quantity in kg, counterparty
  (supplier or odběratel — Říčany shows as the odběratel for internal
  výdeje per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md)),
  and operator name.
- Quick-action buttons: "Nový příjem", "Nový výdej". (A výdej to
  Říčany is just "Nový výdej" with the default odběratel — no
  separate quick-action per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md).)

## What you can do here
- Search and scroll the stock list.
- Click an item in the stock list to open its
  [Detail produktu](05-detail-produktu.md), which can additionally show
  per-branch history for this item.
- Click a row in recent movements to open
  [Historie pohybů](10-historie-pohybu.md) anchored on that entry.
- Start a new příjem via [Příjem zboží](06-prijem-zbozi.md), pre-filled
  to this branch.
- Start a new výdej via [Výdej zboží](07-vydej-zbozi.md), pre-filled to
  this branch — the odběratel picker defaults to Říčany per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md);
  switch to a different customer with one click.
- Open the full [Historie pohybů](10-historie-pohybu.md) for this
  branch via a "celá historie" link.

## What it links to / from
- Reached from:
  - [Přihlášení](01-prihlaseni.md) as the post-login landing for branch
    staff.
  - [Přehled vlastníka](02-prehled-vlastnik.md) via the "zobrazit
    pobočku" link, for owner and Karolína.
  - The "domů" / logo link in the header for branch staff (the home
    screen for them is their own branch).
- Goes to:
  - [Detail produktu](05-detail-produktu.md)
  - [Příjem zboží](06-prijem-zbozi.md)
  - [Výdej zboží](07-vydej-zbozi.md)
  - [Historie pohybů](10-historie-pohybu.md)

## Business rules & validation
- Branch staff see exclusively their own branch. A Týniště account
  never sees Sezimovo Ústí stock or movements, and vice versa — see
  the permissions matrix in
  [`../people-and-roles.md`](../people-and-roles.md).
- Owner-level users may open either branch's view.
- The new-příjem and new-výdej shortcuts are pre-bound to this branch;
  branch staff cannot retarget them to the other branch.
- The stock list reflects the current ledger, including corrections.

## States
- **Empty (brand-new branch or after a full clear-out):** stock list
  shows "na pobočce zatím není evidováno žádné zboží"; recent
  movements show "zatím žádné pohyby"; quick-action buttons are active.
- **Normal:** populated stock list, populated recent movements.
- **Search yields nothing:** the search box returns a "nic neodpovídá
  hledání" placeholder while keeping the cleared-search affordance
  visible.
- **Error / disallowed:** branch staff trying to load the *other*
  branch's view get a "nemáte oprávnění" placeholder; the main nav
  remains available.
- **After successful action:** this screen is a hub. Returning here
  from a saved příjem or výdej shows a transient confirmation banner
  ("Pohyb byl uložen") and the new entry visible at the top of recent
  movements.

## What this screen explicitly does NOT do
- Does not allow editing movements (use [11](11-uprava-pohybu.md)).
- Does not allow catalogue edits (use [04](04-katalog-produktu.md) /
  [05](05-detail-produktu.md)).
- Does not show stock from the other branch under any circumstance for
  branch staff.
- Does not show Říčany as a stocked location — Říčany is destination-only,
  see [`../warehouses.md`](../warehouses.md).
- Does not surface "K vyřešení" the way the owner dashboard does;
  branch staff do not own corrections.

## Open questions for this screen
- Whether branch staff get a read-only filter for "moje pohyby" on the
  recent movements strip — small UX nice-to-have, not blocking.

> Šarže is **not** a column on the branch stock list (per
> [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md):
> šarže is optional and visible at the movement level on
> [Historie pohybů](10-historie-pohybu.md), not aggregated up to
> branch overview).
