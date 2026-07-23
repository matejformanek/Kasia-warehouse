# 0098 — Podpora: resolve note + notify the report's creator

**Date:** 2026-07-23
**Decider:** Matej (standing in for Petr) — Petr requested it directly
**Status:** Active

## Context

Extends the Podpora chain ([`0046`](./0046-support-page.md) →
[`0079`](./0079-feedback-admin-notification.md) →
[`0081`](./0081-per-flag-recipient-opt-ins.md)). Today marking a hlášení
„Vyřešeno" is a silent toggle — the reporter only learns by revisiting the
shared Podpora page. There is no way to add a closing note, and no notification.

## Options considered

1. **Notify on every state change (resolve *and* reopen).** Rejected — a reopen
   is an internal correction; e-mailing „your issue was reopened" is noise.
2. **A required resolution note.** Rejected — most fixes need no comment; forcing
   one adds friction to the common case.
3. **Optional note, notify creator on resolve only.** The vlastník may type a
   free-text note when resolving; on resolve the report's `created_by` is
   e-mailed („your issue was resolved" + the note when present). Reopen stays
   silent and keeps the note. **Chosen.**

## Choice

- Add `Feedback.resolution_note` (`TextField`, blank) — a free-text closing note.
- Resolving a hlášení (open → resolved) stores the note (from the resolve form)
  and e-mails the report's `created_by` via `send_and_log`, logged as a new
  `EmailLog.Category.FEEDBACK_RESOLVED`. The mail recaps the page/description,
  includes the note when present, and links back to Podpora.
- Reopening (resolved → open) clears `resolved_at`/`resolved_by`, **keeps**
  `resolution_note`, and sends **no** e-mail.

## Rationale

Resolve-only notification closes the loop for the reporter without spamming on
internal reopens. An optional note keeps the fast path fast while allowing a
short "here's what changed" when useful. Routing through `send_and_log` keeps the
send logged + failure-swallowing, so a mail outage can't block the toggle
(mirrors the 0079 intake notification).

## Consequences

- **New `EmailLog.Category.FEEDBACK_RESOLVED`**, distinct from the 0079
  intake `FEEDBACK` category, so the outbox separates "new report" from
  "report resolved". Rides migration `0031`.
- **FEEDBACK_RESOLVED mails `Feedback.created_by`** — not a `SettingsRecipient`
  and not `FEEDBACK_NOTIFY_EMAIL`; the per-flag Nastavení table
  ([`0081`](./0081-per-flag-recipient-opt-ins.md)) does not gate it.
- The resolve action grows an inline optional-note field on the Podpora table;
  it stays a plain submit (resolve is reversible — no confirm dialog).
- Plain-text only, right-sized.
