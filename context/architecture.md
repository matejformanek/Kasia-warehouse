# Architecture guide

> How the code is organized and where new code goes. Landed with
> [`decisions/0068`](./decisions/0068-code-architecture-restructure.md) +
> [`0069`](./decisions/0069-css-externalization.md). Keep this current when the
> structure changes.

## Layers & import direction

```
templates (html + static/css)      ← presentation, no business logic
  ▲
views/         thin controllers: validate → call a service → render
  ▲
services/      ALL business logic; the only code that writes Stock; transactional
  ▲
models/        schema + invariants (constraints, clean()); no cross-service imports
```

Import direction points **down** only: views→services→models. Services never
import views; models never import services. `forms/` sits beside views;
`admin/` beside models.

## Package map (`inventory/`)

Each monolith is a package with a re-exporting `__init__.py` (explicit ordered
imports, `__all__` for `views`/`services`). External code imports the same names
as before (`inventory.services.apply_movement`, `from inventory.models import
Movement`).

- **`models/`** — `catalogue` (Branch, Product, Customer, Supplier,
  RecipeComponent, Stock, StockThresholdOverride) · `movement` (Movement,
  MovementLine, MovementAudit) · `dodaci` · `mixing` · `planning` · `config`
  (Settings, SettingsRecipient) · `feedback`. FK forward-refs are string refs.
- **`services/`** — `stock` · `movement` (MovementBuilder, apply/edit) ·
  `dodaci_list` (DodakService) · `email` · `mixing` (MixingJobService) ·
  `reorder` · `transfer` · `receipt` · `counterparties` (role registry) ·
  `recipe_import`.
- **`views/`** — `dashboard` · `movements` · `ciselniky` · `catalogue` ·
  `mixing` · `dodaci` · `inventura` · `settings` · `transfers` · `support` ·
  `partials` · `_mixins` (RequireVlastnikMixin, ArchivableCRUDMixin).
- **`forms/`** — grouped by subsystem + `base` (soft-unique-name validator).
- **`admin/`**, **`tests/`** — grouped the same way.

## Conventions

- **Single write path for Stock:** only `services` (via `MovementBuilder` /
  `_apply_line_to_stock`) mutates `Stock`. Never a raw ORM update in a view.
- **Internal counterparties:** get them from `services/counterparties.py` by role
  (`micharna`/`adjustment`/`transfer`/`order`), never by re-querying by name.
- **Permissions:** global `LoginRequiredMiddleware` covers everything; vlastník
  gating is `RequireVlastnikMixin` (CBV) or the shared helper (function views).
- **Size guidance (not law):** files ≲400 LOC, functions ≲50 LOC. Over that,
  extract a named helper or a service method.
- **CSS:** tokens in `static/css/tokens-{sklad,web}.css`; shared rules in
  `base-*.css` + `components/`; per-screen rules in `pages/<screen>.css` linked
  from `{% block extra_head %}`. `<link>` only — never inline `<style>` or
  `@import`. See `.claude/rules/design-system.md` for the locked class/hook
  contract.

## Recipes

- **Add a screen:** view in the right `views/*` module → URL name in
  `inventory/urls.py` → template extending `base.html` → per-screen CSS in
  `pages/<screen>.css` linked via `extra_head`. Reuse shared classes.
- **Add a číselník (archivable master):** subclass the CBVs with
  `ArchivableCRUDMixin` (model, form, templates, guards via `archive_preconditions()`).
  Only drop to function views if it has product-edit-level complexity.
- **Add a movement type / stock effect:** build it through `MovementBuilder`
  inside a `services/` function wrapped in `transaction.atomic`; if it needs a
  system counterparty, add a role to the registry + a seed migration.
