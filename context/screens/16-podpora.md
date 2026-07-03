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
   inputs: `page_url` (optional CharField, free-form hint like
   `/katalog/`) and `description` (required TextField).
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
- **`page_url` is optional** — free-form `CharField(max_length=255,
  blank=True)`. Not validated as a URL; treated as a hint.
- **Author is auto-filled** from `request.user` on submit; the form
  never exposes the field.
- **Only vlastník can toggle resolved** — `request.user.is_vlastnik`
  check; obsluha gets a Czech error message + redirect to
  `/podpora/`, not a 403 (friendlier UX, matches the
  `supplier_archive` pattern in `inventory/views.py`).
- **No e-mail notification** on submit (deferred — see decision
  0046 § Future considerations).
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

- No e-mail notification to vlastník on new submit (deferred —
  see decision 0046).
- No per-page "report this page" deep-link / icon (Matej
  explicitly chose the simpler version).
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
