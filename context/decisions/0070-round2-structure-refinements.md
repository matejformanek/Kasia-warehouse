# 0070 — Round-2 structure refinements (recursive sub-packaging + components layer)

**Date:** 2026-07-03
**Decider:** Matej
**Status:** Active
**Continues:** [`0068-code-architecture-restructure.md`](./0068-code-architecture-restructure.md)
+ [`0069-css-externalization.md`](./0069-css-externalization.md) (executes, does not amend)

## Context

Round 1 (PR #26) split the six `inventory` monoliths into re-exporting packages
(0068) and externalized all inline CSS into `kasia/static/css/` (0069) — strictly
behavior-preserving. Two things were named-but-folded-in, plus one readability gap
remains:

- `inventory/views/movements.py` is still a single 832-LOC module inside the
  already-split `views/` package. 0068 authorizes the six *top-level* packages but
  does **not** explicitly cover a **recursive sub-package** (a package nested inside
  an already-package).
- 0069 **names** a `components/` CSS layer but Round 1 left the component rules in
  `base-sklad.css` — the layer was never assembled. The append-only rule forbids
  editing 0069 to clarify its scope, so the clarification is recorded here.
- `services/movement.py` carries the dodák PDF/e-mail on-commit boilerplate twice
  (`apply_movement` / `edit_movement`), differing only in the `trigger_reason`.

This is a purely *technical* refinement — **no behavior/logic change, no pixel
change, no schema, no migration.** The 406-test suite is the behavior contract.

## Options considered

- **Inert-only refinement (chosen).** Recursively sub-package the one oversized
  module; assemble the `components/` layer as a byte-identical move; extract the
  duplicated on-commit block into a module-private helper. Nothing a user sees
  changes.
- **Fold in the divergent rules too** (reconcile `.sub-head`/`.cislo`/`.asof`
  margins, decompose `edit_movement`, Branch→CBV). Rejected for this round — each
  is a pixel/behavior change or a larger refactor the user declined; they stay
  out of scope.
- **Leave as-is.** Rejected: the movements module and the un-assembled components
  layer are the two loose ends Round 1 explicitly deferred to Round 2.

## Choice

- **Recursive sub-packaging is permitted** for an oversized module inside an
  already-split package, using the same re-exporting `__init__.py` + `__all__`
  contract as 0068 (external import paths unchanged; `from inventory.views import X`
  and `from inventory.views.movements import X` both keep resolving). **First
  application:** `inventory/views/movements.py` → `inventory/views/movements/`
  (`_shared` / `history` / `prijem` / `vydej` / `edit` / `partials`).
- **Round 2 executes 0069's named `components/` CSS layer.** That layer is
  **sklad-scoped**: 0069's named components (kpis / tables / dialogs / filters /
  forms) are all sklad classes, so `components/*.css` are `<link>`ed from
  `base.html` only; the public surface keeps `base-web.css` and there is **no
  shared cross-surface component tier** (the `--line` token collision + the
  deliberate 0054-vs-0058 divergence make a shared tier cost more than it removes).
  This is a **clarification of 0069's intent recorded here — not an edit to 0069.**
  Rule bodies move byte-for-byte; the `.over-stock`/zebra source order is preserved
  by keeping both in `components/tables.css`.
- **Extract a module-private `_send_dodaci_on_commit(dodaci_list, trigger_reason)`
  helper** in `services/movement.py` for the two identical on-commit blocks; each
  call site supplies its own `trigger_reason` (`"vystavení"` vs `f"oprava: {reason}"`).
  Behavior-preserving: neither site is in a loop, and tests monkeypatch the origin
  modules (`services.dodaci_list.*` / `services.email.*`), not this namespace.

## Rationale

Recursive sub-packaging is the same pattern as 0068, applied one level deeper — the
re-export contract keeps every external import path and `urls.py` unchanged. The
components layer was already decided in 0069; this only assembles it, sklad-scoped,
as a byte-identical move. The helper removes a copy-paste without changing the
transaction or on-commit semantics. All three respect
`right-sized-for-small-business.md` — they shorten and de-duplicate without adding
abstraction a ~6-user tool doesn't need.

## Consequences

- No behavior change; no schema/migration change; no new dependencies; rendered
  HTML and the concatenated CSS cascade stay byte-identical.
- `.claude/rules/design-system.md` updated: the concrete `components/*.css` file
  list + the fixed `<link>` order (tokens → base → components{tables, forms, kpis,
  filters, chips, dialogs} → `{% block extra_head %}` page) added as a hard
  constraint; components are sklad-scoped; locked class names + JS/HTMX hooks
  unchanged.
- `context/architecture.md` `views/` package-map shows `movements/` as a
  sub-package.
- **0069 and 0068 are NOT edited** — append-only permits only a
  `> Superseded by NNNN` banner, which does not apply (0070 continues, not
  supersedes).
- Every inconsistency surfaced while consolidating is logged in
  [`../refactors/0068-restructure-discrepancies.md`](../refactors/0068-restructure-discrepancies.md);
  the inert-only scope means all entries should be inert — anything that would
  change a pixel/behavior is escalated, not folded in.
- **Out of scope (user declined for this round):** frontend visual polish,
  Branch→CBV migration, decomposing `edit_movement`/`start_mixing_job`/
  `product_edit`, reconciling divergent CSS rules, and the literal infra layer
  (audited clean + right-sized — untouched).
- Verification gate unchanged from Round 1: `pytest` 406 green · `ruff check` ·
  `manage.py check` · `makemigrations --check` = No changes · `collectstatic`
  succeeds · byte-identical HTML/CSS diff.
