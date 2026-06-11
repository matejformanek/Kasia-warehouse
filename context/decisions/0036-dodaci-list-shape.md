# 0036 — Dodací list schema shape: two tables, atomic counter, live FK to Customer

## Context

The Pass 2 plan (DodaciList + Settings + WeasyPrint + e-mail; per
`context/state.md` § Next item 2) needs three small but
forecloses-future-paths choices nailed before code lands:

1. The **shape of the version + send trail**. Decision
   [`0007`](./0007-auto-reissue-corrected-dodaky.md) committed to a
   monotonic internal version counter and a per-dodák audit table;
   that decision tentatively named both a `dodaci_list_version` table
   and a `dodaci_list_email_log` table (a 3-table layout). When Pass
   1's `MovementAudit` table landed under
   [`0035`](./0035-audit-line-events.md) we discovered the
   "version" object carries no data of its own except `(version,
   sent_at, recipients, trigger_reason)` — exactly the columns the
   `email_log` already needs. The third table would only ever be
   a join.

2. **Counter atomicity** for the per-(branch, year) sequence
   committed in [`0008`](./0008-dodaci-list-numbering.md). Two
   plausible implementations: a dedicated sequence row locked
   `FOR UPDATE`, vs. `Max(counter)+1` with a retry loop. The shape
   has to be deterministic against Postgres
   ([`0016`](./0016-database-postgres.md)) and harmless against the
   SQLite dev fallback.

3. **Odběratel snapshot vs. live FK on the dodák row.** Whether the
   dodák denormalises odběratel name / address at issue time, or
   re-reads the live `Customer` record on every render. Already
   half-decided by [`0007`](./0007-auto-reissue-corrected-dodaky.md)
   (PDF re-renders against current template), but the data shape
   needs to make it explicit before the migration lands.

## Options considered

### (1) Version + send trail

- **(a) Three tables** — `DodaciList` + `DodaciListVersion` +
  `DodaciListEmailLog`. Matches the literal wording in 0007. Costs:
  the `Version` table has no columns the `EmailLog` doesn't already
  need; every screen-09 read becomes a 3-way join.
- **(b) Two tables** — `DodaciList(current_version: int)` +
  `DodaciListEmailLog(version, sent_at, recipients, trigger_reason,
  status, error_message)`. The "version" object is a column on the
  dodák, not a table. Screen 09's "verze a odeslání" audit table
  reads the email log ordered by `(dodaci_list_id, sent_at, id)`.
- **(c) One table** — collapse the email log into the dodák and
  serialise as JSON. Loses the per-send row addressability the
  admin "Znovu odeslat" action needs.

### (2) Counter atomicity

- **(a) Dedicated sequence row, `SELECT … FOR UPDATE`.** A
  `DodaciListNumberSequence(branch, year, last_counter)` row per
  `(branch, year)`. Allocation: `select_for_update().get_or_create`
  + `last_counter += 1` inside the same atomic block as the dodák
  insert. Deterministic on Postgres; on SQLite `select_for_update`
  is a silent no-op but SQLite serialises writes globally so the
  race window is closed anyway.
- **(b) `Max(counter) + 1` with retry on unique violation.** No
  schema-level lock. On Postgres without a row lock, two
  concurrent výdej saves can both read the same max and both write
  `+1`; one fails on the unique constraint and the operator sees a
  retry. Works but is race-prone and obscures intent.
- **(c) Postgres native sequence per branch.** Cleanest at the DB
  layer but Django ORM doesn't model "one sequence per row of
  another table" natively; would need a migration per new branch
  and lose the SQLite parity the dev fallback relies on.

### (3) Odběratel snapshot vs. live FK

- **(a) Live FK only.** `DodaciList.odberatel → Customer`. Every
  PDF re-render reads the current `Customer` record. Changes to
  customer name / address after issue propagate to the next render.
- **(b) Snapshot fields at issue.** Add `odberatel_name_at_issue`,
  `odberatel_address_at_issue`, … denormalised at insert. PDFs
  re-render against the snapshot; the live FK is only for joins.
- **(c) Hybrid.** Live FK plus per-version snapshot rows. Captures
  point-in-time at every `[OPRAVA]` send. Most data; most code.

## Choice

### (1) Two tables, not three.

```
DodaciList(
    movement: OneToOneField(Movement, on_delete=PROTECT),
    branch: FK(Branch, on_delete=PROTECT),         # denorm of movement.branch
    odberatel: FK(Customer, on_delete=PROTECT),
    date_issued: Date,                             # = movement.date_issued
    year_issued: PositiveSmallInteger,             # date_issued.year
    counter: PositiveInteger,                      # per (branch, year_issued)
    cislo: CharField(unique=True),                 # f"{branch.code}-{year_issued}-{counter:04d}"
    current_version: PositiveInteger default 1,    # monotonic per 0007
    created_at, created_by,
)

DodaciListEmailLog(
    dodaci_list: FK(DodaciList, on_delete=CASCADE),
    version: PositiveInteger,                      # current_version at send time
    sent_at: DateTime,
    recipients: CharField,                         # comma-joined snapshot
    trigger_reason: Text,                          # "vystavení" | "oprava: <reason>"
    status: TextChoices(SENT, FAILED),
    error_message: Text default "",
)
```

No `DodaciListVersion` table. Screen 09's "verze a odeslání" audit
table reads
`dodaci_list.email_logs.order_by("sent_at", "id")` and renders one
row per attempt. The "version" column on the screen comes straight
from `email_log.version`. This **supersedes the three-table hint**
in [`0007`](./0007-auto-reissue-corrected-dodaky.md) §
Consequences (the wording "schema gains a `version` column and a
separate `dodaci_list_email_log` table" is honored — but the
`version` is a column on `DodaciList`, not a separate table). 0007
remains the authoritative decision for the trigger semantics.

### (2) Dedicated sequence row, `SELECT … FOR UPDATE`.

```
DodaciListNumberSequence(
    branch: FK(Branch, on_delete=PROTECT),
    year: PositiveSmallInteger,
    last_counter: PositiveInteger default 0,
    UniqueConstraint(branch, year, name="unique_branch_year_sequence"),
)
```

Allocation lives in a service helper:

```python
def _reserve_dodak_number(*, branch, year) -> int:
    seq, _ = (
        DodaciListNumberSequence.objects
        .select_for_update()
        .get_or_create(branch=branch, year=year, defaults={"last_counter": 0})
    )
    seq.last_counter += 1
    seq.save(update_fields=["last_counter"])
    return seq.last_counter
```

Called inside the same `transaction.atomic()` block as the dodák
insert. Postgres holds a row lock until the outer commit; SQLite
serialises writes globally so the same code is safe by accident.

### (3) Live FK to Customer; no snapshot fields.

`DodaciList.odberatel` is a plain `ForeignKey(Customer,
on_delete=PROTECT)`. PDFs always re-render against the current
`Customer` record — the same trade-off Petr already accepted for
the PDF *template* on
[`../screens/14-nastaveni.md`](../screens/14-nastaveni.md):

> Changes take effect for **future** dodací listy; historical PDFs
> are re-rendered on demand using the **current** template.

The same "one source of truth" principle applies to customer data.
Corrections to a customer's address after a dodák was issued flow
through on the next render. Point-in-time customer snapshots are
not on the table for MVP; if the accountant ever needs them, that
is a future decision file (and a separate migration).

## Rationale

- **(1)** The version object had no data of its own once we
  inspected what it would carry. Two tables map 1:1 to the screen
  09 view: dodák header + audit list of attempts. The "Znovu
  odeslat" admin action writes one new `EmailLog` row, no
  `Version` row, no JSON shimming.
- **(2)** Option (a) is the textbook serialisable-write pattern;
  Django's ORM expresses it in three lines; reading the code makes
  the lock visible. Option (b) hides the race in a retry loop and
  works only because the unique constraint catches the conflict.
  Option (c) is the DB-pure answer but loses SQLite parity and
  forces a migration per branch — wrong shape for ~6 users.
- **(3)** Snapshotting is a feature, not a default. Adding it
  later is cheap (add nullable snapshot columns, backfill from
  `Customer` on the next render trigger); removing it later means
  reasoning about whether the snapshot or the live value is the
  source of truth, every screen, forever. Since
  [`0007`](./0007-auto-reissue-corrected-dodaky.md) already
  commits to "current template" semantics, "current customer" is
  the symmetric choice; mixing the two would be the surprise.

## Date & by-whom

2026-06-11 — Matej (acting as Petr's stand-in per
[`memory/user_role_kasia.md`](../../.claude/projects/-Users-matej-Work-Kasia-warehouse/memory/user_role_kasia.md)).

## Consequences — things this now blocks or unblocks

**Supersedes (in part):**

- The wording in
  [`0007`](./0007-auto-reissue-corrected-dodaky.md) §
  Consequences that names a separate `dodaci_list_version` table.
  The "version" lives as `DodaciList.current_version`. 0007's
  trigger semantics, [OPRAVA] e-mail behaviour and PDF re-render
  rules stand unchanged. A banner on 0007 points here for the
  schema specifics.

**Unblocks:**

- `inventory.DodaciList` + `DodaciListEmailLog` +
  `DodaciListNumberSequence` ship in
  `inventory/0004_dodaci_list_and_settings.py`.
- `inventory/services.py` gains `_reserve_dodak_number`,
  `_create_dodaci_list_for_movement`,
  `render_dodaci_list_pdf`, `send_dodaci_list_email` plus
  the vydej hook in `apply_movement` and the re-issue hook
  in `edit_movement` (replaces the `# TODO Pass 2` marker).
- Screen 09's "verze a odeslání" reads
  `dodaci_list.email_logs` ordered by `sent_at, id`.

**Forecloses (without follow-on decision):**

- A standalone `DodaciListVersion` row. To re-introduce one,
  write a numbered file that explains what columns it would
  carry that the email log doesn't.
- `Max(counter) + 1` allocation. To switch, write a file naming
  the contention scenario that breaks the sequence row.
- Customer-name snapshotting on the dodák. To add it later,
  write a file that names the historical-record use-case (most
  likely accountant-audit-trail) that requires it.

**Resolves:**

- The Pass 2 plan's "decisions to draft inside this pass" item 1.
