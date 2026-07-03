# Správa uživatelů / User management

## Purpose
Administer who can use the system and at what scope. Petr and Karolína
add accounts when a new person starts, disable them when someone leaves,
and reset access when something goes wrong. Deliberately small: there
are around six active users at any time and a budget of about twenty
total (per [`../people-and-roles.md`](../people-and-roles.md)).

## Who uses it
- Petr and Karolína only. Desktop. Rarely — onboarding events, not
  daily.

## What it shows
- Header "Uživatelé".
- A simple table of accounts:
  - Jméno.
  - Přihlašovací identifikátor — **e-mail address** (decided on
    [01](01-prihlaseni.md)).
  - Role: "vlastník / správce" (Petr, Karolína), "obsluha pobočky"
    (branch staff).
  - Pobočka (for branch staff): Týniště nad Orlicí / Sezimovo Ústí.
  - Stav: aktivní / deaktivovaný.
  - Naposledy přihlášen.
- A "Přidat uživatele" action.
- A count of active accounts and a reminder of the budget ("aktivních:
  N z přibližně 20 plánovaných").

## What you can do here
- Add a user — opens a small inline form: jméno, identifier, role,
  branch (required if role = "obsluha pobočky"), initial password
  handling (see business rules).
- Edit a user — name, role, branch, status.
- Deactivate / reactivate a user — preserves their identity and
  history attribution, but blocks login.
- Trigger a password reset for a user.
- Open an audit-style view of the user's actions (defer — for MVP,
  fall back to filtering [Historie pohybů](10-historie-pohybu.md) by
  operator).

## What it links to / from
- Reached from:
  - Main navigation (admin section), owner-level users only.
- Goes to:
  - Stays within the user-management flow. Filtering history by an
    operator opens [Historie pohybů](10-historie-pohybu.md).

## Business rules & validation
- Only owner-level users can reach this screen.
- A branch-staff user must have exactly one branch assignment. They
  cannot be assigned to "both branches" — see the permissions matrix
  in [`../people-and-roles.md`](../people-and-roles.md).
- An owner-level user has no branch — they see both.
- Identifier must be unique among active accounts.
- **Deletion is not supported**, only deactivation. Deleting a user
  who recorded historical movements would orphan the operator
  attribution on those movements.
- The system never displays existing passwords. Resetting issues a
  new credential through whatever flow the implementation chooses
  (e-mail link or admin-set temporary password — deferred to
  user-management design).
- Owner-level users may demote themselves only if at least one other
  active owner-level user remains. The system refuses the last-owner
  demotion / deactivation.

## States
- **Empty (impossible in practice — at least Petr exists):** an
  unreachable state by construction. Mentioned only because the
  template asks.
- **Normal:** table of users.
- **Add / edit form open:** rest of the screen disabled.
- **Validation error:** inline messages (missing branch on branch
  staff, duplicate identifier, last-owner protection).
- **After successful action:** stay on this screen; transient
  confirmation ("Uživatel byl přidán", "Změny uloženy",
  "Uživatel deaktivován").

## What this screen explicitly does NOT do
- Does not allow self-registration from outside this screen.
- Does not allow deletion.
- Does not invent finer permissions than the four roles in the
  matrix in [`../people-and-roles.md`](../people-and-roles.md).
- Does not handle multi-branch staff (one branch per branch-staff
  account, by explicit constraint).
- Does not log who reset whose password as a separately viewable audit
  feed in MVP — fold into general operational logging at the
  implementation layer.

## Open questions for this screen
- **Password-reset mechanism shape** — e-mail link (recommended,
  uses the same SMTP config from [14](14-nastaveni.md)) vs admin
  temporary password. MVP default: e-mail link.
- Whether short-term help (seasonal hands) should have a built-in
  "expiry date" on accounts — defer; deactivation by hand is fine at
  this scale.

> Per-user activity view is folded into
> [Historie pohybů](10-historie-pohybu.md) via the operator filter
> — no separate sub-screen in MVP.

## UX refresh — Phase 2 (2026-07-03)

Uživatelé restyled per mockup `15` (head-card + count, mono email/last-login,
stav pills); locked `.js-confirm` deactivate preserved.
