# Přehled vlastníka / Owner dashboard

## Purpose
A single screen the owner (or Karolína) can open in the morning and see
the state of both branches at a glance — what's on hand, what moved
recently, what dodací listy went out, and anything the system thinks
needs their attention. The point is **calm awareness**, not control:
this is the "is the business breathing normally?" view.

## Who uses it
Petr and Karolína. Primarily on desktop at the Říčany office. Daily.
Branch staff do not see this screen — they land on
[Přehled pobočky](03-prehled-pobocky.md) instead.

## What it shows
- Header strip with the user's name, role, and a "log out" affordance.
- Main navigation (catalogue, příjem, výdej, dodací listy, historie,
  admin) — same nav as every other authenticated screen.
- **Two branch panels side by side**, one for Týniště nad Orlicí and
  one for Sezimovo Ústí. Each panel shows:
  - Branch name and location.
  - A summary of total stock at that branch per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md):
    number of distinct **products** with non-zero stock, total mass
    on hand (sum of `Stock.quantity` rows in kg per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md)),
    and a small list of the products with the largest on-hand
    quantities. Catalogue scale is ~20–30 items per branch per
    Petr's 2026-06-09 brief — the dashboard fits easily.
  - "Recent movements" — the last several příjem / výdej entries at
    that branch, each as a one-line item (date, type, item, quantity,
    operator).
  - A link "zobrazit pobočku" leading to the full
    [Přehled pobočky](03-prehled-pobocky.md) view for that branch.
- A **"Dodací listy k revizi"** section: the most recent dodací listy
  across both branches, with date, customer, branch, total, and a link
  to [Detail dodacího listu](09-detail-dodaciho-listu.md). The owner
  reads this section to know what went out.
- A **"K vyřešení"** (things flagged for owner attention) section,
  surfaced from elsewhere in the system. Examples that belong here:
  - Movements that were edited recently and may need a follow-up
    decision (e.g. a corrected výdej whose dodací list was already
    emailed — see [11 Úprava pohybu](11-uprava-pohybu.md)).
  - Failed dodací list e-mails that need a re-send from
    [Detail dodacího listu](09-detail-dodaciho-listu.md).
  - Items added inline at příjem that have not yet been fully
    classified in the catalogue (if the catalogue model requires it).
  - This section is **empty by default** and is the system's way of
    saying "nothing to worry about today".

## What you can do here
- Click into either branch panel to open the full branch view (03).
- Click a recent movement to open it on
  [Historie pohybů](10-historie-pohybu.md) (scrolled / filtered to that
  entry), and from there into edit if needed.
- Click a dodací list to open its
  [Detail dodacího listu](09-detail-dodaciho-listu.md).
- Click an item in "K vyřešení" to jump to wherever the resolution
  happens (movement edit, dodací list detail, catalogue edit).
- Use the main navigation to leave this screen for any other.

## What it links to / from
- Reached from:
  - [Přihlášení](01-prihlaseni.md), as the post-login landing for owner
    and Karolína.
  - The "domů" / logo link in the top header from any other authenticated
    screen, for owner and Karolína.
- Goes to:
  - [Přehled pobočky](03-prehled-pobocky.md) (per branch).
  - [Historie pohybů](10-historie-pohybu.md).
  - [Detail dodacího listu](09-detail-dodaciho-listu.md).
  - [Detail produktu](05-detail-produktu.md) — if a stock summary item
    is clickable.
  - Any other screen via main navigation.

## Business rules & validation
- Only owner-level roles see this screen. Branch staff who try to reach
  it are redirected to their own
  [Přehled pobočky](03-prehled-pobocky.md).
- "Recent movements" and "Dodací listy k revizi" are read-only here;
  edits happen on the dedicated screens.
- Numbers shown reflect the current state of the ledger, including any
  corrections recorded on [Úprava pohybu](11-uprava-pohybu.md).
- The "K vyřešení" section is the only place that *generates* a sense of
  obligation. Items should disappear from it automatically when their
  underlying condition is resolved — the owner should not have to
  manually dismiss them.

## States
- **Empty (clean morning):** both branch panels populated, recent
  movements list non-empty in normal operation, "K vyřešení" empty.
- **Normal:** as above with one or more items in "K vyřešení".
- **First-ever use / very new install:** branch panels show "zatím
  žádné zboží" placeholders, recent movements show "zatím žádné pohyby",
  "K vyřešení" empty. No errors.
- **Error:** if a branch panel cannot load for some reason, the panel
  shows an inline error with a retry link and the rest of the screen
  remains usable.
- **After successful action:** this screen does not itself produce
  successful actions. It is a launchpad.

## What this screen explicitly does NOT do
- Does not allow recording new movements. Use
  [Příjem zboží](06-prijem-zbozi.md) or
  [Výdej zboží](07-vydej-zbozi.md).
- Does not allow editing dodací listy.
- Does not allow editing movements directly (only as a jumping-off
  point into [11](11-uprava-pohybu.md)).
- Does not show Říčany as a branch panel — Říčany does not hold tracked
  stock, see [`../warehouses.md`](../warehouses.md).
- Does not show financial totals (turnover, margin). The system feeds
  the accountant; it is not a finance view.

## Open questions for this screen
- Whether the "K vyřešení" section needs explicit dismissal vs.
  auto-resolution. Default assumption is auto-resolution; an item
  disappears when its underlying condition is resolved.
- Whether to show simple time-window charts (movement counts last 7 / 30
  days). Defer — could turn this from a calm dashboard into a numbers
  wall.
