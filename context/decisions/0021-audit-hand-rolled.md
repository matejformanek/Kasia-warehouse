# 0021 — Audit trail: hand-rolled `movement_audit` table

## Context

R7 in [`../tech-options.md`](../tech-options.md) and the design in
[`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md):
every correction records the original value, the new value, the
editor, the timestamp, and a mandatory free-text reason. The screen
renders a per-field "byl X → je Y" diff.

[`0007`](./0007-auto-reissue-corrected-dodaky.md) introduced a
second small audit surface — the `dodaci_list_version` +
`dodaci_list_email_log` tables — for the re-issue / re-send trail.

Audit scope across the whole project is **two narrow surfaces**:

1. Movement edits (this decision's table).
2. Dodací list re-issue + e-mail send/failure (already designed in
   [`0007`](./0007-auto-reissue-corrected-dodaky.md)).

Not whole-model history. Not every field on every model.

## Options considered

- **`django-simple-history` 3.11.** Auto-records full history rows
  for whole models. Comes with admin integration, time-travel
  querying, "as of" lookups. Powerful but pulls a dependency for
  what is effectively two tables of audit data; introduces extra
  history tables for every registered model.
- **`django-auditlog`.** Generic, signals-based; lighter than
  simple-history but still a dependency carrying patterns we don't
  need.
- **`django-pghistory`.** Postgres triggers under the hood; more
  database-y and arguably more robust, but adds a generated-table
  layer behind the ORM.
- **Hand-rolled `movement_audit` table.** Schema:
  `(id, movement_id, edited_at, edited_by, reason, field,
  old_value, new_value)`. One row per changed field per save. The
  edit view computes the diff (changed fields only) inside the
  same `transaction.atomic()` block that updates the movement.

## Choice

**Hand-rolled `movement_audit` table.** Columns:

```
id              bigserial
movement_id     fk → movement
edited_at       timestamptz, default now()
edited_by       fk → user
reason          text, not null
field           text, not null         -- e.g. "quantity", "variant_id", "sarze"
old_value       text, null             -- string-rendered for portability
new_value       text, null
```

One row per *changed field*. The edit view computes the diff (only
fields whose value actually changed) inside the same
`transaction.atomic()` block that updates the movement. Rendering
on screen 11 is a `SELECT … WHERE movement_id = ?` ordered by
`edited_at`.

`dodaci_list_version` and `dodaci_list_email_log` (from
[`0007`](./0007-auto-reissue-corrected-dodaky.md)) remain their own
narrow tables for the re-issue trail — they audit a different
object lifecycle and benefit from purpose-built columns
(`version`, `pdf_blob`, `sent_at`, `error`).

## Rationale

- **Scope is two tables, not the whole model graph.** Pulling
  django-simple-history for that is dependency weight without
  benefit. The
  [`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
  first-instinct check applies: reject the enterprise-shaped
  solution.
- **The screen renders "byl X → je Y" per field.** The natural
  representation of that data is already (field, old, new) rows —
  rendering doesn't need transformation work.
- **Migration shape is predictable.** Whole-model history tables
  add an extra migration on every model change forever. A
  hand-rolled audit table changes only when its own shape changes.
- **No dependency upgrade churn.** simple-history follows Django
  version compat; one less moving piece across Django LTS hops.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The `movement_audit` table lands in the first migrations pass
  (next pass).
- The screen 11 diff renderer is a straight ORM query against the
  audit rows for a given movement.

**Forecloses (without follow-on decision):**

- Time-travel queries ("show the state of movement X as of date
  Y") at the model level. If that capability is ever asked for, a
  future decision can introduce simple-history *for that specific
  use case*, with the existing `movement_audit` table staying as
  the operational diff surface.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R7 (audit trail with per-field diffs).

**Makes implementable (0001–0013):**

- [`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md)
  diff rendering.
- [`0007`](./0007-auto-reissue-corrected-dodaky.md) is unaffected
  — its tables stay separate.
- [`0012`](./0012-inventura-via-correction.md) inventura
  reconciliation writes through the same `movement_audit` rows
  with `reason = "při inventuře"`.
- [`0013`](./0013-prebalovani-via-correction.md) přebalování
  records paired corrections, each with their own `movement_audit`
  rows tagged `reason = "přebaleno"`.
