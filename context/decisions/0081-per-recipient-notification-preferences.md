# 0081 — Per-recipient notification preferences + branch scope

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, after using the app)
**Status:** Accepted
**Amends:** [`0052`](./0052-n-list-recipients-supersedes-0031.md) (recipient
N-list), [`0079`](./0079-podpora-enhancements.md) (Podpora e-mail routing)

## Context

The Nastavení „Příjemci dodacího listu" list (per
[`0052`](./0052-n-list-recipients-supersedes-0031.md)) could not express *who
gets which* e-mail. Three flows were wired too bluntly:

- **Dodací list** → *every* active `SettingsRecipient` (no opt-out, no branch
  scope).
- **Souhrn „dochází zboží"** → active + `is_low_stock_recipient` (the one
  working opt-in).
- **Podpora — nové hlášení** (per [`0079`](./0079-podpora-enhancements.md)) → a
  *hardcoded* `settings.FEEDBACK_NOTIFY_EMAIL`, not in the table at all.

Matej wants each recipient to opt in/out of each e-mail type independently
(e.g. Matej himself = Podpora only), plus a per-recipient **branch filter** for
dodáky (some stakeholders only care about one branch's dodáky).

The [`0052`](./0052-n-list-recipients-supersedes-0031.md) guard
(`_assert_recipients_set`) refused a výdej when no active recipient existed. With
per-flag opt-out a dodák could now legitimately reach *nobody*; rather than keep
a guard that would fire on a valid config, we drop it and guarantee delivery a
different way (see Choice).

## Options considered

- **Keep one flat active-list, add per-flag columns** — decouple the three
  flows onto three booleans on `SettingsRecipient` (`is_active` becomes the
  master switch). Cheap, no new model, matches the existing formset UI.
- **Separate recipient tables per flow** — one list per e-mail type. More
  tables, more UI, duplicate addresses to maintain. Over-built for ~6 users.
- **Free-text routing rules** — a mini rules engine. Absurd at this scale.

## Choice

Decouple the three flows onto per-flag booleans on `SettingsRecipient`, with a
nullable branch FK for the dodák scope:

- `is_active` is the **master switch** — an inactive row receives nothing.
- `is_dodaci_recipient` (default `True`) — receives dodáky.
- `is_feedback_recipient` (default `False`) — receives Podpora reports.
- `is_low_stock_recipient` (unchanged) — receives the daily „dochází" summary.
- `dodaci_branch` (nullable FK to `Branch`, `SET_NULL`) — when set, that row
  only receives dodáky from that branch; `NULL` = all branches.

Effective sets:

- **Dodák** = `is_active AND is_dodaci_recipient AND (dodaci_branch IS NULL OR
  dodaci_branch == dodák.branch)`.
- **Souhrn** = `is_active AND is_low_stock_recipient` (unchanged).
- **Podpora** = `is_active AND is_feedback_recipient`, falling back to
  `settings.FEEDBACK_NOTIFY_EMAIL` when no feedback recipient is configured (so
  reports never silently vanish).

**Remove the `_assert_recipients_set` guard.** In its place, every dodák is
**always also mailed to its issuer** (`movement.created_by.email`, unioned +
deduped case-insensitively into the `to=` list). Petr stays a Všechny/dodák
recipient, so a dodák can never reach nobody even with an empty configured list.

## Rationale

Three booleans + one nullable FK is the smallest change that satisfies the ask,
reuses the existing formset UI, and backfills existing rows to today's behaviour
via field defaults (no data migration). The guard removal is safe because the
issuer-copy guarantees at least one recipient on every dodák — a stronger
guarantee than the guard gave (the guard only checked the *configured* list, not
that the mail would actually reach a human who cares about that výdej). Matej
explicitly declined a výdej-time guard in favour of the always-copy-issuer rule.

## Consequences

- Migration `0022` adds three fields on `SettingsRecipient` (+ the credentials
  `EmailLog.category` from [`0082`](./0082-new-user-credentials-email.md)). No
  `RunPython` — defaults backfill.
- `_active_dodak_recipients(branch)` gains a `branch` param; new
  `_active_feedback_recipients()`; `send_feedback_notification` routes through
  the table with the `FEEDBACK_NOTIFY_EMAIL` fallback.
- `send_dodaci_list_email` unions the issuer; no external signature change (both
  branch + issuer derive from the `dodaci_list` arg).
- `_assert_recipients_set` is deleted (import + two call sites in
  `services/movement.py`, plus the service package re-export). Two guard tests
  are rewritten / removed accordingly.
- Nastavení recipient table grows three columns (Dodací listy / Podpora
  checkboxes + „Pobočka" dropdown). Documented in
  [`design-system.md`](../../.claude/rules/design-system.md).
