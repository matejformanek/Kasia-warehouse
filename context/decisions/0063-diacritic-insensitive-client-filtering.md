# 0063 — Diacritic-insensitive, typo-tolerant, live-as-you-type filtering

**Date:** 2026-07-02
**Decider:** Matej (relaying Petr/Karolína's ask, live-app review)
**Status:** Active
**Relates to:**
- [`0054-adopt-ui-directions.md`](./0054-adopt-ui-directions.md) +
  [`.claude/rules/design-system.md`](../../.claude/rules/design-system.md) —
  adds a new locked sklad JS hook (`data-filter-*`).
- [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
  — client-side folding avoids a new DB layer for ~6 users.

## Context

Every text filter in the warehouse app (`?q=`) does a Django `__icontains`
on the server behind a **"Filtrovat" submit button**. That is
diacritic-*sensitive*: `pepr` does not match `Pepř`, `cerny` does not match
`černý`, and a typo (`peppr`) matches nothing. Petr/Karolína want the filters
to "just work" — accents optional, minor misspellings forgiven, and narrowing
**as you type** with no button.

The affected filters are the `q=` text boxes on Katalog produktů
(`catalogue_index`), Historie pohybů (`movement_history`), and the pobočka
dashboard stock table (`branch_dashboard`). The structured selects
(kind/status/state/branch) and the date range stay server-side.

## Options considered

- **Postgres `unaccent` / `pg_trgm` / ICU nondeterministic collation.**
  Rejected. Tests run on the **host against SQLite** (`Makefile`) while
  prod/dev is Postgres 18; Postgres-only SQL would break the SQLite suite,
  and it is a decision-gated *new DB layer* for a ~6-user tool
  (`no-premature-tech-choices.md` + `right-sized-for-small-business.md`).
- **Python folding in the view** (normalize NFD + strip combining marks,
  compare in Python). Rejected. Keeps the round-trip and the submit button,
  loses "as you type", and pulls all candidate rows into Python anyway.
- **Client-side JS folding over the already-rendered rows.** Chosen.
  DB-agnostic, no new dependency, instant, no round-trip, covers **every**
  Czech diacritic generically via `String.normalize('NFD')` (no hardcoded
  char list). Adds typo tolerance cheaply with a small Levenshtein.

## Choice

- **One reusable, attribute-driven filter behaviour** in the sklad shell
  (`kasia/templates/base.html`), wired per-list by data-attributes — no
  per-page JS. New locked hook: `data-filter-rows` / `data-filter-empty`
  (and the reserved-but-currently-unused `data-filter-count`) on the search
  input, `data-filter-text` on each row.
- **Fold** = `normalize('NFD')` + strip combining marks + lowercase + collapse
  whitespace. **Match** = every typed token is a substring of the row's folded
  text **OR** within a small edit distance of some word in the row. The edit
  distance is **optimal-string-alignment (restricted Damerau–Levenshtein)** so
  an adjacent transposition ("perp" ↔ "pepr") — the commonest typo — costs one
  edit, not two. Thresholds (tokens length ≥3 only): ≤1 for length ≤4, ≤2 for
  5–7, ≤3 for ≥8.
- **Remove the three server-side `q` `__icontains` blocks** in
  `catalogue_index`, `movement_history`, `branch_dashboard`. The `q`/`search`
  value is still echoed into the input so it round-trips in the URL and the
  JS re-applies on load. Structured selects + dates stay server-side.
- **Extend** the same live filter to the status-only lists (Dodavatelé /
  Odběratelé / Pobočky) with a standalone (out-of-form) name search input,
  for consistency — no view change there.

## Rationale

Client-side folding is the smallest change that satisfies all three asks
(accents optional, typos forgiven, live) without touching the database layer
or breaking the SQLite test suite. For ~6 users over lists that already cap at
a few hundred rows, filtering in the browser is instant and needs no infra.

## Consequences

- **Historie pohybů** is capped at the newest 200 rows (unchanged); the client
  filter searches within those 200. Date / branch / tab stay server-side and
  pre-narrow the set as today.
- **The "Nalezeno: N" counts (and history tab counts) stay server-rendered
  totals** for the current server-side filter state (tab/branch/date/status),
  *not* the client-typed text — the server can't know what was typed, and
  keeping them server-rendered leaves the ~17 existing count assertions green.
  Live narrowing is shown by hiding non-matching rows + a JS-toggled
  empty-state (`data-filter-empty`), not a live count. `data-filter-count` is
  supported by the JS but left unwired for now.
- The headline matching logic moves to JS, so pytest can't assert folding /
  typo matching directly. Mitigated by (a) tests asserting each row carries the
  `data-filter-text` the JS consumes and that all rows now render regardless of
  `q`, and (b) manual in-browser verification.
- `data-filter-rows` / `-count` / `-empty` / `-text` join the locked sklad
  JS-hook contract in `design-system.md`; renaming them needs a new decision.
- No new dependency, no DB migration, no Postgres-only SQL.
