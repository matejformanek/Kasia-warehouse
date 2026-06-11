# 0035 — Audit trail: extend `movement_audit` with line events

## Context

[`0021`](./0021-audit-hand-rolled.md) landed the hand-rolled
`movement_audit` table with the column set
`(id, movement_id, edited_at, edited_by, reason, field, old_value, new_value)`.
That shape was designed for the per-field "byl X → je Y" diff on
[`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md).

Implementing the movement edit service (Pass 1 of the movement +
audit work — see `context/state.md` § Next item 2) surfaced a gap:
a Movement edit can cover three event types, not just one.

1. **Field changes** on the Movement header or on an existing line —
   exactly what 0021's `(field, old_value, new_value)` shape was built
   for.
2. **Line added** during an edit — a brand-new `MovementLine` appears
   that did not exist before. There is no single "field" that changed;
   the whole line is the change.
3. **Line removed** during an edit — a `MovementLine` is deleted, its
   stock contribution reversed. Again, no single field; the whole
   line is the change.

0021's flat shape can carry (2) and (3) only by overloading: stuffing
verbs into the `field` column (e.g. `field="__line_added__"`), or
serialising the whole line as a JSON blob in `new_value`. Both are
ugly to render on screen 11 and require string-parsing on read.

A small extension to the column set carries all three event types
cleanly and lets screen 11 read `(event, target_kind, field)` directly
without parsing.

## Options considered

- **Overload `field` with verbs.** Keep 0021's column set, write
  `field="__line_added__"` or similar sentinels for line events. No
  schema change. Costs: every reader has to know the sentinel
  vocabulary; rendering the diff means string-matching on the field
  name; future event types compound the problem.
- **Serialise whole-line snapshots into `new_value` / `old_value` as
  JSON.** Keep 0021's column set, drop a JSON object describing the
  line for add/remove events. Costs: JSON parsing on the read side,
  loose typing for what is otherwise a strict per-field log.
- **Extend the column set with `target_kind`, `line_id`, `event`.**
  One row per (event, changed field) — for line add/remove the field
  is empty and the event verb carries the meaning. The column shape
  is loosely generalisable to other audit surfaces later (the
  `target_kind` discriminator makes it cheap to extend).

## Choice

**Extend the `movement_audit` table with three new columns:**

```
target_kind   text, not null    -- enum: "movement" | "line"
line_id       bigint, null      -- MovementLine.id when target_kind="line", else null
                                -- not an FK, so the audit row survives line deletion
event         text, not null    -- enum: "field_changed" | "line_added" | "line_removed"
```

And **relax `field` from `not null` to `not null, default ""`** so
that line-add / line-remove rows can carry an empty `field`. The
`event = "field_changed"` case still carries a non-empty `field`.

Final column set:

```
id              bigserial
movement_id     fk → movement
edited_at       timestamptz, default now()
edited_by       fk → user
reason          text, not null, non-empty (CheckConstraint)
target_kind     text, not null                 -- new
line_id         bigint, null                   -- new
event           text, not null                 -- new
field           text, not null, default ""     -- relaxed from 0021
old_value       text, default ""
new_value       text, default ""
```

Semantics:

- `event = "field_changed"` → `field` non-empty, `old_value` and
  `new_value` carry the per-field diff. `target_kind` is `"movement"`
  for header changes, `"line"` for per-line field changes with
  `line_id` populated.
- `event = "line_added"` → `target_kind = "line"`, `line_id` populated,
  `field = ""`. `old_value` is empty; `new_value` carries a short
  human-readable line summary for the screen-11 renderer.
- `event = "line_removed"` → `target_kind = "line"`, `line_id`
  populated, `field = ""`. `old_value` carries the line summary;
  `new_value` is empty.

The single `reason` text on the edit applies to every audit row
created in that edit's `transaction.atomic()` block.

## Rationale

- **Rendering stays trivial.** Screen 11 reads
  `(event, target_kind, field, old_value, new_value)` directly. No
  JSON parsing, no sentinel-name matching.
- **Strict typing of the discriminator.** `target_kind` and `event`
  are small enums, easy to validate, easy to extend if a future
  movement-level event surfaces.
- **Audit rows survive line deletion.** `line_id` is a plain
  `bigint`, not an FK. The `MovementLine` it references may have been
  deleted by a later edit; the audit trail still has to remain
  readable.
- **Generalises.** When Pass 2 lands the dodací list re-issue trail
  ([`0007`](./0007-auto-reissue-corrected-dodaky.md)), its log can
  reuse this column shape with different enum values rather than
  inventing a third audit table layout.

## Date & by-whom

2026-06-11 — Matej (acting as Petr's stand-in per
[`memory/user_role_kasia.md`](../../.claude/projects/-Users-matej-Work-Kasia-warehouse/memory/user_role_kasia.md)).

## Consequences — things this now blocks or unblocks

**Supersedes (in part):**

- The column list in [`0021`](./0021-audit-hand-rolled.md) §
  Choice — superseded by the column set above. The rest of 0021
  (hand-rolled vs. simple-history rationale, scope across the two
  audit surfaces, append-only semantics) stands unchanged. The
  banner at the top of 0021 points here.

**Unblocks:**

- `inventory.MovementAudit` ships with the extended column set in
  the `inventory/0003_movement_and_audit.py` migration (Pass 1 of
  the movement + audit work).
- `inventory/services.py:edit_movement` writes
  `event = "line_added"` / `"line_removed"` rows for whole-line
  changes without overloading `field`.

**Forecloses (without follow-on decision):**

- Collapsing the event column back into `field` (would re-introduce
  the sentinel-name problem).

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R7 (audit trail with per-field diffs), strictly stronger than
  before — line lifecycle is now captured too.
