# 0092 — Persisted recipe component order (mixing order)

- **Date:** 2026-07-22
- **By:** Matej (prompted by Petr's recepturas; agreed in session)

## Context

Every real receptura's pracovní postup says „Míchat v tom pořadí, jak jsou
suroviny odshora řazeny!" — the ingredient order **is part of the recipe**.
`RecipeComponent` had no order field: `Meta.ordering` and every render site
(product detail, recipe PDF, míchání preview, operator recipe formset, admin)
sorted components **alphabetically by component name**, silently showing a
wrong mixing order. The 18 recipes already on prod were created by ORM scripts
that inserted rows in XLS document order, so their `id` order still carries the
truth — but nothing persisted or displayed it.

## Options considered

- **Persisted `position` field + ↑/↓ reorder buttons on the operator formset** —
  explicit, survives edits, right-sized.
- Rely on `id` creation order only — breaks on any recipe edit (delete +
  re-add reorders), invisible to the operator.
- Drag-and-drop reordering — nicer UX, but needs a JS library or nontrivial
  custom code; overkill for ~6 users (right-sized-for-small-business).
- Formset `can_order` (Django's built-in ORDER field) — renders visible number
  inputs, still needs JS for a decent UX, and stores nothing on the model.

## Choice

`RecipeComponent.position` — `PositiveSmallIntegerField("pořadí", default=0)`,
0-based per-mixture mixing order:

- `Meta.ordering = ("mixture_product__name_cs", "position", "id")` — the `id`
  tiebreak keeps legacy all-zero rows in creation (= XLS) order.
- Every component render site orders by `("position", "id")`: product detail
  (recipe table + „Spočítat dávku" scaler), recipe PDF, míchání preview, the
  operator recipe formset, admin. `MixingJobLine` rows are **created** in
  position order and re-read by `("id",)` (their Meta already preserves it).
  `used_in` on a raw ingredient stays alphabetical by mixture name.
- Operator reorder: ↑/↓ **`.row-move-btn`** buttons per formset row swap the
  `<tr>`; a `renumber()` writes 0..n-1 into hidden per-row `position` inputs in
  DOM order (including `.marked-deleted` rows — harmless, avoids stale values
  on un-delete) after every move / add-row / delete-toggle, then dispatches a
  bubbling `change` event so the `data-guard-unsaved` guard arms. The server
  re-normalizes to dense 0..n-1 over all surviving forms (submitted position,
  form-index fallback) on save — client garbage cannot corrupt order.
- The XLS importer (`create_mixture_from_review`), the seed command and the
  ORM entry scripts set `position` from source row order.

## Consequences

- New **locked hooks** (design-system.md § "Keep stable"): `.row-move-btn` +
  `data-dir`, the hidden `position` input + DOM-order renumber contract, and —
  locking what 0090 left implicit — `#recipe-body` / `#recipe-empty-row` /
  `#recipe-add-row` / `recipe-TOTAL_FORMS`. Renaming any of these is a new
  decision.
- Migration 0028 (AddField + AlterModelOptions). No data migration; a one-off
  idempotent backfill script (scratchpad, per the 0088 workflow) stamps the 18
  existing prod recipes with their XLS document order.
- Future recipe entry (importer button, ORM scripts, formset) must maintain
  dense positions; the server-side normalization makes this self-healing.
