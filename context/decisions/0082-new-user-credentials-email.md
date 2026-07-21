# 0082 — Auto-generate + e-mail new-user credentials

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, after using the app)
**Status:** Accepted
**Amends:** [`0075`](./0075-email-outbox-log.md) (new `EmailLog.category`)

## Context

Creating a user (Správa uživatelů, screen 13) required the vlastník to invent a
password and communicate it out-of-band. Matej wants the system to generate the
password and e-mail the new user their login (their e-mail) + password
automatically, so onboarding is one click and the credential travels through the
audited outbox instead of a side channel.

## Options considered

- **System-generated password, e-mailed, always sent** — no toggle. Simplest;
  the vlastník never sees or types a password. The mail tells the user to change
  it via the existing in-app change-password page.
- **Invite link / set-password token flow** — Django's password-reset machinery,
  no plaintext ever mailed. More secure, but more moving parts (token expiry,
  a landing page, "link expired" support load) than warranted for ~6 internal
  users onboarded by the owner in person/over the phone.
- **Keep manual password entry** — status quo. Rejected: the whole point is to
  remove the out-of-band step.

## Choice

On user creation the form **generates a ~12-char random password** (unambiguous
alphabet, excludes `O0Il1`) via `django.utils.crypto.get_random_string`, creates
the user with it, and the view **always** e-mails the new user their login
(their e-mail) + the password through `send_and_log` under a new
`EmailLog.Category.NEW_USER_CREDENTIALS`. The mail links to the login page and
to the in-app change-password page. No toggle; the send never re-raises so a mail
outage can't block user creation. The create form drops its two password fields.

## Rationale

For a ~6-user internal tool onboarded by the owner, e-mailing a generated
plaintext password (that the user is told to change immediately) is an
acceptable, boring, low-support-load choice — right-sized per
[`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md).
The credential is logged in the outbox (`EmailLog`), so there is an audit trail.
The token/invite flow buys real security value only against threats this tool
doesn't face (public signup, untrusted networks at scale); its extra surfaces
aren't worth it here. Recorded explicitly because e-mailing a plaintext password
is a security-relevant decision, not an implementation detail.

## Consequences

- `accounts/forms.py`: `UserCreateForm` loses `password1`/`password2` + the
  `clean()` override; gains a module-level `generate_initial_password()`; `save()`
  stashes `user._raw_password`.
- `inventory/services/email.py`: new `send_new_user_credentials(user,
  raw_password, sent_by=None)`, re-exported from the services package.
- `EmailLog.Category` gains `NEW_USER_CREDENTIALS` (migration `0022`, folded with
  [`0081`](./0081-per-recipient-notification-preferences.md)).
- `accounts/views.py::user_create` calls the mailer after `form.save()`.
- `user_form.html` replaces the password block with a static note.
- Plaintext password travels by e-mail. Accepted for this scale; the mail
  instructs the user to change it via the existing change-password page.
- Links in outgoing e-mails must be **absolute** (scheme + host + path), not
  bare `reverse()` paths — a path isn't clickable in a mail client. Since the
  send path is off-request, a new per-deployment env knob `SITE_BASE_URL`
  (settings reader defaulting to `http://localhost:8000`, documented in
  `.env.example`, set to `https://kasia.cz` on the box) is prepended via the
  `_absolute_url()` helper in `inventory/services/email.py`. Applies to the
  credentials mail **and** the Podpora notification (0081).
