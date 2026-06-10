# Úprava pohybu / Edit historical movement

## Purpose
The detail view of a single movement (příjem, výdej — including
internal výdeje to Říčany per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md),
and in the future odpis or mixing job) and — for owner-level users —
the place where corrections are recorded. Every correction is an
**audited change**: the system stores the original value, the new
value, who, when, and why. The owner reserves the right to correct
anything; the system's job is to make sure nothing is silently
overwritten.

This screen folds together what an earlier writing pass called
"detail pohybu" and "audit log" (see the reconciliation note in
[`README.md`](README.md)). The flat audit log across all movements is
surfaced via the "Pouze editované" filter on
[Historie pohybů](10-historie-pohybu.md).

## Who uses it
- Petr and Karolína: every correction lives here. Desktop.
- Branch staff: open the same screen in **read-only** mode to inspect
  a movement they recorded.

## What it shows
- Header naming the movement type and date, e.g. "Výdej —
  <datum> — pobočka Týniště".
- A **summary block**:
  - Type (příjem / výdej / future: odpis / mixing job).
  - Datum a čas.
  - Pobočka.
  - Protistrana — supplier on příjem; odběratel on výdej (Říčany
    shows here for internal výdeje per
    [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](../decisions/0030-vydej-default-ricany-supersedes-0004.md));
    (for future odpis) reason; (for future mixing job) source recipe.
  - Operátor původní (the person who recorded the original entry).
  - For a výdej: a link to its dodací list on
    [Detail dodacího listu](09-detail-dodaciho-listu.md).
  - "Editováno" status — none / N edits — with a link that scrolls to
    the audit trail block.
- A **lines** block, each line:
  - **Product** (catalogue), per
    [`decisions/0028-mass-only-supersedes-0006.md`](../decisions/0028-mass-only-supersedes-0006.md)
    — shown as "<Product name>".
  - Quantity in **kg** (3 dp per
    [`decisions/0003-primary-unit-kg-decimals.md`](../decisions/0003-primary-unit-kg-decimals.md)).
  - Optional šarže (optional per
    [`decisions/0001-sarze-tracking.md`](../decisions/0001-sarze-tracking.md);
    operator can fill or leave blank on save).
  - Per-line note. Reason text on the edit is free-form — no
    hardcoded conventions (per
    [`decisions/0033-prebalovani-out-of-scope-supersedes-0013.md`](../decisions/0033-prebalovani-out-of-scope-supersedes-0013.md)
    there is no `"přebaleno"` convention; přebalování is not a
    workflow).
- For owner-level users only, an "Upravit" action that toggles the
  screen into edit mode.
- In edit mode, every field above becomes editable plus:
  - A **required reason field** ("důvod úpravy") — free text Czech —
    must be non-empty to save.
  - "Uložit změny" and "Zrušit" actions.
- An **audit trail** block at the bottom — a list, newest first, of
  every prior edit on this movement:
  - Kdy.
  - Kdo (the editor).
  - Důvod úpravy.
  - A side-by-side diff: original values vs. new values, per field
    changed. Unchanged fields are not shown to keep the diff readable.
- For a výdej: a small reminder that the dodací list has been
  emailed; link to
  [Detail dodacího listu](09-detail-dodaciho-listu.md) and a warning
  that **saving this correction will auto-regenerate the PDF and
  auto-email it** to the original recipients per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md).
  The reason text the editor enters is included in the `[OPRAVA]`
  e-mail body. No separate confirm.

## What you can do here
- Read the movement and its audit trail.
- (Owner-level) Enter edit mode.
- (Owner-level) Edit any field — type, date, branch, counterparty,
  lines, šarže, notes. Yes, even branch — see business rules.
- (Owner-level) Enter a reason and save changes.
- (Owner-level) Cancel edit and discard changes.
- For a výdej: navigate to its dodací list.

## What it links to / from
- Reached from:
  - [Historie pohybů](10-historie-pohybu.md) — primary entry point.
  - [Přehled vlastníka](02-prehled-vlastnik.md) — "K vyřešení" items
    and recent movements rows.
  - [Detail dodacího listu](09-detail-dodaciho-listu.md) — "Otevřít
    výdej" link.
- Goes to:
  - [Detail dodacího listu](09-detail-dodaciho-listu.md) for výdeje.
  - [Historie pohybů](10-historie-pohybu.md) on save / cancel.

## Business rules & validation
- Only owner-level users can edit. Branch staff are read-only.
- Saving an edit is allowed only when the **reason** field is non-empty.
  The system does not accept a silent correction.
- Every save writes a fresh audit-trail entry that captures, per
  changed field: original value, new value, editor identity, timestamp,
  and the reason text. **Unchanged fields are not recorded** to keep the
  trail readable, but the audit entry's timestamp + reason apply to the
  edit as a whole.
- A correction must not put a branch's stock below zero. If the edit
  would, the screen refuses to save and explains why (the operator must
  resolve the chain of corrections — e.g. also correct the offending
  later movement).
- Changing the **branch** of a movement is allowed but treated as
  exceptional: the screen warns that both branches' stock figures will
  shift and asks for explicit confirmation.
- Changing the **type** of a movement (e.g. příjem → výdej) is
  **forbidden**. If the original was the wrong type entirely, the
  correct path is to reduce the wrong movement's quantity to zero (an
  edit with reason "chybně zaevidováno jako příjem") and to record a
  fresh movement of the right type. This avoids untraceable polymorphic
  corrections.
- For a výdej linked to a dodací list, the dodák is re-rendered to
  reflect the corrected lines (see
  [Detail dodacího listu](09-detail-dodaciho-listu.md)) and the dodák
  is marked "editováno". The system **auto-regenerates and auto-emails**
  the new dodák to the recipients of the prior send per
  [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md);
  subject is prefixed `[OPRAVA]` and the body references the correction
  reason. The send is logged in the per-dodák version+send audit table on
  [09](09-detail-dodaciho-listu.md).
- A correction is itself never silently deleted. If the editor enters
  edit mode and saves with no changes and no reason, the save is a
  no-op (no audit entry).

## States
- **Read mode (everyone):** all fields visible, no edit affordances
  for branch staff.
- **Read mode with audit history (owner-level):** edit button visible;
  audit trail populated if there have been prior edits.
- **Edit mode:** fields editable, reason field required, "Uložit" /
  "Zrušit" visible.
- **Validation error:** inline messages (missing reason, edit would
  drive stock negative, attempt to change type).
- **Confirmation prompt:** changing branch, changing date significantly,
  or zeroing a quantity that has downstream issues.
- **Saving:** "Ukládám změny…" state.
- **After successful save:** return to
  [Historie pohybů](10-historie-pohybu.md) with the updated row, or
  stay on this screen with the new audit-trail entry now visible at
  the top of the trail block — choice deferred but stay-on-screen is
  the default since the owner often wants to verify.

## What this screen explicitly does NOT do
- Does not delete movements. There is no delete action; the closest
  is an audited edit that zeroes the quantity with a reason.
- Does not change the *type* of a movement (see business rules).
- Does not let branch staff edit anything.
- Does not produce a separate accountant-export entry per correction —
  that integration is future (see
  [Export pro účetní](future-export-uctarne.md)).

> The re-email on a corrected výdej is **automatic**, not silent, per
> [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md).
> The operator sees a warning before saving; the send is logged.

## Open questions for this screen
- Whether **odpis** (write-off) should be a first-class movement
  type with its own editor, or remain handled here through a
  correction with a reason code. See
  [Skartace](future-skart-skarty.md) and the *Decide later* entry in
  [`../open-questions.md`](../open-questions.md). MVP: handle via
  correction.

> Auto re-issue / re-email of corrected dodáky is closed by
> [`decisions/0007-auto-reissue-corrected-dodaky.md`](../decisions/0007-auto-reissue-corrected-dodaky.md):
> auto-regenerate + auto-email.
>
> A standalone audit-log screen is closed by the scaffold note in
> [`README.md`](README.md): folded into the "Pouze editované" filter on
> [10](10-historie-pohybu.md) + per-movement audit trail here.
