# 0103 — Dodací list also goes to the odběratel's kontaktní e-maily (supersedes 0031 + 0052 in part)

**Date:** 2026-09-30
**Decider:** Petr / Matej
**Status:** Active

## Context

Per [`0031`](./0031-emails-internal-only-supersedes-0009.md) (and its successors
[`0052`](./0052-n-list-recipients-supersedes-0031.md) /
[`0081`](./0081-per-recipient-notification-preferences.md)) a *dodací list
(delivery note)* e-mail goes **only** to internal addresses: the dodák-opted-in
`SettingsRecipient` rows (branch-scoped) plus the issuer
(`movement.created_by`). 0031 kept a single `Customer.email` field "for contact
use" and made the send code **never read it**.

Petr now wants the *odběratel (customer)* to receive the dodák directly, and
some customers have more than one address that should get it (e.g. an owner +
a purchasing mailbox). The single `Customer.email` field was never read, so no
real workflow depends on its current values. This also overturns 0052's
restated "internal only / never to customers" intent; 0052 § Forecloses already
anticipated this ("a future decision could … re-introduce a per-customer
recipient list").

## Options considered

1. **Keep 0031 (internal only).** Contradicts the new instruction.
2. **Send to the existing single `Customer.email`.** Minimal, but one address
   per odběratel is not enough, and the field's current values were typed as
   "contact info", never vetted as a send target.
3. **Replace `Customer.email` with a list of kontaktní e-maily and add them to
   every dodák send.** Edited as rows on the odběratel form. **Chosen.**
4. **A separate `CustomerEmail` model / per-address opt-in flags.** More
   flexible (per-address toggles), but a new table + formset for ~6 users and
   a handful of customers. Rejected as over-built (see
   `right-sized-for-small-business.md`).

## Choice

**Option 3.** `Customer.email` (one `EmailField`) is replaced by
`Customer.emails` — a `JSONField` holding a list of address strings (default
empty), labelled **„Kontaktní e-maily"**. A JSON list rather than a Postgres
`ArrayField` so the test suite runs on both SQLite (host `make test` with no
`DATABASE_URL`) and Postgres (CI / prod); addresses are validated by
`CustomerForm`, not the DB. Existing `email` values are **dropped** (no
data copy — the addresses were never a vetted send target; the operator
re-enters the ones that should receive dodáky).

Whenever a dodák e-mail goes out — the manual first send
([`0096`](./0096-manual-first-send-of-dodaky.md)), „Znovu odeslat"
(dodák detail, admin action, E-maily log resend) and the automatic `[OPRAVA]`
reissue ([`0007`](./0007-auto-reissue-corrected-dodaky.md)) — the odběratel's
kontaktní e-maily are **added to the recipients**, after the
`SettingsRecipient` rows and the issuer, with the existing case-insensitive
dedup. All addresses go in one `to=` list (no BCC), as before.

The odběratel form edits the list as rows (one `<input type="email">` per
address, „+ Přidat e-mail", „×" to remove). The form strips whitespace, drops
blank rows, de-duplicates case-insensitively (first spelling wins) and rejects
an invalid address with a Czech error naming it.

## Rationale

- Petr's instruction: the customer should get the dodák without Karolína
  forwarding it.
- A list covers the multi-address customers without a new table; the only
  send path (`send_dodaci_list_email`) already unions + dedups recipients, so
  adding one more source is a few lines.
- Dropping the old values avoids silently turning never-vetted "contact"
  addresses into live send targets on deploy.
- One `to=` list keeps parity with today's send (customers see the internal
  recipients; acceptable — they are Kasia staff addresses on a Kasia document).

## Date & by-whom

2026-09-30 — Petr / Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Customers receive their dodák (PDF) directly on every send / resend / oprava.
- Multiple addresses per odběratel.

**Supersedes in part:** 0031 (internal-only recipients; `Customer.email`
never read) and 0052 (its "internal only / never to customers" intent).

**Changes:**

- `Customer.email` → `Customer.emails` (migration adds `emails`, removes
  `email`; no data copy). Any existing single contact e-mail is lost.
- `CustomerForm` reads the list from repeated `emails` POST values;
  `customer_form.html` renders the rows; `customer_index.html` shows the
  addresses joined by „, " (and includes them in the live-filter text).
- `send_dodaci_list_email` appends `dodaci_list.odberatel.emails` (the same odběratel the PDF renders).
- `.claude/rules/design-system.md` § Nastavení recipients mentions the
  customer e-mails as an additional dodák audience.

**No change to:**

- `SettingsRecipient` routing (0081) and the issuer copy.
- Internal odběratelé (Míchárna) — they never get a dodák (0039), so never a
  send.
- Other e-mail categories (dochází souhrn, Podpora, Oznámení, výdej request).

**Forecloses (without follow-on decision):**

- Per-address opt-in flags or a BCC send to customers.
- Sending anything other than dodáky to customer addresses.
