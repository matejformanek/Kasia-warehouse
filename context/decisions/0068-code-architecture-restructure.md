# 0068 — Code architecture restructure (packages, CBV/mixins, service classes)

**Date:** 2026-07-03
**Decider:** Matej
**Status:** Active

## Context

The operator app is feature-complete and live on prod. Growth left the
`inventory` app as a handful of monolith modules: `tests.py` 7654 LOC,
`views.py` 3420, `services.py` 2030, `models.py` 1253, `forms.py` 716,
`admin.py` 623 — all single files, **0 class-based views**, near-identical
číselník CRUD (supplier/customer/branch/product), 7 copy-paste
internal-counterparty getters, 7 hand-rolled `Movement(...)` construction sites,
and several 100–260 LOC functions. This is a purely *technical* restructure —
**no behavior/logic change** — to make the codebase short-filed, encapsulated,
de-duplicated, and easy to expand. The 406-test suite is the behavior contract.

## Options considered

- **Idiomatic Django-OOP (chosen).** Split monoliths into packages; use Django's
  own class-based-view + mixin machinery for the repetitive archivable CRUD;
  extract service classes only where state genuinely clusters; keep clear
  one-off function views. Encapsulation and zero duplication without fighting the
  framework.
- **Full OOP everywhere.** Every view a class; a repository layer
  (`Repository[T]`); an ABC `MovementProducer` hierarchy the mixing/transfer/
  adjustment flows inherit. Most "OOP" but fights Django idiom and the
  `right-sized-for-small-business` rule — heavier to maintain for ~6 users.
- **Structure-only.** Split files + dedupe helpers, keep procedural style. Lowest
  risk but leaves the CRUD repetition in place.

## Choice

Idiomatic Django-OOP, landed on one branch (`ft_arch_restructure`) internally
ordered so the full test suite stays green at each checkpoint, merged as one PR.

- **Packages** (each with a re-exporting `__init__.py`, explicit ordered imports,
  `__all__` where large): `inventory/models/`, `services/`, `views/`, `forms/`,
  `admin/`, `tests/`. External import paths (`inventory.models.X`,
  `inventory.services.x`, `from inventory.views import …`), `urls.py`, and all
  tests keep working unchanged. **No migration change** (migrations key on
  `app_label` + model name, not module path).
- **`ArchivableCRUDMixin` + generic CBVs** for the CRUD that shares shape:
  **Supplier** (clean fit) and **Customer** (via an `archive_preconditions()`
  hook — can't archive the default recipient / internal rows). **Branch**
  optionally, via `slug_field='code'`. **Product `create`/`edit` stay
  function-based** — the 139-LOC edit (3 formsets, kind-lock, branch-carry) would
  gain complexity, not lose it, inside a generic mixin.
- **`RequireVlastnikMixin`** centralizes the two divergent `_require_vlastnik`
  copies (inventory + accounts).
- **Internal-counterparty registry** (`services/counterparties.py`) replaces the
  7 getters, keyed by role: `micharna` "Míchárna" (internal, 0007), `adjustment`
  "Inventura / ruční úprava" (internal, 0008), `transfer` "Převod mezi
  pobočkami" (**internal=False** so the dodák fires, 0010), `order` "Objednávka"
  (internal, 0015).
- **`MovementBuilder`** is the single constructor for the 7 `Movement`+lines build
  sites; **`MixingJobService`** / **`DodakService`** cluster their flows. All
  preserve the existing `transaction.atomic` boundaries, the nested-savepoint
  negative-stock guard, and the `on_commit` deferred-email lambdas.

## Rationale

Django's happy path is function views + service functions; its idiomatic OOP is
CBV/mixins for repetitive CRUD, not bespoke class hierarchies. That path removes
the real duplication (the ~15 CRUD views, 7 getters, 7 build sites) and shortens
files without the maintenance cost the full-OOP option would impose on a ~6-user
tool — respecting `right-sized-for-small-business.md`. Keeping the genuinely
complex views (product edit) procedural avoids a leaky abstraction.

## Consequences

- No behavior change; no schema/migration change; no new dependencies.
- Every inconsistency surfaced while centralizing is recorded in
  [`../refactors/0068-restructure-discrepancies.md`](../refactors/0068-restructure-discrepancies.md);
  any behavior/pixel change gets explicit approval, never a silent fold-in.
- New architecture guide: [`../architecture.md`](../architecture.md) — the recipe
  for adding a screen / číselník / movement type.
- CSS externalization ships alongside under
  [`0069`](./0069-css-externalization.md).
- Verification gate at each checkpoint: `make test` green · `ruff check` ·
  `manage.py check` · `makemigrations --check --dry-run` reports no changes.
