# 0075 — Unified e-mail outbox log (`EmailLog`) + admins-only „E-maily" page

**Date:** 2026-07-07
**Decider:** Matej (relaying Petr's ask)
**Status:** Active
**Supersedes in part:** [`0019`](./0019-email-smtp-sync.md) — the dodák-scoped
`dodaci_list_email_log` model (`DodaciListEmailLog`) is folded into a unified
`EmailLog`; its rows are migrated. (0007 defines the re-issue *trigger*, not the
log model, so it is untouched.)
**Builds on:** [`0049`](./0049-smtp-source-of-truth.md) (the app builds
its own SMTP connection from `Settings`, bypassing `EMAIL_BACKEND`),
[`0052`](./0052-n-list-recipients-supersedes-0031.md) (N-list recipients),
[`0074`](./0074-event-driven-low-stock-alert.md) (the event-driven low-stock
alert — one of the newly-logged send paths).

## Context

The app sends several e-mails — dodák (vystavení / oprava / ruční resend), the
event-driven low-stock alert (0074), and the SMTP-test — but there was **no single
place to see what was sent, to whom, and why, or to resend a failed one**:

- Only **dodák** sends were persisted, in a dodák-scoped `DodaciListEmailLog`
  (shown on the dodák detail page). It stored recipients/version/reason/status/
  error — **not** the rendered subject/body.
- The **low-stock alert** and the **SMTP-test** were fire-and-forget — no record.
- Password-reset is Django-owned (one-time token; resend is moot) — out of scope.

Petr's want: an **admins-only page under Správa** listing every e-mail the app
sent, its status, recipients, subject/body and reason, with a **resend** action.

## Options considered

1. **Per-type log tables + per-type screens.** Keep `DodaciListEmailLog`, add one
   for alerts, one for tests. Rejected — three near-identical tables and screens
   for ~6 users; the outbox wants one chronological list.
2. **A logging e-mail *backend*.** Rejected — per 0049 the app builds its own SMTP
   connection and calls `EmailMessage.send()` directly, bypassing
   `settings.EMAIL_BACKEND`, so a logging backend would never see these sends.
3. **One unified `EmailLog`, written at an explicit `send_and_log` seam, one
   Správa page.** **Chosen.**

## Choice

### (1) One unified `EmailLog` model, absorbing `DodaciListEmailLog`

`inventory/models/email_log.py`. Fields: `created_at`, `category` (TextChoices:
`dodaci_vystaveni` / `dodaci_oprava` / `dodaci_resend` / `low_stock_alert` /
`smtp_test` — the "what"), `trigger_reason` (free-text "why"), `recipients`,
`from_email`, **`subject` + `body`** (the rendered content), `status`
(sent/failed), `error_message`, `dodaci_list` FK (null, `SET_NULL`,
`related_name="email_logs"` — the same name the dodák detail already reads),
`dodaci_version`, `sent_by` FK (null — the operator who triggered a manual send;
null for automatic `on_commit` sends). Migration `0019_email_log` creates it,
copies every `DodaciListEmailLog` row (category derived from `trigger_reason`;
`version`→`dodaci_version`; subject/body left empty), then deletes the old model.

### (2) One interception point — `send_and_log`

A new `send_and_log(...)` helper in `inventory/services/email.py` does *send →
write an `EmailLog` row* (SENT, or FAILED + error) in a try/except that never
re-raises (the same posture the dodák send already had, per 0019). Every app send
path routes through it: `send_dodaci_list_email`, `_send_low_stock_alert_email`
(0074), and `settings_test_smtp`. Explicit-helper logging is the right seam
because the app bypasses `EMAIL_BACKEND` (0049).

### (3) Store rendered subject+body — for faithful resend

To resend faithfully, the log stores the **rendered subject + body**. The
low-stock alert's content (the products that just crossed) is ephemeral and
cannot be recomputed later, so it must be stored. Dodák rows instead re-derive
from the live `DodaciList` on resend (existing behaviour) — so historical/migrated
dodák rows (empty subject/body) resend correctly. Thus resend branches on type: a
dodák row re-runs `send_dodaci_list_email` (re-renders PDF + subject/body); a
non-dodák row re-sends the stored subject/body/recipients. Both write a fresh
`EmailLog` row (`trigger_reason="ruční opětovné odeslání"`).

### (4) Vlastník-gated Správa page

`e-maily/` (`email_log_index`) + `e-maily/<pk>/` (`email_log_detail`) +
`e-maily/<pk>/odeslat-znovu/` (`email_log_resend`), all gated with
`require_vlastnik` (the existing Správa gate). Index: status tabs + category
filter, 50/page pagination, the 0063 diacritic-insensitive client text search
over recipients+subject. Detail carries the resend button (`.js-confirm`, no
native dialog per 0061).

### (5) Retention: keep everything

No pruning, no retention window. At ~tens of sends/day and ~6 users the table
stays small for years; a prune job is unwarranted complexity
(`right-sized-for-small-business.md`).

## Rationale

- **One chronological outbox** answers Petr's "what did we send" directly; one
  model + one page instead of three.
- **`send_and_log` is the only seam** that catches every path given 0049's
  bypass of `EMAIL_BACKEND`.
- **Stored subject+body** is the minimum needed to resend an ephemeral alert;
  dodák rows lean on the existing live-render path, so migrated rows still work.
- **Reuses the dodák's proven posture** — fail-silent send, resend control — now
  generalised across all app e-mails.

## Date & by-whom

2026-07-07 — Matej (relaying Petr's ask).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory/services/email.py` gains `send_and_log`; the three writers delegate
  to it. `EmailLog` feeds the outbox page and the dodák detail's "Verze a
  odeslání" table (via `email_logs`).

**Removes:**

- `DodaciListEmailLog` (model, admin, every import) — replaced by `EmailLog`.

**Forecloses (without follow-on decision):**

- Any retention/pruning job. To open, bring a concrete table-size concern.
- Logging password-reset e-mails (Django-owned one-time tokens).

**Cross-cutting:**

- `right-sized-for-small-business.md` — no new rule file; a single outbox page at
  ~6 users does not warrant one. This decision + the model docstring are the
  authoritative record.
