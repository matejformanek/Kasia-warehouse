# Detail produktu / Product detail

## Purpose
The full read- and (for owner-level users) edit view of one catalogue
entry. For a raw spice this is mainly identification and per-branch
stock. For a mixture (směs) this is additionally the recipe — the
list of recepturní složky that defines what the mixture is made of.

## Who uses it
- Branch staff open it to verify the name, unit, and recipe of an item
  before recording a movement or before physically mixing.
- Owner and Karolína open it to create, rename, edit, or archive items
  and to maintain mixture recipes.
  Desktop primarily. Phone usable for the read view.

## What it shows
- Czech name (the canonical brand-or-trade name).
- Type marker: "koření" or "směs" (per
  [`decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md):
  a `kind` discriminator on the shared products table).
- Status: aktivní / archivované.
- Free-text notes (optional) — short description, sourcing notes,
  anything the owner wants visible.
- A **stav zásob** section (per
  [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md)):
  one row per branch that **drží** this product (a `Stock` row exists)
  showing on-hand quantity in kg per
  [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md):
  - Týniště nad Orlicí — quantity in kg.
  - Sezimovo Ústí — quantity in kg.
  - (Branch staff see only their own branch's row.)
  - Per
    [`decisions/0053-stock-row-is-branch-carry.md`](../decisions/0053-stock-row-is-branch-carry.md):
    when no branch carries the product, the table renders a single
    empty-state row pointing vlastník at the *Pobočky* controls in
    edit mode. Vlastník toggles carry-state via Přidat / Odebrat
    buttons on the edit screen; obsluha sees the *Drží / Nedrží*
    badges read-only.
- A small product-level **summary mass**: total on-hand in kg across
  both branches (owner-level) or just this branch (branch staff).
- For mixtures only:
  - The **receptura** — a list of recepturní složky, each row
    `(component product, ratio)` per
    [`decisions/0005-mixture-recipe-model.md`](../decisions/0005-mixture-recipe-model.md).
    Ratios are stored as decimals; the screen renders them as
    percentages and visibly warns if the total is not 100 %.
  - Mixing jobs run on
    [Míchání směsi](15-michani.md) (in MVP per
    [`decisions/0032-mixing-in-mvp.md`](../decisions/0032-mixing-in-mvp.md));
    recipe edits here affect future jobs only — past jobs carry a
    recipe snapshot per
    [`decisions/0005`](../decisions/0005-mixture-recipe-model.md).
- A "naposledy upraveno" line — who, when, briefly.
- A short embedded history strip: the most recent movements involving
  this product, with a link to the full
  [Historie pohybů](10-historie-pohybu.md) filtered to this product.

## What you can do here
- (Owner-level only) Edit name, type, notes.
- (Owner-level only) For a směs, edit the receptura — add a row, change
  a ratio, remove a row.
- (Owner-level only) Archive / unarchive the product.
- (Owner-level only) Save changes via "Uložit".
- Anyone: click the embedded history strip to open
  [Historie pohybů](10-historie-pohybu.md) filtered to this product.
- Anyone: navigate back to [Katalog produktů](04-katalog-produktu.md).

## What it links to / from
- Reached from:
  - [Katalog produktů](04-katalog-produktu.md) — clicking a row.
  - [Přehled pobočky](03-prehled-pobocky.md) — clicking a stock row.
  - [Historie pohybů](10-historie-pohybu.md) — clicking an item name in
    a movement row.
- Goes to:
  - [Katalog produktů](04-katalog-produktu.md) — back link.
  - [Historie pohybů](10-historie-pohybu.md) — full history filtered to
    this item.

## Business rules & validation
- Name is required and unique within the active catalogue (see
  [04](04-katalog-produktu.md)).
- Stock is recorded in kg only per
  [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md);
  there is no pack-format model in MVP.
- For směs: every recepturní složka must reference an *active*
  product (typically a `kind = raw_spice` product). Ratios are
  stored as decimals (0.000 – 1.000), non-negative; the screen
  visibly warns if the total ratio is not 100 %.
- Archiving a product is allowed only when stock at every branch is
  zero and no movement-line draft references it. If any stock
  remains, the screen explains that and offers no action.
- Branch staff are read-only on every field.

## States
- **Create mode (new item):** all fields blank, primary action
  "Vytvořit položku", stock rows replaced by "po vytvoření bude na obou
  pobočkách 0".
- **Read mode (branch staff):** all fields visible but uneditable; no
  edit / save / archive controls.
- **Edit mode (owner-level):** fields editable, "Uložit" / "Zrušit"
  controls visible.
- **Validation error:** inline message next to the offending field
  ("celkový poměr složek musí být 100 %", "název už existuje").
- **Archived:** status pill visible, fields read-only by default,
  "Obnovit" action available for owner-level users.
- **After successful action:**
  - Save → stays on this screen, transient confirmation, "naposledy
    upraveno" updated.
  - Create → stays on this screen now in normal edit mode.
  - Archive → returns to [Katalog produktů](04-katalog-produktu.md).

## What this screen explicitly does NOT do
- Does not record stock movements. Use příjem / výdej.
- Does not run a mixing job — that is its own screen
  [Míchání směsi](15-michani.md).
- Does not store prices anywhere per
  [`decisions/0029-no-prices-supersedes-0011.md`](../decisions/0029-no-prices-supersedes-0011.md)
  — no `cena` field, no supplier history, no margins. Free-text notes
  are the only metadata beyond name + type.
- Does not let branch staff edit anything.

## Open questions for this screen
- Whether a per-product "default šarže prompt" flag is worth adding —
  e.g. force the operator to remember to enter šarže for products
  Petr cares about traceability on. Defer; not blocking.

## UX refresh — Phase 2 (2026-07-03)

Detail ported to mockup `04`: two-column layout with a sticky right rail
(**Rychlá fakta** tiles + **Akce**), left KPI strip + per-branch table.
Recipe-scaler JS/ids preserved verbatim. Actions repeated at the page bottom.
