# 0046 — Support page (in-app docs + feedback log)

**Date:** 2026-06-16
**Decider:** Matej (2026-06-16, conversation with Claude during prod
swap session — request placed after favicon landed)
**Status:** Accepted

## Context

Petr's user pool is ~6 people (Petr, Karolína, 2× obsluha at TYN,
2× obsluha at SEZ). When something doesn't work or a user isn't
sure which screen to use, the fall-back today is **call Matej or
Karolína**. That doesn't scale even at 6 users — Matej is now the
operator, not the customer — and it leaves zero record of what
people get stuck on, which is exactly the signal we need during
the 14-day shadow run per [0034](./0034-shadow-run-before-go-live.md).

Two adjacent needs from the same screen:

1. **Reference / "what is this page for"** — operators new to the
   tool keep asking "kam mám zaznamenat …?". A single in-app help
   page with a per-screen reference plus common workflows would
   let them self-serve.
2. **Feedback log** — bugs, questions, feature wishes, "tohle by
   se mi líbilo jinak". Today these vanish into chat/SMS to Matej.
   A simple DB-backed log captured at submission time gives
   Matej a curated backlog and gives users transparency on what's
   been said.

External tools (Linear, GitHub issues) are off the table for ~6
non-technical users — adds a second login and a second context.
A wiki / Markdown docs site (MkDocs, Hugo) is also too much
infra for a help page that probably won't change weekly.

## Options considered

- **A — Separate "help" microsite (Hugo / MkDocs on a subdomain).**
  Rejected: extra deploy target, extra DNS, the wiki itself
  becomes another thing to keep in sync. The whole point of the
  ~6-user shape is "everything in one app".
- **B — External issue tracker for feedback (Linear / GitHub).**
  Rejected: second login, second context, none of the operators
  have github/linear accounts and shouldn't need to.
- **C — Single in-app `/podpora/` page with two sections —
  static-template docs above + DB-backed feedback form/list below.**
  **Chosen.** One Django view, one new model, one template, one
  nav link. Matches the small-business shape per
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md).

## Choice

**Implement option C.** Concretely:

### New model `inventory.Feedback`

| Field | Type | Notes |
|---|---|---|
| `id` | auto PK | |
| `created_by` | FK → `accounts.User` (PROTECT) | who reported |
| `created_at` | DateTime, auto_now_add | |
| `page_url` | CharField(max_length=255), blank=True | optional ref, e.g. `/katalog/` |
| `description` | TextField | free-form Czech |
| `resolved_at` | DateTime, nullable | null = open |
| `resolved_by` | FK → `accounts.User` (SET_NULL, nullable) | vlastník who closed |

`Meta.ordering = ["-created_at"]`. No migration data seed; the
table starts empty.

### Page layout `/podpora/`

Three sections on one Django template:

1. **Návod k použití** — static Czech content with two parts:
   - "Co kde najdu" — bulleted reference of each page (~14 short
     lines, grouped by category)
   - "Postupy" — 5-6 step-by-step workflows (příjem, výdej,
     plánovaný převod, míchání plánované + ad-hoc, inventura,
     oprava staršího pohybu)
   - Lives directly in the template (not in a DB). Right-sized:
     this changes when the app changes, which means the dev
     editing the template is the same person editing the docs.
2. **Nahlásit chybu / požadavek** — Django form with
   `page_url` + `description` inputs and a submit button.
3. **Historie hlášení** — table of `Feedback` rows (newest
   first), 20-row pagination via simple `[:20]` slice for MVP.
   Vlastník sees "Vyřešit" / "Otevřít znovu" toggle button per
   row; obsluha sees the same rows but no toggle.

### Permissions

- **All logged-in users** can submit feedback and see the full
  feedback list (transparency at 6-user scale; if anyone wants
  privacy, they ping Matej directly — out of scope here).
- **Only vlastník** can mark resolved / re-open. Matches the
  existing tiering pattern from
  [`0040`](./0040-operator-crud-tiering.md).

### URL routes

- `GET /podpora/` — render page
- `POST /podpora/` — submit feedback
- `POST /podpora/<int:pk>/vyresit/` — toggle resolved state
  (vlastník only)

### Navigation

Add **Podpora** link to `base.html` main nav, right-aligned near
the user menu (visible to all logged-in users, like the other
nav links).

## Rationale

The single in-app page is the simplest version that solves both
needs together. Splitting docs from feedback would mean two
separate pages users have to remember; bundling them keeps the
mental model "tady je všechna pomoc" / "here is all the help".

The static-template docs avoid the trap of building an authoring
UI for content that the dev (Matej) edits anyway. When the app
changes, the template changes — same git commit. No drift between
code and docs.

The DB-backed feedback gives Matej a curated backlog with
attribution (who, when, what page) and a state (open/resolved)
so users can see their report was actually noted. Resolved-toggle
is the only state machine — no priority field, no labels, no
assignment — because none of those are needed at 6 users. If
shadow-run reveals more state is needed, add it then.

## Consequences

**Now:**
- New `inventory.Feedback` model + migration (`0011`).
- New view, form, URL routes, template.
- `base.html` gains "Podpora" nav link.
- Tests added (~6 cases: submit, list, toggle as vlastník,
  reject toggle as obsluha, page_url optional, description
  required).
- New screen design doc `context/screens/16-podpora.md`.

**Blocks / unblocks:**
- Unblocks self-service help for operators during shadow run
  ([0034](./0034-shadow-run-before-go-live.md)).
- Unblocks Matej building a real backlog without external tools.

**Future considerations (deferred):**
- E-mail notification to Matej when new feedback is submitted —
  trivial to add later, not in this pass; daily e-mail batch
  would mirror the low-stock summary shape from
  [0045](./0045-low-stock-summary-email.md).
- Per-page "Report this page" button auto-filling `page_url` —
  nicer UX but Matej explicitly asked for the simpler version.
  Easy upgrade later (one extra `?page=…` query param).
- Categories / labels (bug vs question vs wish) — not yet
  warranted; the description field is free-form Czech.
- Vlastník reply field — for now, "resolved" is the only
  acknowledgement. If shadow-run reveals operators want a
  written reply, add a `resolution_note` TextField.

## Cross-references

- [`0034-shadow-run-before-go-live.md`](./0034-shadow-run-before-go-live.md) — why this matters now
- [`0040-operator-crud-tiering.md`](./0040-operator-crud-tiering.md) — vlastník-only toggle pattern
- [`0045-low-stock-summary-email.md`](./0045-low-stock-summary-email.md) — shape of future e-mail batch
- [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md) — "one app, one DB"
