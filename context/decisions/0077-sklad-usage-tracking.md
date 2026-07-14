# 0077 — Per-user usage tracking for `/sklad/`: first-party `ScreenVisit` log

**Date:** 2026-07-14
**Decider:** Matej
**Status:** Active
**Supersedes in part:** [`0076`](./0076-public-site-analytics.md) — the
Forecloses item "Analytics on any `/sklad/` surface." is narrowed to
**third-party / browser-side trackers only**. Everything else in 0076 stands —
explicitly including the Umami context-processor path gate
(`web/context_processors.py`), which is the `/sklad/` + `/admin/`
**load-bearing privacy boundary** with a pinning test: it stays intact and
untouched. This decision adds a different, first-party **server-side**
mechanism that never ships a script to the browser.
**Builds on:** [`0074`](./0074-event-driven-low-stock-alert.md) +
[`0075`](./0075-email-outbox-log.md) (the in-app observability precedents —
Django models, vlastník-gated Správa pages, no new infra),
[`0021`](./0021-audit-hand-rolled.md) + [`0035`](./0035-audit-line-events.md)
(the append-only `MovementAudit` pattern this model mirrors).

## Context

Matej's primary goal for the whole server is to know how the **employees** —
the logged-in operators the app was built for — actually use it: which
operator visited which warehouse screen, and when. The public-site Umami
(0076) was the side dish; this is the main course.

Umami cannot answer it by design: it is cookie-less and pseudonymous, and
0076's Forecloses list bans analytics on any `/sklad/` surface. But the ask
needs no tracker at all — inside `/sklad/` every request already carries
`request.user`. **Identity is native.** What is missing is durability for
*reads*: gunicorn/Caddy logs are ephemeral stdout (gone on container
restart), `auth_user.last_login` records logins only, and `MovementAudit`
(0021/0035) records writes only. Nothing records that an operator opened the
Katalog, a product detail, or a dodák PDF.

This is warehouse-usage data about known, authenticated users — exactly the
territory 0074/0075 kept **in-app** (a Django model + a Správa page), and
that is the shape here too.

## Options considered

1. **First-party middleware + append-only model.** One `ScreenVisit` row per
   authenticated full-page GET under `/sklad/`, written server-side; a
   vlastník-only „Aktivita" page under Správa. No client JS, no third party,
   no new infra. **Chosen.**
2. **Second Umami website + `umami.identify()`.** Rejected — ships a browser
   tracker to operators and reverses 0076's privacy boundary; identity would
   be bolted onto a tool designed to be pseudonymous.
3. **Parse access logs.** Rejected — Caddy/gunicorn logs are ephemeral
   stdout, carry no Django identity, and making them durable + parsed is
   more moving parts than one model.
4. **Do nothing.** Rejected — doesn't answer the primary question; two weeks
   into real use nobody can say which screens operators actually open.

## Choice

**A `ScreenVisit` row per authenticated, full-page, successful GET under
`/sklad/`, written by the project's first custom middleware; an append-only
table kept forever; a vlastník-only „Aktivita" page under Správa.**

1. **Model `inventory.ScreenVisit`** — `user` (FK, PROTECT), `url_name` +
   `namespace` (which screen), `path` (disambiguates detail pages),
   `created_at`. Deliberately absent: IP address, User-Agent, branch,
   method. Append-only per the 0021/0035/0075 pattern; no admin
   registration (EmailLog precedent).
2. **`ScreenVisitMiddleware`** (response phase, registered last): records
   iff GET ∧ path starts `/sklad/` ∧ status 200 ∧ user authenticated ∧ not
   an htmx request ∧ resolved `url_name` not an excluded fragment partial.
   The `create()` is wrapped so a failure can never break a request. One
   synchronous INSERT per pageview — no queue, no batching, at ~6 users.
3. **Tracked on purpose:** PDF opens (`dodaci_list_pdf`, `recipe_pdf` —
   "who opened which dodák PDF" is real usage signal), the root-namespace
   password-change pages, and the Aktivita page itself. **Not tracked by
   construction:** POSTs (writes are `MovementAudit`'s job), htmx fragment
   partials, anonymous requests (the login + password-reset pages serve 200
   to anonymous visitors under `/sklad/` — the `is_authenticated` guard is
   load-bearing, not belt-and-braces), 404s/redirects.
4. **GET-only, pageviews-only.** Writes already have a richer record
   (`MovementAudit` — who, what, why); duplicating them here would be noise.
5. **Retention: keep everything** (0075 precedent). At ~6 users × tens of
   pageviews/day the table stays trivially small for years; no prune job.
6. **„Aktivita" page** (`/sklad/aktivita/`, vlastník-gated like E-maily):
   per-user summary (last visit, 7-day/30-day counts), top screens over 30
   days, and a filterable, paginated recent-visits list with Czech screen
   labels.

## GDPR & transparency

Legal basis: **legitimate interest** of the employer in understanding how an
internal work tool is used. Data is minimal — who / which screen / when —
with no IP, no User-Agent, no content, and no off-box transfer; it is less
invasive than the `MovementAudit` trail operators already generate on every
write. **Operators must be told** the tool logs which screens they open —
Petr communicates this to the team before or at go-live (the same
transparency posture as the audit trail). This is not covered by 0076's
"no consent banner" reasoning (that was about anonymous visitors); it is an
employment-context processing note, recorded here.

## Rationale

- **Identity is already in the request.** A tracker adds a second identity
  system to a surface that has a native one; the middleware just persists
  what Django already knows.
- **In-app beats infra** for warehouse data about known users — the exact
  line 0076 drew when it distinguished itself from 0074/0075. This stays on
  the in-app side of that line.
- **Append-only + keep-forever** matches every observability precedent in
  the repo (MovementAudit, EmailLog) and keeps the model trivial.
- **Minimal fields** keep the GDPR posture defensible and the table small;
  every omitted field (IP, UA, per-interaction events) can be argued for
  later with a concrete need and a new decision.

## Date & by-whom

2026-07-14 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The code PR: `inventory/models/activity.py` (`ScreenVisit`) + migration,
  `inventory/middleware.py` (`ScreenVisitMiddleware`, the project's first
  custom middleware), `inventory/views/activity.py` (`activity_index`),
  the `/sklad/aktivita/` route, the Správa nav item, and tests.
- Answering "does anyone actually use screen X" before pruning or
  redesigning it.

**Commits us to:**

- Maintaining the excluded-fragment list in the middleware: any **new GET
  htmx partial endpoint** must be added to `EXCLUDED_URL_NAMES` or it
  pollutes the Aktivita log (recorded in
  `.claude/rules/frontend-and-templates.md`).
- Telling the operators (via Petr) that screen visits are logged.

**Forecloses (without a follow-on decision):**

- Any third-party or browser-side tracker on `/sklad/` (0076's ban,
  restated in its narrowed form).
- Per-interaction event tracking (clicks, keystrokes, dwell time) —
  pageviews only.
- Retention/pruning jobs — bring a concrete table-size concern first.

**Amends:** `.claude/rules/right-sized-for-small-business.md` — the 0076
carve-out sentence now also points here for the first-party `/sklad/` visit
log. The 0076 file itself gains only the standard superseded-in-part banner.
