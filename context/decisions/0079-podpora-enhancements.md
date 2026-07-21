# 0079 — Podpora enhancements (page dropdown + e-mail on new report)

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, sklad UX round after using the app)
**Status:** Accepted
**Amends:** [`0046`](./0046-support-page.md)

## Context

Two follow-ups to the Podpora page ([`0046`](./0046-support-page.md))
surfaced from real use. Both **reverse deferred/deliberate choices in
0046**, so per
[`decision-log-discipline.md`](../../.claude/rules/decision-log-discipline.md)
they are recorded as a new append-only entry that references 0046
(which gets a one-line `> **Amended by 0079**` banner — the only
permitted edit to a landed decision).

1. **„Which page" field is a free-text slash path.** 0046 §Choice and
   `context/screens/16-podpora.md` (lines 39-40, 67-68) specify
   `page_url` as a **free-form** `CharField` hint like `/katalog/`.
   Auto-fill of the page was listed as a *deferred* future item (0046
   §Future considerations, "Per-page 'Report this page' button
   auto-filling `page_url`"). In practice non-technical operators don't
   understand slash paths — they don't know their screen is `/katalog/`.
   A dropdown of plain Czech screen names is what they can actually use.
2. **No e-mail on a new report.** 0046 explicitly **deferred** e-mail
   notification ("E-mail notification to Matej when new feedback is
   submitted — trivial to add later, not in this pass"). Reports can sit
   unseen; the operator has no fast path when something is urgent.

## Options considered

- **Page field:** free-text (status quo) vs **dropdown of screen
  names** vs a per-page auto-filled `?page=` deep-link. **Chosen: the
  dropdown.** It's the friendly, no-typing option and needs no model
  change. The `?page=` deep-link (0046's deferred idea) stays optional
  polish, not required.
- **E-mail:** none (status quo) vs a **daily digest** (0046 floated the
  low-stock-summary shape) vs an **immediate per-report notification**.
  **Chosen: immediate**, to one fixed admin address. At ~6 users the
  volume is tiny; a digest would only add latency to noticing an urgent
  report.

## Choice

### 1 — Page field becomes a dropdown of Czech screen names

`inventory/forms/feedback.py`: `page_url` is redeclared as an explicit
`forms.ChoiceField(required=False, widget=forms.Select, …)` with its
label on the field. **Choices use `value == label`** so the friendly
Czech string is what gets stored in the existing
`Feedback.page_url` `CharField(max_length=255, blank=True)` — the model
keeps **no** `choices=`, so old free-text rows stay valid and **no
migration** is needed. A leading blank choice
(`("", "— vyberte stránku (volitelné) —")`) keeps an unselected dropdown
posting `""`. Label: „Které stránky se hlášení týká? (volitelné)".

Screen names offered: Přehled, Katalog, Inventura, Příjem, Výdej,
Míchání, Historie, Dodací listy, Detail produktu, Dodavatelé,
Odběratelé, Nastavení, Uživatelé, Podpora, + „Jiné / nevím".

`support.html` renders the stored friendly name as **plain text** in the
history table (the old `<code>` slash-path wrapper is dropped).

**Optional tie-in (not required):** the per-page help panel (0078) may
carry a „Nahlásit problém na této stránce" link to
`…/podpora/?page=<label>`; the view pre-fills `initial={"page_url": …}`
on GET. Because value == label, `?page=` must carry the exact
URL-encoded Czech label; used only as unbound `initial` it isn't
validated, so a stale value renders harmlessly. Kept only if cheap.

### 2 — E-mail notification on every new report

- `settings.FEEDBACK_NOTIFY_EMAIL` (default
  `"matej.formanek@kasia.cz"`, env-overridable) — a fixed admin
  address, **not** a `SettingsRecipient` (this is the app operator, not
  the dodák-list recipients).
- `EmailLog.Category.FEEDBACK = "feedback", "hlášení z podpory"` added
  (migration `0021`, a single `AlterField` on `category`'s choices — no
  DB DDL). The E-maily outbox page + admin read categories generically,
  so the new member auto-appears and its rows resend from stored
  subject/body (0075 seam).
- `inventory/services/email.py::send_feedback_notification(feedback)`
  calls the single `send_and_log(...)` interception point (0075) with
  `category=FEEDBACK`, `recipients=[settings.FEEDBACK_NOTIFY_EMAIL]`,
  `from_email` built by the same
  `f"{name} <{addr}>" if name and addr else (addr or None)` snippet the
  dodák / low-stock paths use (passing `None` lets Django apply
  `DEFAULT_FROM_EMAIL`). `send_and_log` logs FAILED and never re-raises,
  so a mail outage can't block the save.
- `support_view` POST schedules the send via
  `transaction.on_commit(lambda: send_feedback_notification(f))` after
  `f.save()` — keeps SMTP latency off the request, mirrors the dodák /
  low-stock paths.
- A **direct-contact note** renders under the form: „Pokud na vaše
  hlášení nikdo neodpoví delší dobu nebo jde o vážný problém, napište
  přímo správci:" + a `mailto:matej.formanek@kasia.cz` link.

## Rationale

The dropdown is the change that actually helps the operator — they pick
their screen by its Czech name instead of guessing a slash path. Keeping
`value == label` means the fix is form-only: the model, the stored data,
and every existing row are untouched, and there is no migration for the
field.

Immediate e-mail (vs a digest) matches the tiny volume and the real need
— noticing an urgent report fast. Routing it through the existing
`send_and_log` seam means it's logged, resendable, and outage-safe for
free, with no new send machinery. The direct-contact note is the
belt-and-suspenders path when even that goes unanswered.

## Consequences

**Now:**
- `forms/feedback.py`: `page_url` → `ChoiceField`; dead
  `Meta.widgets`/`Meta.labels` entries removed.
- `support.html`: `<code>` wrappers dropped; direct-contact note added.
- `settings.base`: `FEEDBACK_NOTIFY_EMAIL`.
- `EmailLog.Category.FEEDBACK` + migration `0021`.
- `services/email.py`: `send_feedback_notification` helper.
- `support_view`: `on_commit` send.
- Tests: fix `test_support_post_creates_feedback_and_redirects` (post a
  valid label), keep `test_support_post_with_optional_page_url` (empty
  choice) green, add service + view e-mail coverage.
- `context/screens/16-podpora.md` updated (dropdown + notification).

**Amends 0046:**
- 0046's free-text `page_url` choice and its deferred "auto-fill" /
  "e-mail notification" future items are now superseded in part by this
  entry. 0046 carries a `> **Amended by 0079**` banner.

**Not doing:**
- No daily digest, no reply field, no categories/labels (still out of
  scope, as in 0046).
- The `?page=` deep-link is optional, not load-bearing.

## Cross-references

- [`0046-support-page.md`](./0046-support-page.md) — the page this amends (free-text `page_url`, deferred e-mail)
- [`0075-email-outbox-log.md`](./0075-email-outbox-log.md) — the `send_and_log` seam the notification routes through
- [`0078-per-page-contextual-help.md`](./0078-per-page-contextual-help.md) — the per-page help panel that may host the optional `?page=` link
- [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md) — why immediate-not-digest, fixed-address-not-list
