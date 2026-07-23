# 0097 — Oznámení: vlastník-only broadcast e-mail on the E-maily page

**Date:** 2026-07-23
**Decider:** Matej (standing in for Petr) — Petr requested it directly
**Status:** Active

## Context

The owner has no in-app way to tell the ~6–20 users "we shipped the thing you
asked for" (or any other announcement). Today every app e-mail is event-driven
(dodák on výdej, low-stock souhrn, Podpora intake, new-user credentials, SMTP
test) and routes through the single logged seam `send_and_log`
([`0075`](./0075-unified-email-outbox.md)). A free-text broadcast is the missing
piece.

The audience is warehouse **users** (the `accounts` User table), not the dodák
`SettingsRecipient` list — an announcement is aimed at whoever logs in, chosen
at send time, not a standing per-flag opt-in.

## Options considered

1. **One e-mail per recipient (a loop of `send_and_log`).** Rejected — N outbox
   rows per announcement clutters the log, and N SMTP sends is needless for ~20
   users.
2. **A new nav entry / dedicated „Oznámení" screen.** Rejected — the E-maily page
   is already the vlastník-only e-mail surface; a composer belongs there, not
   behind a new sidebar item.
3. **Single BCC send, composer on the E-maily page.** One `EmailMessage` with the
   whole audience in **BCC** (recipients never see each other), `to` = the app's
   own from-address, logged as one row. **Chosen.**

## Choice

Add a vlastník-only **„Oznámení" composer on the existing E-maily page**
(`email_log_index`) — subject + body + audience selector with three modes:

- **all** — every active user (default),
- **branch** — every active user (audience is all active users; branch narrows
  intent, resolved to that branch's users),
- **selected** — a manually-checked subset.

It sends **one BCC e-mail** (audience in `bcc`, `to` = the app from-address) via
`send_and_log`, logged as a new `EmailLog.Category.ANNOUNCEMENT`. To fit a
full-audience BCC join, `EmailLog.recipients` widens from `CharField(512)` to
`TextField`, and when `bcc` is passed the stored `recipients` is the **BCC join**
(the real audience), not the `to` header. Resend of an ANNOUNCEMENT row
re-routes through the same BCC path (stored recipients → `bcc`), so it never
leaks the audience into `to`.

## Rationale

Single BCC is the smallest thing that respects recipient privacy and keeps the
outbox to one row per announcement. Placing the composer on E-maily reuses the
existing vlastník gate and puts the send next to its own log. Targeting app
users (not `SettingsRecipient`) matches what an announcement is — a message to
people who log in, picked when you send.

## Consequences

- **`EmailLog.recipients` is now a `TextField`.** Every consumer already treats
  it as an opaque comma-joined string (detail/resend split on `,`, `__str__`,
  admin search, tests) — widening breaks nothing. Migration `0031`.
- **`send_and_log` gains a keyword-only `bcc`.** When set, the logged
  `recipients` column is the bcc join; the `to` header is the app from-address.
- **Resend branches on category.** An ANNOUNCEMENT row re-sends via BCC; every
  other non-dodák row keeps re-sending its stored recipients into `to`.
- **Oznámení is not `SettingsRecipient`-routed** — the per-flag Nastavení table
  ([`0081`](./0081-per-flag-recipient-opt-ins.md)) stays authoritative only for
  dodáky / Podpora-intake / dochází-souhrn.
- Plain-text only (no HTML/multipart), right-sized for ~6–20 users.
- Announcements are one-shot: no scheduling, no drafts, no templates.
