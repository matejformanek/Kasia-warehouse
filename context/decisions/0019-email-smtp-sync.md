# 0019 — E-mail backend: Django built-in SMTP, synchronous send

> **Superseded in part by [0075](./0075-email-outbox-log.md)** — the
> `dodaci_list_email_log` model defined here is folded into a unified `EmailLog`
> (all business e-mails, rendered subject+body stored, resend from a Správa page).
> The synchronous-SMTP + fail-silent + resend posture is unchanged.

## Context

R6 (outbound SMTP with attachment + templated body) and R11 (failed
e-mail visibility) in [`../tech-options.md`](../tech-options.md).
The volume is tens of dodáky per day at most. Per
[`0007`](./0007-auto-reissue-corrected-dodaky.md), every výdej save
sends one e-mail; every correction triggers an `[OPRAVA]` re-send.

A background-job system (Celery + Redis, RQ, Dramatiq) would
decouple send from the request, but the cost is real: another
process to operate, another dependency tier in the container stack,
another failure mode (Redis down) to design around. For ~6 users
and ~tens of sends/day, **synchronous send inside the výdej save
with try/except** is sufficient — failures surface in
[`../screens/02-dashboard-vlastnika.md`](../screens/02-dashboard-vlastnika.md)
*K vyřešení* and the resend control on
[`../screens/09-detail-dodaku.md`](../screens/09-detail-dodaku.md).

## Options considered

- **Django built-in SMTP backend, synchronous send wrapped in
  try/except.** Send happens in-request after the DB transaction
  commits (so a send failure doesn't roll back the výdej, per the
  R8 atomicity rule — výdej + PDF + číslo atomic; e-mail outside
  the transaction). Failures write a row to `dodaci_list_email_log`
  with the error and surface on screens 02 + 09.
- **Celery + Redis.** Async send. Decouples request from SMTP
  latency. Adds Redis + a worker container + a beat scheduler.
  Three extra moving parts for a 6-user system.
- **Dramatiq / RQ.** Same shape as Celery, lighter.
- **Postmark/SES transactional API.** Reliable but binds the system
  to a SaaS; for a Czech B2B distributor that's a procurement step
  the owner doesn't need. SMTP via any provider Petr already has
  (Seznam, Office 365, …) is enough.

## Choice

**Django's built-in SMTP backend, synchronous send.** Send happens
*after* the database transaction commits — the výdej, the dodací
list row, the PDF blob, and the číslo are durable before the SMTP
call. The send is wrapped in try/except; success writes a row to
`dodaci_list_email_log` with `sent_at`; failure writes a row with
`error`, and the dodák appears on screen 02 *K vyřešení* with a
resend button on screen 09.

SMTP credentials read from env (`EMAIL_HOST`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_PORT`, `EMAIL_USE_TLS`). The first
operating SMTP target is Petr's existing mail provider.

## Rationale

- Per
  [`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md):
  reject the first enterprise-shaped suggestion. The job queue is
  exactly that here.
- R11 is fully met by the email-log row + the dashboard tile + the
  resend control. The operator's mental model — "if the green check
  is missing, click resend" — is one click.
- Synchronous SMTP latency at typical provider response times
  (~100–500 ms) is invisible inside the výdej save flow.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The výdej save implementation (next pass) is a straight
  `transaction.atomic()` block followed by a try/except SMTP call.
- No Celery / Redis / worker container in
  [`0023`](./0023-runtime-orchestration-compose.md).

**Forecloses (without follow-on decision):**

- A worker-based send architecture. If send latency or volume
  ever becomes a problem, a future decision can introduce a queue.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R6 (SMTP + attachment + templated body), R11 (failed-email
  visibility).

**Makes implementable (0001–0013):**

- [`0007`](./0007-auto-reissue-corrected-dodaky.md) auto-reissue —
  the corrected PDF is sent on the same code path with subject
  prefixed `[OPRAVA]`.
- [`0009`](./0009-dodaci-list-email-recipients.md) recipient model —
  the recipient list is composed from Petr + Karolína (default) +
  per-customer remembered + ad-hoc additions at issue time.
