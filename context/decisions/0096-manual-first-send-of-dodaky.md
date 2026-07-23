# 0096 — Manual first-send of dodáky ("Čeká na odeslání")

> **Amends [`0007`](./0007-auto-reissue-corrected-dodaky.md) and the
> send-on-issue part of [`0019`](./0019-email-smtp-sync.md)** — the *initial*
> dodák e-mail is no longer sent automatically at výdej; it waits for an operator
> click. Corrections *after* the dodák has been sent keep 0007's auto-reissue +
> `[OPRAVA]` behaviour unchanged.

## Context

Under [`0007`](./0007-auto-reissue-corrected-dodaky.md) +
[`0019`](./0019-email-smtp-sync.md), saving a customer **výdej** auto-created
its **dodací list** and immediately e-mailed it ("vystavení"); every later
movement edit bumped the dodák version and auto-re-e-mailed an `[OPRAVA]`.

In practice a list is edited several times by several people before it is really
finalized, so recipients get a burst of premature/half-baked e-mails — the exact
opposite of what the auto-send was meant to fix. (0007 named the failure mode it
was avoiding as "half the dodáky get forgotten and never sent"; that risk is now
covered differently — see Consequences.)

## Options considered

- **Keep auto-send (status quo).** Zero clicks, but the premature-burst problem
  stands. Rejected.
- **Interstitial "confirm send?" screen after saving výdej.** One extra screen in
  the hot path; still forces a decision before the operator has reviewed the PDF.
  Rejected as heavier than needed.
- **Persisted `send_state` gate + manual "Odeslat" on the dodák detail
  (chosen).** The výdej save lands the operator on the dodák detail (already the
  case) with a "Čeká na odeslání" banner + a primary Odeslat button. No new
  screen; the operator reviews/edits freely with no e-mails, and sends when sure.

## Choice

Add a persisted `DodaciList.send_state ∈ {WAITING, SENT}` (default `WAITING`).
Saving a výdej still deducts stock and still creates the dodák, but **sends
nothing** — the dodák starts `WAITING`. A new thin service `send_first_dodaci`
(called by a new `POST dodaky/<cislo>/odeslat/` view) performs the first send and
flips `WAITING → SENT` on a successful send. After `SENT`, behaviour reverts to
0007: a movement edit bumps the version and auto-re-e-mails an `[OPRAVA]`. While
`WAITING`, an edit bumps no version and sends no e-mail (just re-generates the
PDF). A výdej edit now **redirects back to its dodák detail** (the operator
reviews the regenerated dodák there). A prominent **"Čeká na odeslání"** section
appears on the dodák index, the owner Přehled, and the obsluha branch dashboard
so a pending send is never forgotten.

## Rationale

- **Stock is still committed at save** (unchanged from today). The user confirmed
  this: `WAITING` gates **only** the e-mail. Because stock is already deducted,
  the "amount fell below at send time → not legit → forced inventura" situation
  cannot occur, so no send-time re-check / inventura gate is needed — that keeps
  the send path a thin, single-purpose service.
- **Reuses existing plumbing** — the e-mail send (`send_dodaci_list_email`
  already accepts `sent_by`), recipient resolution ([`0081`](./0081-per-recipient-notification-preferences.md)),
  branch scoping ([`0040`](./0040-operator-crud-tiering.md)), the outbox log
  ([`0075`](./0075-email-outbox-log.md), no new categories/statuses), and the
  `.card` / `table.lines` `tr.row-link` + `kasiaConfirm` UI hooks
  ([`0061`](./0061-display-1dp-comma.md)). The "Čeká na odeslání" list is a
  whole-row-clickable table with an out-of-form Odeslat button (the 0059
  PLANNED-cancel pattern — a `.js-confirm` form can't nest in `tr.row-link`).
- **The state mutation stays in the service layer**, consistent with
  `current_version` (only ever mutated in services).

## Date & by-whom

2026-07-23 — Matej (on behalf of Petr).

## Consequences

- **New field + migration.** `DodaciList.send_state` (migration
  `0030_dodacilist_send_state`). Pre-existing rows are backfilled to `SENT` (they
  were already auto-issued under the old flow); prod has 0 dodáky
  ([`0087`](./0087-production-data-wipe-for-go-live.md) wipe) so it is a no-op there. New rows
  default `WAITING`.
- **`is_edited` re-reads.** A `WAITING` draft stays v1 through edits, so
  `edited_dodaky` / `is_edited` now mean "re-issued after being sent", not "edited
  at all". The owner Přehled "Editovaný dodák" bucket and the index "Pouze
  editované" filter follow suit.
- **The "forgotten send" failure mode 0007 worried about** is now covered by the
  three prominent "Čeká na odeslání" lists (index + owner Přehled + branch
  dashboard) rather than by auto-sending.
- **Unaffected:** internal výdeje (`is_internal_vydej`) still create no dodák;
  [`0059`](./0059-merge-objednavka-into-prijem.md) planned-příjem flow; the
  `[OPRAVA]` correction path for already-sent dodáky (0007); 0075 categories;
  0081 recipients; 0040 scoping; 0061 dialogs. Rebased cleanly on
  [`0095`](./0095-hotovy-vyrobek-finished-product-type.md) (a customer výdej with
  finished-product lines still creates a dodák → the waiting/send flow applies
  unchanged).
