# 0038 — DB locale provider: ICU (`cs-CZ`) on Postgres 18

> Partially supersedes
> [`0016`](./0016-database-postgres.md): the LC_COLLATE/LC_CTYPE
> specifics ("`cs_CZ.UTF-8`") below are replaced by ICU
> `cs-CZ`. Everything else in 0016 stands.

## Context

Per `context/state.md` § Next item 1 (2026-06-10), the compose
stack currently can't bring `db` up with the locale settings
that [`0016`](./0016-database-postgres.md) committed to:

```
initdb: error: invalid locale name "cs_CZ.UTF-8"
```

Root cause: the `postgres:18-trixie` base image ships with a
minimal Debian locale set (`C`, `C.UTF-8`, `POSIX`). The Czech
`cs_CZ.UTF-8` libc locale isn't generated. With the
`POSTGRES_INITDB_ARGS: "--locale=cs_CZ.UTF-8 --encoding=UTF8"`
line in `compose.yaml`, initdb refuses to start the cluster.

To unblock the stack, the locale source has to land in the
image — either by extending the postgres image with `locales-all`
+ `localedef cs_CZ`, or by switching from libc locales to ICU,
which PG18 ships and supports natively as a first-class locale
provider.

This isn't a new requirement — [`0016`](./0016-database-postgres.md)
already commits to Czech collation; the only question is *how*
that collation is sourced.

## Options considered

- **(a) Extend the postgres image with `locales-all`.**
  ```dockerfile
  FROM postgres:18-trixie
  RUN apt-get update && apt-get install -y locales-all && \
      rm -rf /var/lib/apt/lists/*
  ```
  Preserves [`0016`](./0016-database-postgres.md) verbatim
  (`cs_CZ.UTF-8` libc locale). Costs: +~50 MB to the db image, a
  new `Dockerfile.db`, our own image to push (or `build:` in
  compose so it stays per-host), drift risk vs. upstream
  `postgres:18-trixie`. Slim variant of (a): install only
  `locales` + `localedef -i cs_CZ -f UTF-8 cs_CZ.UTF-8` so only
  the one locale is generated (~5 MB), but same Dockerfile +
  image-management story.
- **(b) ICU locale provider.** PG18 supports
  `--locale-provider=icu --icu-locale=cs-CZ` natively. No extra
  packages, no custom image. The libc `--locale` argument still
  has to be set to something `initdb` accepts; we pass
  `C.UTF-8` (universally available in the base image) which only
  drives a handful of libc-bound things (uppercase folding for
  ASCII, regex character classes); the actual sort/comparison
  semantics — the ones Karolína cares about in the catalogue —
  come from ICU. The Czech ICU locale is **`cs-CZ`** (hyphen, not
  underscore — ICU's BCP-47 style).
- **(c) Skip Czech collation entirely.** Run the cluster with
  `--locale=C.UTF-8` (the base image default) and rely on
  application-level sort overrides where needed. Loses the "Czech
  sort order Karolína expects" rationale from
  [`0016`](./0016-database-postgres.md); accumulates ad-hoc
  ORDER BY hacks across the codebase. Wrong shape for an MVP
  whose whole point is Czech-first.

## Choice

**(b) ICU locale provider.** `compose.yaml`'s `db` service moves
to:

```yaml
POSTGRES_INITDB_ARGS: "--locale-provider=icu --icu-locale=cs-CZ --locale=C.UTF-8 --encoding=UTF8"
# LANG env var removed — no longer needed.
```

The `cs-CZ` ICU locale gives the Czech alphabetic order
(č, ř, š, ž all sorted at the correct positions per Czech
collation rules) — same intent as the `cs_CZ.UTF-8` libc locale
that [`0016`](./0016-database-postgres.md) named. `C.UTF-8` is
the fallback libc locale used for things ICU doesn't cover; it's
present in every Debian-based image.

`Dockerfile.db` is **not added** — the stock `postgres:18-trixie`
image is used as-is. No image build step beyond what `0023`
already implies.

## Rationale

- **Native PG18 support.** ICU is the locale provider the PG
  community is steering toward; PG15 introduced it as a default
  option, PG18 makes it first-class. Choosing it now avoids a
  future migration.
- **Deterministic across glibc versions.** libc collation
  behaviour shifts subtly between Debian releases when libc is
  updated; ICU bundles its own collation rules so the sort order
  is stable for the life of the ICU library. Matters at MVP
  scale because the same image runs in dev (Matej's Mac, x86 +
  arm64) and in prod (Hetzner CPX22 x86) — ICU keeps both
  identical.
- **Image stays stock.** No `Dockerfile.db`, no image to push or
  re-tag during upgrades, no drift surface to maintain. Matches
  `.claude/rules/right-sized-for-small-business.md`: boring beats
  clever.
- **Performance.** ICU collation is generally faster than libc
  for non-ASCII strings; on a ~6-user app it doesn't move the
  needle either way but it's the right direction.
- **No data loss risk.** This is a pre-cutover compose-stack fix;
  no production cluster exists yet, so no `pg_dump` / `pg_restore`
  is needed. The cluster is initialised once with the new locale
  provider when the next `docker compose up -d db` lands.

## Date & by-whom

2026-06-12 — Matej (acting as Petr's stand-in per
[`memory/user_role_kasia.md`](../../.claude/projects/-Users-matej-Work-Kasia-warehouse/memory/user_role_kasia.md)).

## Consequences — things this now blocks or unblocks

**Supersedes (in part):**

- The "`LC_COLLATE='cs_CZ.UTF-8'`, `LC_CTYPE='cs_CZ.UTF-8'`"
  specifics in
  [`0016`](./0016-database-postgres.md) § Choice. The
  intent ("Czech sort order Karolína expects") is preserved; the
  mechanism is ICU instead of libc. Everything else in 0016
  (Postgres 18, psycopg 3.2+, `NUMERIC(p,s)` choices, single-box
  deployment) stands. A pointer banner sits at the top of 0016.

**Unblocks:**

- `compose.yaml` `db` service starts cleanly with
  `cs-CZ` collation under `postgres:18-trixie`.
- The locale-blocked test path documented in `state.md`
  2026-06-10 — running the test suite against Postgres (instead
  of SQLite) works without the "neutralised locale" workaround.
- The Hetzner box bring-up per
  [`infra/RUNBOOK.md`](../../infra/RUNBOOK.md) no longer hits
  the locale gate.

**Forecloses (without follow-on decision):**

- Reverting to a libc-only locale provider. To switch back, a
  numbered file naming the ICU-specific failure mode (e.g.
  divergent sort vs. an external Czech reference) would be
  required, plus a dump/restore migration.
- Custom `Dockerfile.db` extensions for locale alone. (If a
  future need for a custom DB image arises — e.g. an extension
  PG18 doesn't ship — that decision lands on its own.)

**Operational notes:**

- Existing local dev databases initialised under the
  neutralised-locale workaround (per `state.md` 2026-06-10) must
  be re-initialised: `docker compose down -v` to drop the
  `pgdata` volume, then `docker compose up -d db`. **No
  production cluster exists yet**, so this is a clean
  re-initialisation.
- `pg_dump` / `pg_restore` cross-locale-provider notes: the
  cluster default locale provider is set at `initdb` time; per-
  database / per-column collations can still be created with
  either provider after the fact. Not needed at MVP scope.
- Application code does not change — Django reads `DATABASE_URL`
  the same way regardless of locale provider.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Same R-set as [`0016`](./0016-database-postgres.md); the Czech
  sort intent is preserved.
