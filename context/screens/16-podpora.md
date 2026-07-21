# Podpora / Support

Single in-app help page combining static reference docs with a
DB-backed feedback log. Per
[`decisions/0046-support-page.md`](../decisions/0046-support-page.md).

## Purpose

Operators new to the tool keep asking "kam mám zaznamenat …?" and
when something doesn't work the report vanishes into chat/SMS to
Matej. One in-app page solves both: a per-screen reference + common
workflows + tips on top, a feedback form + history below. Lets the
~6 users self-serve during the 14-day shadow run per
[`0034`](../decisions/0034-shadow-run-before-go-live.md) without
escalating every question to Matej, and gives Matej a curated
backlog of bugs/wishes with attribution.

## Who uses it

Every logged-in user (Petr, Karolína, 2× obsluha TYN, 2× obsluha
SEZ). Desktop primary, responsive on tablet. Frequency varies:
obsluha read the návod section on demand (rarely after the first
week); vlastník reviews + resolves feedback weekly during shadow
run, less often after that.

## What it shows

Three sections in one template:

1. **Návod k použití** — three `<details>` accordions:
   - "Co kde najdu" — per-screen reference, one line per nav entry.
   - "Postupy" — six numbered workflows: příjem, výdej, plánovaný
     převod, plánované míchání, ruční úprava stavu, oprava staršího
     pohybu.
   - "Tipy a triky" — ~11 gotchas mined from the screen docs
     (default Říčany odběratel, šarže optional, [OPRAVA] re-send,
     rezervace zmenšují „Efektivní", apod.).
2. **Nahlásit chybu nebo požadavek** — Django form with two
   inputs: `page_url` (optional **dropdown of Czech screen names**,
   e.g. „Katalog", „Výdej", … + „Jiné / nevím"; per
   [`0079`](../decisions/0079-podpora-enhancements.md), replaces the old
   free-text slash-path hint) and `description` (required TextField).
   On submit an **e-mail notification** goes to the fixed admin address
   (`settings.FEEDBACK_NOTIFY_EMAIL`) via the 0075 `send_and_log` seam,
   scheduled in `transaction.on_commit`. A direct-contact note under the
   form points users at `matej.formanek@kasia.cz` for
   unanswered/urgent reports.
3. **Historie hlášení** — table of last 50 `Feedback` rows,
   newest first. Columns: Datum, Kdo, Stránka, Popis, Stav, plus
   Akce (vlastník-only).

## What you can do here

- **Read docs** — open / close accordions.
- **Submit a hlášení** — POST form. Auto-attributed to the current
  user; `resolved_at` and `resolved_by` left null on creation.
- **Mark resolved / re-open** (vlastník only) — POST to
  `/podpora/<pk>/vyresit/`. Flips `resolved_at` between `now` and
  `None`. Obsluha gets a Czech error message + redirect; no 403.

## What it links to / from

- **Reached from:** main nav "Podpora" link (visible to all
  logged-in users, between "Historie" and the vlastník-only
  "Pobočky").
- **Goes to:** posts return back to `/podpora/`. The workflow text
  in accordion B references screen 11 (úprava pohybu) by name; no
  explicit hyperlink.

## Business rules & validation

- **Description is required** — Django's `TextField` rejects
  empty input via form validation, no save attempted.
- **`page_url` is optional** — a `ChoiceField` (`required=False`)
  whose choices are `value == label` Czech screen names, stored into the
  unchanged `CharField(max_length=255, blank=True)` (no model `choices=`,
  no migration; old free-text rows stay valid). Per
  [`0079`](../decisions/0079-podpora-enhancements.md).
- **Author is auto-filled** from `request.user` on submit; the form
  never exposes the field.
- **Only vlastník can toggle resolved** — `request.user.is_vlastnik`
  check; obsluha gets a Czech error message + redirect to
  `/podpora/`, not a 403 (friendlier UX, matches the
  `supplier_archive` pattern in `inventory/views.py`).
- **E-mail notification** on submit — one message to
  `settings.FEEDBACK_NOTIFY_EMAIL` via `send_and_log` (0075), scheduled
  in `on_commit` so SMTP latency stays off the request; logged FAILED,
  never re-raised (per [`0079`](../decisions/0079-podpora-enhancements.md),
  supersedes 0046's deferral).
- **No reply field** — "Vyřešené" is the only acknowledgement.
- **List slice `[:50]`** — newest first, no pagination. Likely
  enough for 6 users over the 14-day shadow run.

## States

- **Empty** — "Zatím žádná hlášení." muted-color placeholder
  under the table header.
- **Open feedback present** — orange "● Otevřené" status cell.
- **Mixed open + resolved** — resolved rows have muted Stav cell
  (`opacity: 0.6; text-decoration: line-through`) showing resolver
  email + timestamp underneath; "Otevřít znovu" button on the
  vlastník side.
- **All resolved** — same as mixed, just no open rows.
- **After successful submit** — flash message "Děkujeme — vaše
  hlášení bylo uloženo." + redirect back to `/podpora/`; new row
  visible at top of the table.
- **After successful toggle** — silent redirect back to
  `/podpora/`; row's Stav cell updated.

## What this screen explicitly does NOT do

- No *digest* / batched e-mail — a single immediate notification per
  report ships instead (per 0079); no daily roll-up.
- No per-page "report this page" deep-link is *required*; per-page help
  (0078) may optionally link here with `?page=<label>` (0079).
- No categories, priority, labels, or assignees.
- No reply field, no resolution note.
- No Markdown rendering of `description` — `linebreaksbr`
  preserves newlines, nothing else.
- No pagination — slice `[:50]` newest first.
- No edit / delete affordances for already-submitted hlášení
  (admin only).

## Open questions for this screen

None for MVP. Future considerations are tracked in
[`decisions/0046-support-page.md`](../decisions/0046-support-page.md)
§ Future considerations: e-mail digest of new hlášení, per-page
deep-link auto-filling `page_url`, categories/labels, vlastník
reply field, Markdown.

## UX refresh — Phase 2 (2026-07-03)

Podpora restyled per mockup `17` with refreshed Czech návod (Inventura,
planned příjem, immediate míchání, effective stock, 1 dp). Report form +
feedback-toggle logic preserved.

## Enhancements — Phase 3 (2026-07-21, per [`0079`](../decisions/0079-podpora-enhancements.md))

- `page_url` free-text → **dropdown** of Czech screen names (value ==
  label; no migration).
- **E-mail notification** on every new report to
  `settings.FEEDBACK_NOTIFY_EMAIL` (`send_and_log` seam, `on_commit`);
  new `EmailLog.Category.FEEDBACK`.
- **Direct-contact note** under the form (mailto the admin for
  unanswered/urgent reports).
- Per-page contextual help („?") now also reaches these docs from every
  screen (per [`0078`](../decisions/0078-per-page-contextual-help.md)); the
  per-page panels are full friendly walkthroughs (what the screen is for,
  step-by-step, field/column meanings, tips).
- **Video-návod block** above the report form (`.video-tutorial` /
  `.video-placeholder` in `pages/support.css`) — a 16:9 **poster + play
  button** that reads as a ready-to-play video (poster =
  `static/img/video-tutorial-thumb.png`; no „coming soon" text, intentional so
  it can be filmed as if live). Swap the inner markup for a real
  `<video>`/embed when the clip exists; reuse the image as its poster.
