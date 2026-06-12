# 0016 — Database: PostgreSQL 18 + psycopg 3

> The LC_COLLATE/LC_CTYPE specifics ("`cs_CZ.UTF-8`") below are
> superseded by [`0038`](./0038-db-locale-icu.md): the locale
> provider is ICU (`cs-CZ`) instead of libc, sourced from the
> stock `postgres:18-trixie` image. The Czech-sort intent is
> preserved; everything else in this file stands.

## Context

With Python ([`0014`](./0014-language-python-uv.md)) and Django
([`0015`](./0015-framework-django.md)) committed, the DB choice falls
out of R3 (relational with FKs), R4 (exact decimals), R8 (real
transactions), R10 (per-branch monotonic counter under concurrency),
R12 (immutable history).

PostgreSQL is the documented happy path for Django, supports
NUMERIC arithmetic exactly, has `SELECT ... FOR UPDATE` for the R10
counter row, and supports the Czech `cs_CZ.UTF-8` collation natively.

**PostgreSQL 18** is the current major release (released
2025-09); long-term community support runs through 2030-11. **psycopg
3.2+** is the modern Django-recommended driver (psycopg2 is in
maintenance-only mode; psycopg 3 has first-class async support, better
connection pooling, and is what Django itself recommends for new
projects since 4.2).

## Options considered

- **PostgreSQL 18 + psycopg 3.2+ (`psycopg[binary]`).** Current
  stable; well-supported in Django 5.2.
- **PostgreSQL 17 + psycopg 3.** One major behind. No win.
- **PostgreSQL + psycopg2.** Older driver; maintenance-only. New
  projects should use psycopg 3.
- **MariaDB / MySQL.** Decimal arithmetic is workable but Django's
  Postgres-specific features (advisory locks, JSONB if ever needed,
  generated columns) are wasted; collation and Czech sort order are
  more brittle.
- **SQLite.** Excellent for tests and tiny apps; loses concurrent
  writes, lacks the locking primitives the R10 counter wants, and
  doesn't have a Czech collation.

## Choice

**PostgreSQL 18** as the application database, with
**psycopg 3.2+** (`psycopg[binary]`) as the Python driver. Database
created with `LC_COLLATE='cs_CZ.UTF-8'`, `LC_CTYPE='cs_CZ.UTF-8'`,
`ENCODING='UTF8'`. Runs as the `db` service in
[`compose.yaml`](../../compose.yaml) using the `postgres:18-trixie`
image, bound to `127.0.0.1` only, with a named volume `pgdata`.

`NUMERIC(10,3)` is the mass column type per
[`0003`](./0003-primary-unit-kg-decimals.md); `NUMERIC(p,6)` for
recipe ratios per
[`0005`](./0005-mixture-recipe-model.md).

## Rationale

- Postgres is the Django happy path; every R-requirement that
  involves the DB is met directly.
- `cs_CZ.UTF-8` collation gives the Czech sort order Karolína
  expects in the catalogue list.
- `SELECT ... FOR UPDATE` on the per-branch counter row in
  [`0008`](./0008-dodaci-list-numbering.md) is the textbook pattern.
- One Postgres on the same box as the web service is the minimum
  viable per
  [`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md);
  no separate DB host until ~6 users genuinely outgrows it.
- psycopg 3 is the default driver Django recommends; choosing it now
  avoids a forced upgrade later.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- [`0023`](./0023-runtime-orchestration-compose.md) — `db` service
  definition with `postgres:18-trixie` image, named volume,
  localhost binding.
- The Django settings module reads `DATABASE_URL` from env (resolved
  to a Postgres DSN against the compose `db` host or production
  hostname).

**Forecloses (without follow-on decision):**

- Non-Postgres databases for this app.
- psycopg2 as a driver — even if a stray tutorial mentions it.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R3 (relational + FKs), R4 (exact decimal NUMERIC), R8 (real
  transactions), R10 (counter under concurrency), R12 (no-hard-delete
  patterns enforceable via constraints).

**Makes implementable (0001–0013):**

- The full schema implied by 0001–0013 — `product`, `variant`,
  `stock`, `movement`, `dodaci_list`, `dodaci_list_version`,
  `movement_audit` — all map to Postgres tables with the expected
  constraint vocabulary.
- The branch counter from
  [`0008`](./0008-dodaci-list-numbering.md) implemented as a
  `(branch_id, year)` row locked via `SELECT ... FOR UPDATE`.
