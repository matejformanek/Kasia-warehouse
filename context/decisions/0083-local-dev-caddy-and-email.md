# 0083 — Local-dev Caddy + e-mail overrides (env-driven, prod-safe)

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, while test-driving the local stack)
**Status:** Accepted
**Relates to:** [`0024`](./0024-tls-caddy.md) (Caddy), [`0056`](./0056-domain-cutover-https.md)
(HTTPS cutover Caddyfile), [`0049`](./0049-smtp-source-of-truth.md) (SMTP from
Settings), [`0082`](./0082-new-user-credentials-email.md) (`SITE_BASE_URL`)
**Amends:** [`0075`](./0075-email-outbox-log.md) (adds `EmailLog.Category.PASSWORD_RESET`)

## Context

After the [`0056`](./0056-domain-cutover-https.md) HTTPS cutover, the committed
`Caddyfile` serves **only** `kasia.cz` / `www.kasia.cz` / `analytics.kasia.cz`
and redirects the bare IP. On a laptop this is unusable: Caddy tries to obtain a
Let's Encrypt cert for `kasia.cz`, fails ACME, and serves nothing on
`http://localhost` — so `make up` (whose banner promises `http://localhost`)
can't actually be opened without a manual port-publish workaround.

Separately, local e-mail did not work. The app builds its SMTP connection from
`Settings`/env (per [`0049`](./0049-smtp-source-of-truth.md)), so `make up`
points at the real `mail.kasia.cz` with a dev sender (`no-reply@kasia.local`).
Sends log `SENT` (the server accepts submission) but never arrive — a fake
`.local` sender fails SPF/DKIM at the recipient, and testing this way would risk
sending real mail through the production relay. A password-reset test "didn't
come" for exactly this reason.

Both needed a dev fix that leaves production **byte-for-byte unchanged**.

## Options considered

- **Env-selected dev config files** — a `Caddyfile.dev` chosen via a `CADDYFILE`
  env var on the compose volume mount, and `EMAIL_BACKEND` made env-overridable
  so dev can use the console backend. Prod defaults (committed `Caddyfile`, SMTP
  backend) apply whenever the vars are unset. One compose file, differences in
  `.env` — matches `infra-as-code.md`.
- **`compose.dev.yaml` override** — a second compose file for dev. Rejected:
  `infra-as-code.md` explicitly forbids it ("No `compose.dev.yaml`. If a dev-only
  knob is needed, drive it from `.env`.").
- **Mailpit / MailHog service** — a real dev inbox with a web UI. Rejected for
  now: it needs a new service *and* a `Settings.smtp_use_tls=False` / port tweak
  to satisfy the 0049 connection builder (which reads TLS/port from the DB), i.e.
  it couples to seed data. The console backend sidesteps the SMTP path entirely
  (non-SMTP backends ignore the host/port/TLS kwargs) and needs zero services.
- **Parametrise the single Caddyfile with env vars** — Caddy can template the
  site address, but the prod-only `www` / IP-redirect / `analytics` blocks can't
  be conditionally omitted, so a dev run would still attempt ACME for them.
  Rejected as fragile.

## Choice

Drive both from `.env`, defaulting to production behaviour:

- **Caddy:** compose mounts `${CADDYFILE:-./Caddyfile}`. A new committed
  `Caddyfile.dev` sets `auto_https off` and serves `:80 → web:8000` over plain
  HTTP. Dev `.env` sets `CADDYFILE=./Caddyfile.dev`; prod leaves it unset.
- **E-mail:** `EMAIL_BACKEND` becomes `os.environ.get("EMAIL_BACKEND",
  "…smtp.EmailBackend")`. **Dev uses the same real `mail.kasia.cz` SMTP as prod**
  (Matej's preference — he wants real mail in his inbox while testing), so the
  send path and the `EmailLog` row behave exactly as in prod. For delivery the
  sender must be a **real `@kasia.cz` address** — a fake `.local`/`.example`
  sender is accepted by the relay but dropped by Gmail (SPF/DKIM). So dev sets
  `DEFAULT_FROM_EMAIL=Kasia vera <aplikace@kasia.cz>` (password-reset sender) and
  `Settings.email_from_address=aplikace@kasia.cz` (app-mail sender, via Nastavení
  → Odesílatel). The env-overridable `EMAIL_BACKEND` remains as an **offline
  alternative** (`…console.EmailBackend` prints mail to the web log and sends
  nothing) for working without a network. Prod leaves everything unset → real
  SMTP with the prod `Settings` sender.
- **Links:** dev `.env` sets `SITE_BASE_URL=http://localhost` (prod:
  `https://kasia.cz`), per [`0082`](./0082-new-user-credentials-email.md).

All three are documented (commented, not set) in `.env.example`.

## Rationale

Env-selected files keep exactly one `compose.yaml` and one prod `Caddyfile`,
honouring `infra-as-code.md`. Because every knob defaults to today's production
value, an unset var on the box means **nothing changes in prod** — the migration
risk is zero. The console backend is the smallest thing that makes dev mail
observable without a real relay or a new service; a browsable Mailpit inbox can
be added later if the dev workflow wants it, but it isn't worth the service +
seed-data coupling today (right-sized per
[`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)).

## Consequences

- New committed file `Caddyfile.dev`; `compose.yaml` proxy mount is now
  `${CADDYFILE:-./Caddyfile}`.
- `kasia/settings/base.py`: `EMAIL_BACKEND` is env-overridable (default SMTP).
- `.env.example` documents `CADDYFILE`, `SITE_BASE_URL`, the dev mail sender, and
  the optional offline `EMAIL_BACKEND` as dev-only, unset-on-prod knobs.
- Local dev: `make up` → **http://localhost** (and self-signed
  **https://localhost**) works; e-mail sends for real via `mail.kasia.cz` from
  `aplikace@kasia.cz` and lands in the inbox, with the `EmailLog` row written as
  in prod. (`caddy-local-ca.crt` can be extracted + trusted to drop the
  self-signed-cert browser warning; it is gitignored.)

## Reproducibility (a fresh clone/session must not hit the old issues)

The dev fixes are **committed**, so `make up` works out of the box without
manual `.env` or DB surgery:

- **`make up` defaults `CADDYFILE=./Caddyfile.dev`** (Makefile `export
  CADDYFILE ?= …`), so localhost serves even when the dev `.env` doesn't set it.
  Override with `make up CADDYFILE=./Caddyfile`. The box deploys via `deploy.yml`
  (never `make`), so prod is unaffected.
- **`SITE_BASE_URL` reader defaults to `http://localhost`** (matches the dev
  Caddy on :80), so e-mail links are clickable on a fresh clone.
- **`seed_walkthrough_data` sets a real `@kasia.cz` sender** (from
  `EMAIL_HOST_USER`, else `aplikace@kasia.cz`) instead of the old
  `no-reply@kasia.local`, so a freshly-seeded dev DB actually delivers mail.
- **Password reset** is routed through `send_and_log`
  (`LoggedPasswordResetForm`) using the **Settings sender**, so it delivers +
  logs regardless of the `DEFAULT_FROM_EMAIL` env value, and shows in the outbox
  as a `PASSWORD_RESET` row.

The only non-committable prerequisite for *real delivery* in dev is the SMTP
password in the local `.env` (`EMAIL_HOST_PASSWORD`) — inherent to sending
through `mail.kasia.cz`; with it absent, dev can still use the offline console
backend. Nothing here changes prod defaults.
- **Prod action (one-time):** on the box `.env`, set
  `SITE_BASE_URL=https://kasia.cz` (for absolute e-mail links, 0082) and leave
  `CADDYFILE` / `EMAIL_BACKEND` unset. Deliverability of external mail still
  depends on `mail.kasia.cz`'s relay + SPF/DKIM — outside this repo.
