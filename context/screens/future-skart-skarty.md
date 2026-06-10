# Skartace / Write-off

**Not in MVP. Documented now to keep the data model honest.**

This screen does not ship with the first usable release. In MVP, any
write-off / shrinkage / damage at a branch is handled via the
[Úprava pohybu](11-uprava-pohybu.md) correction flow with an explanatory
reason ("rozsypáno", "expirováno", "poškozeno"). This screen is
documented so the data model can later promote **odpis** to a
first-class movement type without rework.

The MVP-vs-future split here is itself the central open question — see
"Open questions for this screen" below.

## Purpose
Record an **odpis** — a write-off of stock that is unsellable (damaged,
expired, spilled, destroyed). The screen exists to give shrinkage and
loss the same dignity as příjem and výdej: a structured event with a
typed reason, recorded at the moment it happens, not folded into a
later correction.

The colloquial **skartace** is treated as one reason code under odpis
(destruction of unsellable goods), per
[`../domain-glossary.md`](../domain-glossary.md).

## Who uses it
- Branch staff at the moment the loss is discovered. Phone-friendly
  because losses tend to happen on the warehouse floor, not at a desk.
- Owner and Karolína for any branch.

## What it shows
- Header "Nový odpis na pobočce <branch name>".
- An issue **date**, defaulting to today.
- A **lines** area, each line:
  - **Variant picker** (per
    [`../decisions/0006-pack-size-product-variant.md`](../decisions/0006-pack-size-product-variant.md)).
  - Quantity in the variant's unit, positive — the system treats the
    line as a decrement internally.
  - Optional šarže (optional per
    [`../decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md)).
  - **Důvod odpisu** picker, with codes such as:
    - "poškozeno"
    - "expirováno"
    - "rozsypáno"
    - "skartováno"
    - "jiné" (with a required free-text qualifier).
  - Optional per-line note.
- An "Přidat řádek" action.
- Optional **doklad / fotografie** attachment — only relevant once
  attachments are supported.
- An **operátor** display.
- Primary action "Uložit odpis".
- Secondary action "Zrušit".

## What you can do here
- Set the date.
- Add and remove lines, with variants, quantities, and reason codes.
- (If enabled) attach photo evidence.
- Save the odpis.
- Cancel and discard.

## What it links to / from
- Reached from:
  - Future "Nový odpis" affordance on
    [Přehled pobočky](03-prehled-pobocky.md) — does not exist in MVP.
  - Main navigation (future).
- Goes to:
  - [Přehled pobočky](03-prehled-pobocky.md) on save.
  - [Historie pohybů](10-historie-pohybu.md) where the resulting odpis
    movement appears under its own type.

## Business rules & validation
- Branch is fixed by operator scope.
- At least one line.
- Quantity per line must be positive and must not exceed current on-hand
  at this branch.
- Reason code is required on every line.
- "Jiné" requires a non-empty free-text qualifier.
- Date cannot be in the future; significantly past dates produce a soft
  confirmation.
- No customer, no dodací list, no e-mail.
- Edits to a recorded odpis follow the
  [Úprava pohybu](11-uprava-pohybu.md) correction model — the audit
  trail and reason field apply equally.
- The odpis is visible in [Historie pohybů](10-historie-pohybu.md) under
  type "odpis" and can be filtered by reason code (a future filter
  refinement).

## States
- **Empty (just opened):** branch fixed, date = today, one empty line.
- **Normal:** at least one line with item, quantity, and reason.
- **Validation error:** inline messages.
- **Quantity exceeds on-hand:** inline warning, save blocked.
- **Saving:** "Ukládám…" state.
- **After successful save:** redirect to
  [Přehled pobočky](03-prehled-pobocky.md) with transient confirmation
  "Odpis byl uložen".

## What this screen explicitly does NOT do
- Does not generate any external document. The accountant is informed
  via the future [Export pro účetní](future-export-uctarne.md) or via
  ad-hoc reporting.
- Does not e-mail anyone in MVP-of-the-future-feature.
- Does not transfer stock — odpis is destruction, not movement.
- Does not allow negative on-hand. If reality shows less stock than
  the ledger does (manko discovered without obvious damage), the
  correct flow is a future **inventura** reconciliation, not an
  odpis.

## Open questions for this screen
- The **central MVP question**: is odpis a first-class movement type
  with its own screen and reason codes (this screen, eventually), or
  is it just an [Úprava pohybu](11-uprava-pohybu.md) correction with
  a reason like "skartace"? See *Shrinkage / damage as first-class
  movement type* in [`../open-questions.md`](../open-questions.md).
  MVP handles it as a correction; this screen is documented in
  anticipation of the answer flipping to "first-class".
- Photo / attachment support — only worth designing once the answer
  to the above is "first-class".
- Whether odpis lines should be reportable separately to the accountant
  (loss is tax-deductible in some contexts) — defer to the accountant
  conversation that also drives
  [Export pro účetní](future-export-uctarne.md).
- The **inventura** boundary: shrinkage discovered during a stock-take
  may belong to inventura's reconciliation flow rather than to odpis.
  Open. See *Inventura (stock-take) workflow shape* in
  [`../open-questions.md`](../open-questions.md).
