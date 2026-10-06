# 0104 — App security hardening: own-branch guards, roles fail closed, login lockout (supersedes 0099 in part)

**Date:** 2026-10-06
**Decider:** Matej
**Status:** Active

## Context

The repository is public and the app is live on kasia.cz. A read-only audit
(app code, deploy, dependencies, live site) found no SQL injection, XSS or CSRF
hole and login enforced globally, but these application-level gaps:

1. **IDOR on movements.** `movement_edit`, `prijem_confirm`,
   `prijem_plan_cancel` and `movement_saved` looked a `Movement` up by pk with
   no branch check, so an *obsluha (branch staff)* could edit, confirm, cancel or
   view another branch's movements by URL. Dodáky already had the guard
   ([`0040`](./0040-operator-crud-tiering.md) — `dodaci._deny_other_branch`);
   movements did not. The edit forms also let obsluha move a movement to
   another branch.
2. **Other-branch stock leaked to obsluha** in three places: the míchání preview
   partial (`?branch=` any id), the výdej live-check `stock_map` (all branches)
   and the product-edit „Pobočky" carry rows.
3. **Roles failed open.** `User.is_vlastnik` was "superuser OR not in
   `obsluha`", so any account without a group was an owner. This came from
   Pass 3d (`state.md` 2026-06-12, so admin-created accounts would land on the
   owner dashboard during the shadow run) and is restated in
   [`0099`](./0099-vydej-branch-request-notification.md) § Consequences
   („`is_vlastnik` is True for superusers *and* unassigned users", which cites
   0034 — that link actually points at the shadow-run decision; the clause never
   had a decision of its own). `_sync_role` only ever managed the `obsluha`
   group, so on prod **no** account was in `vlastnik`: users 6, 10, 13, 14 were
   owners purely by being groupless.
4. **No login brute-force protection** on `/sklad/prihlaseni/` or `/admin/`,
   and the public password-reset form could be used to spam inboxes.
5. **`SECRET_KEY` silently fell back to a hard-coded dev key** when the env var
   was missing.
6. **Sessions lasted Django's default 2 weeks** on shared warehouse PCs.
7. **The XLS recipe importer** read an uploaded workbook without bounds (an
   `.xlsx` is a zip — a 2.5 MB upload can inflate to gigabytes).
8. **Dependency CVEs:** Django 5.2.15 (fixed in 5.2.17), Pillow 12.2.0 (fixed in
   12.3.0).

Infra hardening (backups, SSH, Caddy headers incl. HSTS, CI permissions) is a
separate decision, 0105.

## Options considered

- **Roles:** (a) keep fail-open; (b) fail closed in the property only; (c) fail
  closed + a data migration that preserves every current owner + a login-time
  gate. (b) alone would lock out the four real owners on deploy and still leave
  a groupless user unscoped on the ~37 `is_obsluha and branch_id` filter sites
  (they are neither role, so they see all-branch data).
- **Brute force:** (a) django-axes; (b) a hand-rolled cache counter on login;
  (c) Caddy-level rate limiting (needs a Caddy plugin build). axes is the
  standard, maintained Django answer and also covers `/admin/`.
- **Lockout key:** username only (one attacker locks a user out from
  everywhere), IP only (behind Caddy every request has the proxy's IP → one bad
  actor locks out everyone), or **username + client IP**.
- **CSP / Django-side HSTS / secure-cookie default:** considered and **dropped**
  — see Consequences.

## Choice

1. **Own-branch guard for movements.** A shared
   `deny_other_branch(request, branch_id)` in `inventory/views/_shared.py`
   returns 403 when `user.is_obsluha and user.branch_id != branch_id` (a
   branch-less obsluha is denied everything branch-owned). Applied to
   `movement_edit` (GET+POST), `movement_saved`, `prijem_confirm` (GET+POST)
   and `prijem_plan_cancel`; `dodaci._deny_other_branch` now delegates to it.
   `PrijemEditForm` / `VydejEditForm` take `user` + `movement` and, for obsluha,
   set the `branch` field **`initial = movement.branch_id` together with
   `disabled = True`** (a disabled field takes its value from `initial`;
   without it every obsluha edit would fail "required").
   **Převody (planned transfers) stay unscoped on purpose** — either branch's
   staff may plan/execute one. The planned-transfer detail page links a paired
   movement to `movement_edit` only for a vlastník or the movement's own branch,
   so obsluha is not sent into a 403.
2. **Own-branch stock for obsluha:** `mixing_preview_partial` 403s for another
   branch; the výdej `stock_map` and the product-edit carry rows contain only
   the obsluha's own branch (the carry badges stay read-only per 0053).
3. **Roles fail closed.** `is_vlastnik` = superuser, or in `vlastnik` and not
   in `obsluha`. Migration `accounts/0003_assign_vlastnik_group` adds
   `vlastnik` to **every non-superuser not in `obsluha`, including inactive
   accounts** (prod ids 6, 10, 13, 14 — it preserves today's effective rights
   and promotes nobody; Matej reviews id 14 separately). `_sync_role` now sets
   both groups explicitly (vlastník ↔ `vlastnik`, obsluha ↔ `obsluha`), the
   admin „add user" form exposes `groups`, and the last-owner count mirrors
   `is_vlastnik` with `distinct()`. **Login gate:** the sklad login uses
   `RoleCheckedAuthenticationForm`, which refuses a correct password for any
   non-superuser that is neither vlastník nor obsluha-with-branch, with a Czech
   message.
4. **django-axes** (new dependency, `>=8.3,<9.0`): `AxesStandaloneBackend` +
   `AxesMiddleware`; 5 failures lock the **(username, client IP)** pair for 1
   hour; success resets; `AXES_USERNAME_FORM_FIELD = "username"` (Django's
   login form posts the e-mail as `username`); client IP from
   `accounts.security.client_ip` = the **rightmost** `X-Forwarded-For` entry
   (written by Caddy, which replaces client-sent XFF; `web:8000` is not
   published), else `REMOTE_ADDR`; Czech lockout page
   `registration/locked_out.html` (HTTP 429). Covers `/sklad/prihlaseni/` and
   `/admin/`. **Password reset:** `ThrottledPasswordResetView` allows 5 POSTs
   per client IP per hour via the default (per-process LocMem) cache — no new
   infra; with 3 gunicorn workers the ceiling is ≤ 15/h, still bounded.
5. **`SECRET_KEY` guard:** with `DEBUG` off, a missing key, the old hard-coded
   dev key or the `.env.example` placeholder raises `ImproperlyConfigured` at
   settings import. Skipped under pytest (host `make test` has no env); the
   Docker build (`build-only`) and CI (`ci-only-secret`) pass their own keys.
   Verified before merge that the prod key is none of these (86 chars).
6. **`SESSION_COOKIE_AGE` = 12 h.**
7. **XLS importer caps:** at most 500 rows × 30 columns are read; an `.xlsx`
   whose zip members' uncompressed total exceeds 50 MB (or that is not a valid
   zip) is rejected with a Czech message before openpyxl parses it.
8. **Dependency bumps:** Django 5.2.17, Pillow 12.3.0, psycopg 3.3.6,
   django-htmx 1.29.0. WeasyPrint stays `<70` (its advisory needs
   `xmp_metadata`/`stylesheets` arguments the app never passes); gunicorn stays.

## Rationale

- The IDOR guard mirrors the established 0040 dodák pattern — one helper, one
  message shape, no new concept.
- Fail-closed roles only become safe with the migration (nobody loses access)
  and the login gate (a role-less account can't get a session and fall through
  the `is_obsluha and branch_id` filters as an unscoped user).
- Keying axes on username **and** IP is what makes it a brute-force brake rather
  than a denial-of-service lever; resolving the real client IP is what keeps it
  from keying everyone on the Caddy container.
- A guard that fails the deploy's `migrate` step on a bad key leaves the old
  container serving (`deploy.yml` is `set -e`), so it can't take prod down.

## Date & by-whom

2026-10-06 — Matej.

## Consequences — things this now blocks or unblocks

**Supersedes in part:** [`0099`](./0099-vydej-branch-request-notification.md)
§ Consequences — the clause „`is_vlastnik` is True for superusers *and*
unassigned users" is reversed: an unassigned (groupless) user is no longer a
vlastník and cannot log in. (The rest of 0099 — the výdej request mail to the
branch's obsluha — is unchanged; it still fires for vlastník-issued výdeje.)

**Commits us to:**

- Every new owner account needs the `vlastnik` group — the Správa uživatelů
  form does it; a user created in `/admin/` must get a group there.
- Post-deploy check: `User.objects.filter(is_superuser=False,
  groups__isnull=True).count() == 0`.
- Staff log in at least daily (12 h sessions) — tell Karolína and the branches.
- Break-glass unlock for a locked-out user: `infra/RUNBOOK.md` § 9
  (`axes_reset_username` / `axes_reset`).
- A non-DEBUG process on the host now needs a real `DJANGO_SECRET_KEY` (or
  `DJANGO_DEBUG=1`) even for `manage.py check`; `make test` is unaffected.
- Any new view that loads a branch-owned object by pk calls
  `deny_other_branch` (see `.claude/rules/frontend-and-templates.md` §
  role-scoping).

**Deliberately not done (accepted `check --deploy` warnings):**

- **No CSP.** A self + Google Fonts policy would break ~16 inline sklad
  scripts, the public nav `onclick`, the Umami beacon and the Google Maps
  iframes; there is no known XSS and `X-Frame-Options: DENY` already ships.
- **No Django-side HSTS** (W004 accepted). Caddy adds it for `kasia.cz` only
  (0105); a Django setting would also pin HSTS on `https://localhost` in local
  `make up`.
- **Secure-cookie default unchanged** — it stays an opt-in env reader per
  `infra-as-code.md`; prod already sets `DJANGO_SECURE_COOKIES=1`.
  `SECURE_PROXY_SSL_HEADER` is already set unconditionally.
- **No `SECURE_SSL_REDIRECT`** (W008 accepted) — Caddy redirects.

**Rollback:** re-tagging the previous image is safe — old code ignores the
extra `vlastnik` group memberships and the axes tables.
