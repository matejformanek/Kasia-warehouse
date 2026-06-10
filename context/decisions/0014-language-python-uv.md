# 0014 — Language / runtime: Python 3.14 via uv

## Context

Design phase closed 2026-06-04 with decisions
[`0001`](./0001-sarze-tracking.md)–[`0013`](./0013-prebalovani-via-correction.md)
landed. The first tech-stack decision is the language / runtime — every
later decision (framework, ORM, PDF library, container base image)
depends on this slot.

The standing pre-commitment in
[`../../.claude/rules/python-uses-uv.md`](../../.claude/rules/python-uses-uv.md)
fixes *how* Python would be set up, but not *whether*. This file
exercises the *whether*.

Candidate languages were narrowed in
[`../tech-options.md`](../tech-options.md) § 4 to: Python/Django,
Ruby/Rails, PHP/Laravel, Elixir/Phoenix, TypeScript/Next.js, plus the
off-the-shelf-ERP and headless-CMS branches. Python won the primary
recommendation on R1–R12 fit (exact decimals via `Decimal`, mature
PDF story via WeasyPrint, CZ talent abundance for handover).

Python 3.14 is the latest stable release (released 2025-10) and is
the LTS Python release; it is supported through 2030-10. Pinning the
major+minor explicitly avoids drift when Python 3.15 lands in late
2026.

## Options considered

- **Python 3.14 + uv.** Current stable, supported to 2030.
  `pyproject.toml` + `uv.lock` reproducibility. `uv sync` works
  identically on dev laptop and inside the container.
- **Python 3.13.** One minor behind. No advantage for this project;
  loses a year of upstream support.
- **Python 3.12.** Two minor behind, supported through 2028. Safe
  conservative choice but no reason to lag — `python:3.14-slim-trixie`
  is the same operational shape.
- **Ruby 3.x + Rails.** Capable on R1–R12 but CZ Ruby talent pool is
  thinner than Python for handover.
- **PHP 8.x + Laravel.** Cheap CZ hosting and abundant developers,
  but decimal ergonomics and WeasyPrint-quality PDF rendering are
  weaker.
- **TypeScript / Node + Next.js.** Workable as a monolith but the
  JS-ecosystem churn is operational debt for a 6-user system that
  has to outlive several Node major releases.

## Choice

**Python 3.14, managed by uv.** `.python-version` pinned to `3.14`;
dependencies in `pyproject.toml`, lockfile committed as `uv.lock`.
All Python commands run via `uv run …` (per
[`../../.claude/rules/python-uses-uv.md`](../../.claude/rules/python-uses-uv.md)).

## Rationale

- R1 (Czech UTF-8) and R4 (exact decimals via `Decimal` →
  Postgres NUMERIC) are first-class in Python.
- R5 (PDF) is best-served by WeasyPrint, a Python library — see
  [`0017`](./0017-pdf-weasyprint.md).
- CZ talent pool: Python + Django are widely taught in CZ
  universities and bootcamps; handover risk is the lowest of the
  candidates.
- `uv` is the project-wide standing toolchain
  ([`../../.claude/rules/python-uses-uv.md`](../../.claude/rules/python-uses-uv.md));
  pinning Python at 3.14 is one `uv python pin 3.14` call.
- Python 3.14 supported through 2030-10. Comfortably outlasts the
  Django 5.2 LTS window (see [`0015`](./0015-framework-django.md)).

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- [`0015`](./0015-framework-django.md) — web framework can name Django.
- [`0016`](./0016-database-postgres.md) — psycopg 3 as the driver.
- [`0017`](./0017-pdf-weasyprint.md) — WeasyPrint as the PDF library.
- [`0022`](./0022-container-image.md) — multi-stage Dockerfile with
  `python:3.14-slim-trixie` runtime + `uv` for dependency install.
- The Python toolchain rule
  ([`../../.claude/rules/python-uses-uv.md`](../../.claude/rules/python-uses-uv.md))
  flips from conditional to active.

**Forecloses (without follow-on decision):**

- Other languages for any new service in this project. If a future
  decision adds (say) a Go worker, that decision must supersede the
  "two-tier, single-language" assumption.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R1 (UTF-8), R4 (exact decimals), R7 (audit-trail patterns), R12
  (immutable history) — all first-class in Python.

**Makes implementable (0001–0013):**

- The `NUMERIC(10,3)` mass model from
  [`0003`](./0003-primary-unit-kg-decimals.md) → Django
  `DecimalField(max_digits=10, decimal_places=3)`.
- Recipe ratios at 6 dp from
  [`0005`](./0005-mixture-recipe-model.md) → same field shape.
