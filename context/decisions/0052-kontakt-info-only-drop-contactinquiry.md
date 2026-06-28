# 0052 — Kontakt is info-only; drop the `ContactInquiry` form, model, and table

## Context

[`0051`](./0051-public-site-ia-and-content.md) shipped the Kontakt page with a
poptávkový **formulář** backed by a durable `ContactInquiry` model (DB-first,
then a best-effort e-mail notification). In local walkthrough (2026-06-28) Matej
decided **not to use a web form as a contact channel at all**: Kasia's B2B
partners reach the firm by phone and e-mail, and a named person directory is how
they actually get to the right desk. The form also looked poor and the page had
no map.

The real public contact data already exists on the old kasia.cz (captured
2026-06-26 / re-scraped 2026-06-28) — a three-person directory (Šulc / Prodej,
Kovačková / Administrativa, Formánek / Nákup), a fax number, and four
provozovny with real addresses, per-branch phones, and building photos. That
makes an info-only page strictly better than the form it replaces.

This decision **partially supersedes [0051](./0051-public-site-ia-and-content.md)**:
the `ContactInquiry` durable-store rationale (options A vs D, the model section)
and the "poptávkový formulář" IA lock no longer apply. Everything else in 0051
(four-page IA, content decoupled from the warehouse DB, modern-web essentials,
discreet sklad link) stands.

## Options considered

- **A — Info-only Kontakt: exec directory + direct phone/email + embedded map;
  remove the form entirely incl. the model + table (chosen).** Phone/e-mail are
  the contact channel. No user PII is stored.
- **B — Keep the form, just restyle it and add a map.** Rejected — Matej does not
  want a web form as a channel; keeping it keeps the only `web → inventory` SMTP
  coupling and a PII store for no benefit.
- **C — Keep the model, drop only the public form (admin-only capture).** Rejected
  — a write-only model nothing writes is dead weight; remove it cleanly.

## Choice

**Option A. Kontakt becomes an info-only page: a contact panel (address, phones,
e-mail, fax, IČO/DIČ, datová schránka, otevírací doba), a three-person
executive directory (photo + name + role + per-person e-mail/phone when
supplied), and an embedded, cookie-free map of the sídlo. The
`ContactInquiry` model, its form, its read-only admin, the `kontakt_ok`
thank-you route, and the `_notify_inquiry` SMTP path are all removed; a
`DeleteModel` migration DROPs the table.** Provozovny is rebuilt at the same
time with the four real locations (decision content, not a new decision).

## Rationale

- **Matej's call:** direct phone/e-mail + a named directory is how Kasia is
  actually contacted; a web form is not a channel he wants to maintain.
- **Real data beats a form:** the scraped directory + addresses + photos make an
  info page genuinely more useful than the placeholder-laden form page was.
- **Less to maintain, cleaner architecture:** removing the form removes the only
  `web → inventory` import (the `_notify_inquiry` SMTP helper), so `web` becomes
  a clean leaf app.
- **No new tech.** The embedded map uses OpenStreetMap's cookie-free export
  iframe — no JS library, no API key, no build step. It is the site's first
  external runtime dependency and degrades gracefully (the "Otevřít v mapách"
  link still works if OSM is down).

## Date & by-whom

2026-06-28 — Matej (owner-side; local-walkthrough decision).

## Consequences — things this now blocks or unblocks

**Unblocks / does:**

- Removal of `web/forms.py`, `ContactInquiry` (`web/models.py`), `web/admin.py`'s
  registration, the `kontakt_ok` view + route + template, `_notify_inquiry` +
  `_CONTACT_RECIPIENTS`, and the `CONTACT_INQUIRY_RECIPIENTS` setting. A
  `0002_delete_contactinquiry` migration DROPs the table (the lone test row goes
  with it — acceptable, it was a test submission).
- A redesigned info-only Kontakt page and a four-location Provozovny page, both
  with embedded maps and real photos.

**Architecture / privacy:**

- **`web` is now a clean leaf app** — no `web → inventory` imports remain after
  `_notify_inquiry` goes.
- **GDPR posture:** no form means **no user PII is stored** on the public site.
  The only third-party data flow left is the embedded map — loading the OSM
  iframe exposes the visitor's IP to the map host. The footer privacy note is
  extended to say so, keeping the "no tracking cookies" claim honest.

**Supersedes (in 0051):** the `ContactInquiry` model section, option D, and the
"poptávkový formulář" part of the Kontakt IA. The rest of 0051 stands.

**Still open (placeholders until supplied):** per-person exec e-mails/phones
(Šulc / Kovačková / Formánek) and the company DIČ.
