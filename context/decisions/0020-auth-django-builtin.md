# 0020 — Authentication: Django auth + groups, e-mail + password

> **Amended by [0047](./0047-design-review-gallery.md)** — the "no public surface beyond /login/ and /healthz/" line is narrowed to *application* views and data; a static, data-free design-review gallery is intentionally public under `/static/navrhy/` (entry `/navrhy/`).
>
> **Second amendment by [0049](./0049-public-site-and-sklad-split.md)** — a public marketing site (real Django views) is now intentionally login-exempt at `/`; the entire warehouse app (every gated screen + the auth chain) moves under `/sklad/`. 0020's auth posture for all warehouse screens and data is unchanged — those simply live under `/sklad/` now.

## Context

R9 in [`../tech-options.md`](../tech-options.md): two roles —
**vlastník / správce** (Petr, Karolína; both branches) and **obsluha
pobočky** (branch staff; scoped to one branch). No SSO, no SAML, no
2FA in MVP per
[`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
("password + optional magic-link is plenty for ~6 users").

[`../screens/01-prihlaseni.md`](../screens/01-prihlaseni.md) locked
the login identifier as e-mail (not username).
[`../screens/13-sprava-uzivatelu.md`](../screens/13-sprava-uzivatelu.md)
defines the management surface.

## Options considered

- **Django built-in auth + groups.** `User` model with e-mail as
  the login field (custom `AbstractUser` swapping `USERNAME_FIELD =
  "email"`). Two groups: `vlastnik`, `obsluha`. Branch scoping via
  a `branch` FK on the user. View-level permission checks via
  decorators / mixins.
- **django-allauth.** Adds social/OAuth flows and a polished
  signup/login UI. Overkill — no social login is wanted.
- **Magic-link only.** Friendlier for non-technical staff but adds
  e-mail-delivery latency to every login. With ~6 users and shared
  branch laptops, the password flow with browser-remembered creds
  is the lowest-friction option.
- **Keycloak / external IdP.** Conference-talk shaped for 6 users.
- **2FA in MVP.** Friction outweighs the threat model — branch
  laptops on a small Czech business LAN; the data is dodáky and
  stock, not credentials. Future decision can add TOTP when the
  threat model changes.

## Choice

**Django's built-in auth with a custom user model (`email` as
`USERNAME_FIELD`) and two groups (`vlastnik`, `obsluha`).** Branch
scoping by a `branch` FK on the user (null for `vlastnik`).
Password reset via Django's built-in e-mail flow (uses the same
SMTP backend from [`0019`](./0019-email-smtp-sync.md)). No 2FA, no
SSO, no social login.

Permissions enforced at the view layer via decorators
(`@vlastnik_required`, `@branch_scoped`). Editing historical
movements is owner-only per the R9 rule
([`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md)).

## Rationale

- Six users, shared laptops on a known LAN, no external party
  access. The threat surface does not justify SSO or 2FA in MVP.
- Django auth covers the whole surface — password storage with
  modern hashing (argon2 / bcrypt), CSRF, session cookies, password
  reset via e-mail — without third-party dependencies.
- E-mail as login identifier matches the screen lock and the way
  staff already think about identity.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The `User` model in the first models pass extends `AbstractUser`,
  sets `USERNAME_FIELD = "email"`, adds a `branch` FK (nullable).
- View-level permission decorators (`@vlastnik_required`,
  `@branch_scoped`) implemented in the next pass.

**Forecloses (without follow-on decision):**

- SSO / SAML / OAuth integrations.
- 2FA / TOTP — re-opens via a future decision when the threat model
  warrants it.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R9 (two roles, branch scoping, owner-only edits).

**Makes implementable (0001–0013):**

- The owner-only edit gate on
  [`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md)
  — `@vlastnik_required` on the edit view.
- The branch-scoped list on
  [`../screens/03-prehled-pobocky.md`](../screens/03-prehled-pobocky.md)
  — filter by `request.user.branch` when the user is `obsluha`.
