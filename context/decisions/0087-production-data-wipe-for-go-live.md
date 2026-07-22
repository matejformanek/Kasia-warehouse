# 0087 — Production data wipe for go-live

## Context

Kasia-warehouse has been live at `kasia.cz` since 2026-07-14 and the
production box (91.98.47.1) still carries the **test + shadow-run data**
accumulated during the design phase and the 14-day shadow run
([`0034`](./0034-shadow-run-before-go-live.md)). Before real operators
start entering real příjem / výdej / dodáky this week, the owner (Petr,
via Matej) wants prod reset back to a clean baseline: keep the
owner/admin accounts, both branches, and the settings — then re-enter the
real catalogue (products, suppliers, customers, recipes, stock) from
scratch.

Two facts about the schema shaped the design:

1. **Almost every operational FK is `on_delete=PROTECT`.** Deletion must
   therefore run in a strict dependency order inside one transaction, or
   it raises `ProtectedError`. There are no signals, no overridden
   `save()`/`delete()`, and no CHECK/UNIQUE constraint fires on a DELETE.
2. **Five "counterparty" rows are seeded reference data the app looks up
   at runtime** by `.get(name=…, is_internal=…)` in
   `inventory/services/counterparties.py` (`_ROLES`): *Míchárna*,
   *Inventura / ruční úprava*, *Převod mezi pobočkami*, *Objednávka*,
   *Neuveden* — plus the default customer *Říčany*
   (`is_default_recipient=True`). Deleting any of them makes míchání /
   inventura / převod / objednávka / blank-supplier příjem **500 at
   runtime** (none self-heal). They must survive the wipe.

This reverses part of a landed decision (0034's "shadow dodáky are kept,
counters not reset at cutover") and is a hard-to-undo operation, so per
[`.claude/rules/decision-log-discipline.md`](../../.claude/rules/decision-log-discipline.md)
it is recorded before it lands.

## Options considered

- **(a) Manual `psql`/Django-shell deletes on the box.** Fast, but an
  ad-hoc destructive write against prod with no review, no test, and no
  reproducibility — forbidden by
  [`infra-as-code.md`](../../.claude/rules/infra-as-code.md).
- **(b) Soft-delete everything (`is_active=False`).** Matches the app's
  usual pattern, but leaves every test row in the DB, still counts against
  reports/queries, and does not reset the dodák number sequences — so the
  first real dodák would not be `0001`. Does not achieve the "clean
  baseline" the owner asked for.
- **(c) Drop + recreate the database.** Would lose the ICU `cs-CZ`
  collation provisioned per [`0038`](./0038-postgres-icu-locale.md) and
  requires re-running all migrations + re-seeding the reference data.
  Heavier and riskier than needed.
- **(d) A committed, reviewed, `--commit`-gated management command that
  hard-deletes everything outside an explicit keep-set, in PROTECT-safe
  order, inside one transaction.** Reproducible, testable, invoked on the
  box the same way `deploy.yml` runs `migrate`.

## Choice

**(d)** — a new `reset_production_data` management command.

- **Hard delete** (not soft `is_active`) — a true wipe, a deliberate
  divergence from the app's usual soft-delete stance, chosen because the
  owner wants the test rows gone, not hidden.
- **KEEP:** users `admin@kasia.cz`, `petr@kasia.cz`, `karolina@kasia.cz`,
  `matej.formanek@kasia.cz` (passwords untouched); branches TYN + SEZ;
  auth groups `vlastnik` / `obsluha`; the `Settings` singleton + both
  `SettingsRecipient` rows; the 5 seeded internal counterparties + Říčany.
- **DELETE everything else** — all operational rows (Movement + lines +
  audit, DodaciList, EmailLog, MixingJob + lines, PlannedTransfer,
  PlannedOrder, Feedback, ScreenVisit, Stock, StockThresholdOverride), all
  entered catalogue (Product, RecipeComponent, non-kept Suppliers /
  Customers), the `DodaciListNumberSequence` rows, the 8 non-kept users,
  and the framework `django_session` + admin `LogEntry` tables.
- **Keep-set is derived, not duplicated:** the counterparty keep-predicate
  reads `(name, is_internal)` tuples from `counterparties._ROLES` (plus the
  `is_default_recipient=True` customer), so it cannot drift from the
  runtime lookups. The user keep-set is a reviewed `KEEP_USER_EMAILS`
  constant.
- **Dry-run by default; `--commit` required to mutate.** A startup guard
  (the only prod safety net — there is no `IS_PROD` flag and the command
  must run with `DEBUG=False`) asserts every kept user exists, ≥1 is a
  superuser, and each counterparty keep-row is present, aborting with
  `CommandError` on any failure. It deliberately does **not** gate on
  `DEBUG` (that would refuse to run on prod).
- **Run path:** backup prod off-repo first (pg_dump), then land the command
  via PR → CI deploy, then invoke on the box via
  `docker compose run --rm web python manage.py reset_production_data`
  (dry-run, then `--commit`) — the same sanctioned one-off-container path
  `deploy.yml` uses for `migrate`, never an ad-hoc shell write.

## Rationale

- **The owner asked for a clean slate**, and soft-delete does not deliver
  one (leftover rows, un-reset counters).
- **PROTECT-safe ordering in one transaction** makes the wipe
  all-or-nothing: a mis-ordered delete aborts with `ProtectedError` and
  rolls back, leaving prod untouched.
- **Deriving the keep-set from `_ROLES`** removes the single most likely
  way to break prod (deleting a counterparty the app resolves at runtime).
- **Committed + tested + run-via-CI-artifact** keeps the mutation in
  reviewed code and off the box's shell, satisfying
  [`infra-as-code.md`](../../.claude/rules/infra-as-code.md).

## Date & by-whom

2026-07-22 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Real go-live: operators enter the real catalogue against an empty,
  clean DB.
- The first real dodák at each branch is `0001` (the
  `DodaciListNumberSequence` rows are deleted and re-created lazily).

**Reverses:**

- The 0034 clause "shadow dodáky are kept, counters not reset at
  cutover." Shadow-run dodáky and their numbering are wiped; a
  `> **Superseded in part by 0087**` banner is added to 0034.

**Intentional data loss (accepted):**

- The `ScreenVisit` / Aktivita history ([`0077`](./0077-sklad-usage-tracking.md))
  and the Podpora / `Feedback` history ([`0046`](./0046-support-page.md))
  from the design + shadow phase are wiped. These are design-phase noise,
  not business records.
- The `EmailLog` outbox ([`0075`](./0075-email-outbox-log.md)) is wiped.

**Rollback:**

- A logical `pg_dump` (`--clean --if-exists --no-owner`) is taken off-repo
  before the run and restored into the **existing** database (never
  drop/recreate — that would lose the 0038 ICU locale). The atomic
  transaction means a failed run needs no rollback; the dump covers only
  a "changed our mind after a clean run" case.

**Forecloses (without a follow-on decision):**

- Re-running the command on a live operational DB — it is a one-time
  go-live tool. It stays in the tree (tested) but should not be run again
  once real data exists.
