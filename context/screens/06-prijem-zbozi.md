# Příjem zboží / Receive goods

## Purpose
Record that goods have arrived at a branch from a supplier. This is one
of the two everyday entry points to the ledger (the other being výdej).
Saving a příjem increases stock at the branch and writes a movement
record visible in [Historie pohybů](10-historie-pohybu.md).

## Who uses it
- Branch staff at the moment goods are unloaded. Phone-friendly use is
  important: the operator may be in the aisle next to a pallet, not at
  a desk.
- Owner and Karolína may use it for either branch when needed, though
  in practice they rarely do.

## What it shows
- A header "Nový příjem na pobočce <branch name>". For branch staff the
  branch is fixed; for owner-level users the branch is a chooser.
- A **dodavatel** picker (supplier) — searchable from the existing
  supplier list, with an inline "přidat dodavatele" action for owner-level
  users when the supplier is new. Branch staff hitting an unknown
  supplier are walked through a minimal "quick add" inline (name + IČO)
  if owner has enabled this; otherwise they ask the owner. Default
  assumption: minimal quick-add is enabled.
- An optional **doklad dodavatele** field — the supplier's paperwork
  number, for cross-reference.
- The receipt **date**, defaulting to today, editable.
- A **lines** area, each line:
  - **Product picker** (per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md))
    — searches [Katalog produktů](04-katalog-produktu.md) by Czech
    product name. The UI shows "Oregano" (one row per product).
  - Quantity in **kg** (3 dp per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md)).
  - Optional **šarže** field — operator records when the supplier
    sack/box carries a printed batch (per
    [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md));
    skips otherwise.
  - Optional expiry date alongside šarže when supplier provides one.
  - Optional per-line note.
  - "Odebrat řádek" affordance.
- An "Přidat řádek" action.
- A short summary at the bottom: number of lines, total mass in kg.
- Primary action "Uložit příjem" and a "Zrušit" link.
- An inline option to **add a new catalogue item** while staying on
  this screen, when a delivered item is not yet in the catalogue —
  available to anyone who has catalogue-edit permission; for branch
  staff the inline path is limited to the "quick add" subset
  (name + unit) and the owner is informed via "K vyřešení" on
  [Přehled vlastníka](02-prehled-vlastnik.md) that a new item exists
  and may need full review.

## What you can do here
- Pick a dodavatel.
- Add a doklad number.
- Add and remove lines.
- For each line, pick a product, enter quantity in kg, optionally
  record šarže (+ expiry) and a note.
- Inline-add a new dodavatel (subject to permission).
- Inline-add a new catalogue item (subject to permission).
- Save the příjem with "Uložit příjem".
- Cancel with "Zrušit" and return to the previous screen.

## What it links to / from
- Reached from:
  - "Nový příjem" quick action on
    [Přehled pobočky](03-prehled-pobocky.md).
  - Main navigation.
- Goes to:
  - [Přehled pobočky](03-prehled-pobocky.md) on successful save.
  - [Detail produktu](05-detail-produktu.md) on inline catalogue add
    (optional — could stay on this screen with a transient confirmation;
    decided to stay on this screen so the operator does not lose their
    in-progress příjem).

## Business rules & validation
- Branch is fixed by the operator's scope. Branch staff cannot record
  a příjem against the other branch.
- Dodavatel is required.
- At least one line is required.
- Each line must have a product and a positive quantity in kg.
- Date cannot be in the future. Date significantly in the past is
  allowed but should produce a soft confirmation ("opravdu zaznamenat
  do <date>?") — this is the common case of forgetting to enter
  yesterday's delivery, not an error.
- Inline-added items get a default status of "aktivní" and a placeholder
  description; the owner is responsible for completing details later.
- Saving a příjem is atomic: either all lines apply and stock updates
  succeed, or none do — partial saves are not allowed.
- After save, the příjem appears in [Historie pohybů](10-historie-pohybu.md)
  and the per-branch stock in [Přehled pobočky](03-prehled-pobocky.md)
  reflects the new on-hand.

## States
- **Empty (just opened):** branch pre-filled, dodavatel empty, one
  empty line ready, date = today.
- **Normal:** at least one line filled in.
- **Validation error:** inline messages next to offending fields
  (missing dodavatel, missing item, non-positive quantity, future
  date). Save button enabled but submission blocked until clean.
- **Confirmation prompt:** date is more than a few days in the past or
  a quantity looks implausibly large — soft confirmation modal.
- **Inline-add open:** a sub-form for adding a dodavatel or a catalogue
  item is visible inline; while it is open, the rest of the screen is
  disabled.
- **After successful save:** redirect to
  [Přehled pobočky](03-prehled-pobocky.md) with a transient confirmation
  ("Příjem byl uložen"). The new movement is visible at the top of
  recent movements.

## What this screen explicitly does NOT do
- Does not generate any document — no příjemka PDF is emailed in MVP.
- Does not contact the supplier in any way.
- Does not handle returns to a supplier (treat as a separate flow when
  it ever happens; not in MVP).
- Does not run a mixing job — receiving raw spice is distinct from
  consuming it in a směs production. See
  [Míchání směsi](15-michani.md).
- Does not modify the catalogue beyond the explicit inline-add step.

## Open questions for this screen
- Whether the branch staff inline "quick add" of a dodavatel should be
  allowed at all or always require owner. Default: **allow**, per the
  brief's "bez školení" constraint — making branch staff wait for the
  owner to add a supplier mid-unload would stall the workflow.
- Whether to attach the supplier's paperwork (scan / PDF) to the
  příjem. Defer; not in MVP.
- Receipt that does not match the supplier's paperwork: the
  [`../workflows.md`](../workflows.md) inbound section says "record
  what was delivered" — UI handles this implicitly today (operator
  types the real quantity); a richer "expected vs. actual" view is
  out of MVP.
