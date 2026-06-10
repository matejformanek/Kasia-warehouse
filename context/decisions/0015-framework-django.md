# 0015 — Web framework: Django 5.2 LTS

## Context

With Python committed in [`0014`](./0014-language-python-uv.md), the
web framework is the next slot. Requirements
R1–R12 in [`../tech-options.md`](../tech-options.md) drive the
choice: server-rendered HTML (R2), full relational ORM (R3), exact
decimals (R4), built-in SMTP backend (R6, R11), real DB transactions
with `SELECT ... FOR UPDATE` for the per-branch counter (R8, R10),
role-based scoping (R9), and a sturdy admin for screens 13 + 14.

Django ships two release tracks:

- **5.2 LTS** (released 2025-04, security support to 2028-04-30).
- **6.0** (released 2025-12, non-LTS, security support to ~2027-04).

5.2 LTS is the right shape for a 6-user system that has to outlive a
single developer's attention.

## Options considered

- **Django 5.2 LTS.** Three years of security fixes. ORM `Decimal`
  support, sequence handling, built-in auth + groups + permissions,
  built-in SMTP, admin, migrations, `select_for_update`.
- **Django 6.0.** Newer features but the security window ends ~2027.
  Forces a 5.2-→6.0 upgrade we don't need yet.
- **FastAPI + SQLAlchemy + Jinja2.** Strong API ergonomics but loses
  the batteries: no admin, no auth, no migrations — all hand-built.
  For a 6-user warehouse tool this is more code, not less.
- **Flask.** Minimalist; same loss-of-batteries as FastAPI without
  the API niceties. The admin alone (screens 13 + 14) is more work
  than 5.2 LTS warrants.

## Choice

**Django 5.2 LTS**, installed as `django==5.2.*`. Apps split by
bounded context (initial: `inventory`). Settings split into
`kasia/settings/base.py` (+ `prod.py` if/when needed).

## Rationale

- LTS window comfortably outlasts MVP shakedown + first year of
  operation. Predictable upgrade story: 5.2 → 6.2 LTS (expected
  ~2027) is a single hop.
- The Django admin covers ~80% of
  [`../screens/13-sprava-uzivatelu.md`](../screens/13-sprava-uzivatelu.md)
  and [`../screens/14-nastaveni.md`](../screens/14-nastaveni.md) for
  free.
- `select_for_update()` + `transaction.atomic()` is the textbook
  pattern for the R10 per-branch counter and R8 výdej atomicity.
- Czech localisation is first-class: `LANGUAGE_CODE = "cs"`,
  `USE_I18N`, `USE_TZ`, decimal/date formatting all behave.
- CZ Python+Django talent pool is abundant — handover risk is low.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- [`0018`](./0018-frontend-htmx.md) — frontend approach (server
  templates + htmx).
- [`0019`](./0019-email-smtp-sync.md) — Django's built-in SMTP
  backend.
- [`0020`](./0020-auth-django-builtin.md) — Django auth + groups for
  the two roles in R9.
- [`0021`](./0021-audit-hand-rolled.md) — hand-rolled audit table
  using Django ORM signals or explicit save-time writes.
- Django skeleton scaffolded in this pass (`kasia` project,
  `inventory` app).

**Forecloses (without follow-on decision):**

- An API-first split (FastAPI / DRF heavy) — re-opening that
  requires a new decision.
- Django 6.x adoption until a future decision overrides the LTS
  preference.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R2 (server-rendered web), R3 (relational ORM), R6 (SMTP),
  R7 (audit patterns), R8 (atomic transactions), R9 (auth + roles),
  R10 (counter under concurrency), R11 (failed-email surfacing),
  R12 (no-hard-delete patterns).

**Makes implementable (0001–0013):**

- The full schema implied by 0001–0013 maps cleanly onto Django
  models with explicit Decimal fields and FK constraints.
- The auto re-issue plumbing in
  [`0007`](./0007-auto-reissue-corrected-dodaky.md) is a Django
  signal + `transaction.atomic()` block.
