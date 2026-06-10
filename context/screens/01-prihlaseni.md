# Přihlášení / Login

## Purpose
The single entry point to the system. A user identifies themselves so that
the rest of the application can show them the right branch's stock,
respect their permissions, and attribute their actions in the audit trail.

## Who uses it
Every human who touches the system: Petr, Karolína, the two Týniště
operators, the two Sezimovo Ústí operators, and any short-term help.
Used on desktop in the office and on a phone in the warehouse aisle.
Frequency: once per working session.

## What it shows
- Kasia vera branding (logo, name).
- A short title that names the system in Czech.
- An identifier field — **e-mail address** (label: "E-mail"). E-mail
  is the universal identifier and supports the "zapomenuté heslo"
  reset flow without admin intervention.
- A password field.
- A "Přihlásit" action.
- An optional "zapomenuté heslo" link.
- Czech-language inline error text when login fails.
- Application version or build marker in a discreet footer, useful when
  the owner reports a bug.

## What you can do here
- Submit credentials with the "Přihlásit" button (or Enter key).
- Request a password reset via "zapomenuté heslo", if that flow is built.
- Nothing else. No self-registration. No "create account" link.

## What it links to / from
- Reached from: any unauthenticated URL in the system (redirect target).
- Goes to:
  - [Přehled vlastníka](02-prehled-vlastnik.md) — for Petr and Karolína.
  - [Přehled pobočky](03-prehled-pobocky.md) — for branch staff, scoped
    to the branch they are assigned to.

## Business rules & validation
- Account is created **only** by an admin on
  [Správa uživatelů](13-sprava-uzivatelu.md). There is no public signup.
- Each account is bound to a role and, for branch staff, to one branch.
- After login, the user's role and branch scope determine which screens
  are visible in navigation.
- Failed login attempts must not reveal whether the username or the
  password was the wrong one (single generic error message).
- Sessions persist long enough that operators are not re-prompted
  mid-shift, but short enough that an unattended shared device does not
  stay logged in for days.

## States
- **Empty:** fresh visit, both fields blank, no error.
- **Normal:** user typing, no error yet.
- **Error / disallowed:** generic "neplatné přihlašovací údaje" message
  shown beneath the form; fields remain populated except the password.
- **Locked / disabled account:** message that the account is inactive
  and to contact the administrator. The user is not told why.
- **After successful action:** redirect to the role-appropriate landing
  screen (02 or 03 above).

## What this screen explicitly does NOT do
- No self-service registration.
- No customer login (B2B customers never log in — they receive dodací
  listy by email).
- No social / external SSO in MVP.
- No second-factor authentication in MVP.

## Open questions for this screen
- Password reset flow shape (e-mail link, admin-issued temporary
  password) — deferred to user-management design on
  [`13-sprava-uzivatelu.md`](./13-sprava-uzivatelu.md).
- Session lifetime policy — deferred to operational handover (after
  the first tech-stack decision).
