# 0090 — Per-component recipe note is editable on the operator recipe form

**Date:** 2026-07-22
**Decider:** Matej (standing in for Petr)
**Status:** Active — amends
[`0088`](./0088-recipe-component-notes-and-untracked-ingredients.md)

## Context

[`0088`](./0088-recipe-component-notes-and-untracked-ingredients.md) added
`RecipeComponent.note` (a per-ingredient free-text comment) but deliberately kept
it **off** `RecipeComponentForm` — set via ORM / admin only. The reasoning there
was that the note would be entered once, in the ORM import sessions, and omitting
it from the formset guaranteed a formset save could never wipe an
admin-entered note.

That was a mistake. When the vlastník **creates or edits a směs manually** (the
operator recipe formset on the product-edit screen), the per-ingredient note has
to be editable there too — otherwise a note can only ever be added through the
Django admin, which the operator does not use. Petr confirmed: the note „must be
there" on the manual recipe form.

## Options considered

1. **Leave it admin/ORM-only (0088 status quo).** Rejected — the operator can't
   set a per-ingredient note when building a recipe by hand, which is the normal
   path. The admin is not part of the operator workflow.
2. **Add `note` to `RecipeComponentForm.Meta.fields`.** **Chosen.** The recipe
   formset is already **vlastník-only** (`can_edit_recipe = is_mixture and
   is_vlastnik`), so the field inherits that gating — no new permission surface.

## Choice

Add **`"note"`** to `RecipeComponentForm.Meta.fields`
(`("component_product", "ratio", "note")`). Render it as a third editable column
(„Poznámka") in the recipe formset table on `product_form.html`, in both the
live rows and the hidden `#recipe-empty-row` clone template, and extend the
add-row JS to rewrite the cloned `note` widget's `name`/`id` onto the
formset-prefixed scheme (same as `component_product` / `ratio`).

**Consequence of making it a form field:** a formset save now **writes** the note
(a cleared field empties it). This is the intended editable behaviour and
replaces 0088's "omitting it preserves the note" guarantee — the note is now
operator-owned data, not admin-only.

Scope: the **operator recipe formset** (`product_edit`). The XLS-import review
form is out of scope (the importer parses ratios + names, not per-line notes).

## Rationale

- **The manual recipe path is the normal path.** Editing on the form is where the
  note belongs; admin-only was an over-cautious carry-over from the ORM-entry
  framing.
- **No new permission surface.** The recipe formset is already vlastník-only, so
  the field is automatically vlastník-only.
- **Small, contained.** One field on one form + one table column + the existing
  clone-JS rewrite. No model change (the field exists since 0088), no migration.

## Date & by-whom

2026-07-22 — Matej (standing in for Petr).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The vlastník sets/edits a per-ingredient „Poznámka" directly when building or
  editing a recipe on the product-edit screen.

**Amends 0088:**

- 0088's "`RecipeComponent.note` … **not** added to `RecipeComponentForm`
  (omitting it preserves existing notes on a formset save)" clause is **reversed**.
  A banner is added to the top of 0088 pointing here. Rule text in
  `.claude/rules/design-system.md` § "Katalog is grouped" is updated accordingly.

**Companion fix (0089, not a decision):**

- 0089 added `Product.default_batch_kg` to `ProductForm` but `product_form.html`
  renders fields **explicitly** and omitted the widget, so the vlastník could not
  actually set the default batch on the create/edit screen. Fixed here: a
  „Výchozí dávka" field block is rendered on `product_form.html`, gated on the
  BoundField (`{% if form.default_batch_kg %}`) so it stays vlastník-only. Ships
  in the same PR because the user reported both gaps together.

**No change to:**

- The `note` render surfaces from 0088 (recipe PDF per-ingredient column +
  mixture-detail recipe table) — unchanged; still **not** on the raw-ingredient's
  own page nor the scaler table.
- `RecipeComponent.note`'s schema (added in migration 0026; no migration here).
- The untracked-ingredient half of 0088 — untouched.
