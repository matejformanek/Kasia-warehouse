# 0049 — SMTP source of truth: Settings DB first, env as fallback

**Date:** 2026-06-26
**Decider:** Matej (post `/plan-review-comprehensive`; Petr's mail
provider has issued server details for `mail.kasia.cz:587` STARTTLS,
`aplikace@kasia.cz` mailbox + password landing out-of-band).
**Status:** Accepted.

**Refines:**
[`0019`](./0019-email-smtp-sync.md) — the synchronous send +
`fail_silently=False` + `DodaciListEmailLog` FAILED-row contract is
**unchanged**; only the credential-read layer moves from env-only to
DB-first.
[`0037`](./0037-settings-singleton.md) — plaintext `smtp_password`
on `Settings` and the `PasswordInput(render_value=False)` widget are
**unchanged**.

**Supersedes:** none.

## Context

Until today, two parallel SMTP configuration surfaces coexisted in
the codebase:

1. **Django env vars** (`EMAIL_HOST`, `_PORT`, `_USE_TLS`,
   `_HOST_USER`, `_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`) — read at
   process boot from `/srv/kasia/.env` per
   [`0019`](./0019-email-smtp-sync.md). These drove the real dodák
   send via Django's default `EmailMessage.send()` connection.
2. **`Settings.smtp_*` DB fields** (host, port, use_tls, user,
   password, email_from_address, email_from_name) — added in
   [`0037`](./0037-settings-singleton.md) for the operator-editable
   `/nastaveni/` UI. These drove the test button at
   `settings_test_smtp` via an explicit `get_connection(...)` call,
   but **not** the real dodák send.

Result: Karolína (vlastník) could populate the SMTP fields through
the UI, click "Otestovat odeslání", get a green ✓, yet every real
dodák send would still go through the env-time credentials. The
test button was misleading; rotating SMTP password required a box
edit + container restart instead of a UI save.

This contradicts the operator-CRUD tier in
[`0040`](./0040-operator-crud-tiering.md): vlastník-tier edits should
take effect immediately without a Matej-mediated redeploy.

## Options considered

- **A — Keep env as source of truth; remove the DB fields.** Reject:
  rotating SMTP password becomes a deploy. Doesn't match the
  vlastník-can-self-serve posture in 0040. Throws away the existing
  UI affordance from 0037.
- **B — Make DB the only source; drop env entirely.** Reject: a
  fresh box on first boot has no Settings row populated until an
  operator opens `/nastaveni/`. Password reset emails
  (`accounts/views.py`, env-driven, fires before the operator ever
  logs in to populate Settings) would break. Also forces a
  migration to widen `Settings.smtp_use_tls` to a nullable boolean
  to express "fall through to env", which is solving a
  doesn't-exist problem.
- **C — DB-first, env as fallback for blank string fields; DB
  always wins for `smtp_use_tls`.** Single shared helper
  `_smtp_connection_from_settings(s)` builds the SMTP connection;
  test button + real sends call the same helper.
- **D — Encrypt `smtp_password` at rest.** Reject for now per
  [`0037`](./0037-settings-singleton.md) — plaintext-at-rest is
  acceptable for the 6-user box; revisit if Kasia grows or the
  password is reused across services.

## Choice

**Option C.** The helper lives in `inventory/services.py`:

```python
def _smtp_connection_from_settings(s):
    """Build an SMTP connection from Settings DB, with env as
    fallback for string fields.

    Contract:
      - host / username / password: ``None`` when the DB field is
        blank → Django's default backend reads env.
      - port: ``Settings.smtp_port`` is non-nullable with default
        587, so the DB value effectively always wins. Env
        ``EMAIL_PORT`` is not consulted. To change ports, operators
        flip the DB field.
      - use_tls: same shape as port — ``Settings.smtp_use_tls`` is
        non-nullable with default True; DB always wins, env
        ``EMAIL_USE_TLS`` is not consulted. If a future operator
        wants STARTTLS off, they flip the DB checkbox.
      - Called at execution time (e.g. inside
        ``transaction.on_commit``), not at registration time —
        so it always reads the LIVE Settings, not a snapshot from
        when the výdej started.
    """
    from django.core.mail import get_connection
    return get_connection(
        host=s.smtp_host or None,
        port=s.smtp_port or None,
        username=s.smtp_user or None,
        password=s.smtp_password or None,
        use_tls=s.smtp_use_tls,
        timeout=10,
    )
```

Wire-up:

- `send_dodaci_list_email` (real customer dodák send) builds the
  connection via the helper, passes `connection=` to
  `EmailMessage`, and keeps the existing `fail_silently=False` +
  `DodaciListEmailLog` FAILED-row contract from 0019 unchanged.
- `send_low_stock_summary` (per
  [`0045`](./0045-low-stock-summary-email.md)) uses the same
  helper.
- `settings_test_smtp` (the "Otestovat odeslání" button) is
  refactored onto the same helper, eliminating the two duplicated
  `get_connection(...)` blocks and making test ≡ real send by
  construction.
- `accounts/views.py` (password reset) stays env-driven — Django's
  `PasswordResetView` uses `DEFAULT_FROM_EMAIL`; rewiring it would
  reach into Django internals for marginal value.

## Rationale

- **Single source of truth, no schema churn.** The DB fields
  already exist (added by 0037); the env vars stay as documented
  fallback. No migration.
- **Vlastník self-serve.** Karolína / Matej can rotate the SMTP
  password through `/nastaveni/` without a redeploy. Matches
  [`0040`](./0040-operator-crud-tiering.md).
- **Test button stops lying.** After this change, "Otestovat
  odeslání" exercises the exact code path a real dodák send uses.
- **Fresh-box bootstrap still works.** The first dodák from a
  fresh box still sends because env-time `EMAIL_HOST_*` are picked
  up via the `or None` fall-through.
- **Right-sized.** A nullable `smtp_use_tls` would force a
  migration to model "fall through to env on TLS" — but our env
  is `TLS=1` and the DB default is `True`; both agree, so the
  branch is hypothetical. We don't pay migration cost for a
  scenario that doesn't exist at 6 users (per
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)).

## Explicit non-goals

- Not introducing a nullable `smtp_use_tls` BooleanField or a
  nullable `smtp_port` field. DB-only for TLS and port is the
  honest contract; document it in the helper docstring instead.
  Both prod env and DB default agree (TLS=1, port=587); a fall-
  through branch for these would force a migration to solve a
  problem that doesn't exist at 6 users.
- Not encrypting `smtp_password` at rest. See 0037.
- Not rewiring `accounts/views.py` password reset. Env-only is
  fine for that path.
- Not adding `EMAIL_USE_SSL` support. Provider answered STARTTLS
  on 587; SSL-on-465 is not in play.

## Consequences

**Unblocks:**

- Mail go-live on prod: `EMAIL_HOST_PASSWORD` lands in
  `/srv/kasia/.env` (out-of-band from provider), and the same
  values are also populated through `/nastaveni/` as deliberate
  redundancy. Either layer keeps mail working if the other is
  blank.
- Future SMTP password rotations via UI alone — no
  `docker compose up -d` round-trip.

**Forecloses (without follow-on decision):**

- Per-environment SMTP differences via Settings (because
  `Settings` is a singleton). Acceptable: dev sends via locmem
  backend regardless; prod has one mailbox.

**Touches:**

- `inventory/services.py` — new helper + two call sites.
- `inventory/views.py:settings_test_smtp` — collapse onto helper.
- `inventory/models.py:Settings.smtp_password` — add `help_text`.
- `kasia/templates/inventory/settings_form.html` — one Czech
  inline note under the SMTP section.
- `inventory/tests.py` — 4 new tests.
- `context/state.md` + `context/screens/14-nastaveni.md` —
  precedence note.

**No schema changes**: `Settings.smtp_*` fields already exist per
[`0037`](./0037-settings-singleton.md).
