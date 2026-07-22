# 0088 — Untracked ingredients (`Product.is_stock_tracked`) + per-component recipe notes

**Date:** 2026-07-22
**Decider:** Matej (standing in for Petr) — ahead of the real-recipe entry batch
**Status:** Active

## Context

A batch of real XLS receptury is about to be entered — **directly via the ORM in
Claude sessions**, one-by-one with names matched by hand, *not* through the app's
XLS importer button. Before that batch lands, two data-model gaps have to close
so the recipes can be represented faithfully:

1. **"Voda" (water) is used in recipes but is effectively unlimited.** It is
   never bought, never counted, never runs out. Today *every* recipe component is
   ordinary tracked stock — there is no way to say "this ingredient exists in a
   recipe but is not a warehouse item". Left as-is, a water component would seed a
   Stock row at every branch, show up as „Prázdné" in the Katalog, trigger a
   „Dochází" e-mail, and block a míchání as a phantom shortage.
   [`0072`](./0072-reorder-threshold-not-null.md) § Forecloses already reserved
   this exact follow-up: *"a new decision reintroduces an explicit 'untracked'
   flag (not a nullable threshold)"*. This is that decision.

2. **Each ingredient line needs its own free-text comment.** Today only the
   *recipe-level* note exists (`Product.notes` on the mixture, „Poznámky k
   míchání", per [`0055`](./0055-recipe-pdf-and-notes.md)). Per Petr the comment
   belongs on the **recipe component** — the same raw spice can carry a
   *different* comment in a different mixture — shown on the recipe **PDF** and
   the **mixture's detail page**, but *not* on the raw ingredient's own product
   page.

No app *feature* (import UI, operator buttons) is added — this is schema +
display/guard plumbing so ORM-entered data behaves correctly.

## Options considered

**For the untracked ingredient (the substantive change):**

1. **Reuse a sentinel threshold / a magic branch.** Model water as a normal
   product with some special threshold or a hidden branch. Rejected: it still
   seeds Stock, still deducts, still shows in every roll-up — the special-casing
   would have to be re-derived at every read site and would leak the sentinel.
2. **A separate `UntrackedIngredient` model, distinct from `Product`.** Rejected:
   `RecipeComponent.component_product` is a FK to `Product`; a parallel type would
   fork the recipe model, the mixing service, the forms, and the PDF. Enormous
   blast radius for one flag's worth of behaviour.
3. **A boolean `Product.is_stock_tracked` (default `True`), guarded at the stock
   read/write chokepoints.** Water stays a `Product` (`kind=raw_spice`) so it
   remains selectable in the recipe form; a single flag drives "no Stock, no
   deduction, unlimited" everywhere. **Chosen.**

**For the comment:** put it on `RecipeComponent` (`note`, a plain `CharField`) vs.
on `Product`. Component-level is the only option that satisfies Petr's
"different comment per mixture" requirement; it has no trade-offs, so it rides
along in this change as a schema addendum.

## Choice

Add two fields (one migration, `inventory/migrations/0026_*`, both with DB
defaults so the non-interactive CI/SSH `migrate` never prompts):

- **`Product.is_stock_tracked = BooleanField(default=True)`** — the substantive
  change. `default=True` keeps every existing product + test fixture tracked (no
  data migration). **Set at product creation only** (ORM / admin): flipping a
  product that already has Stock or movement history from tracked → untracked
  would strand its stock, so it is deliberately **not** an operator action and is
  **not** exposed on `ProductForm` (an unchecked HTML checkbox posts nothing,
  which Django coerces to `False` — that would silently make create-form
  submissions untracked). It is exposed on `ProductAdmin` (`list_display` +
  `list_filter`) only.
- **`RecipeComponent.note = CharField(max_length=255, blank=True, default="")`** —
  the schema addendum. `default=""` is required so `makemigrations` adds a DB
  default and does not prompt. Set via the ORM in the import sessions; **not**
  added to `RecipeComponentForm` (omitting it from `Meta.fields` means a formset
  save preserves existing notes — Django never touches an omitted field), but
  added to the admin inline + `RecipeComponentAdmin` as the fallback edit surface.

### What "untracked" means (the behavioural contract)

An untracked product **never reads or writes `Stock`** and counts as **unlimited**:

- **No Stock rows.** `seed_branch_carriage_for_product` early-returns for
  untracked, so a newly-created Voda gets no rows in the first place.
- **Never deducted.** The central write primitive `_apply_line_to_stock`
  early-returns for untracked, covering every movement path (příjem / výdej /
  transfer / adjustment / mixing consume all funnel through it).
- **Never in a stock report.** Excluded from `low_stock_rows()`,
  `catalogue_stock_groups()` (→ Katalog, obsluha/vlastník Přehled, inventura
  „Dochází" roll-up), and the two self-built inventura querysets (all-branch +
  per-branch). Excluded from the movement product dropdown (unselectable on
  ordinary příjem/výdej — it belongs only in recipes).
- **Never blocks a mix or a výdej.** `plan_mixing_job` and the `start_mixing_job`
  fresh-start loop `continue` past untracked components (so no `MixingJobLine`,
  no consume `MovementLine`, no reservation via `reserved_kg`); the PLANNED→
  RUNNING path needs no guard — its correctness derives from `plan_mixing_job`
  never having created an untracked line. The `_compute_overdraw` výdej check and
  the client `stock_map` skip untracked.
- **Never alerts.** The `apply_movement` / `edit_movement` `low_stock_pairs`
  builders filter to tracked products, so a water line never triggers a „Dochází"
  crossing e-mail.
- **Renders „neomezeno".** In the míchání preview (`_mixing_preview.html`) an
  untracked component's on-hand cell shows „neomezeno", its Stav is „ok", and it
  never contributes to the overdraw warning card.
- **Still a real ingredient on the sheet.** It is **not** filtered out of the
  recipe PDF or the mixture detail recipe table — water has a ratio/kg and
  belongs on the printed míchání sheet.

The **Voda product itself** is created in the import session
(`Product(kind=raw_spice, name_cs="Voda", is_stock_tracked=False)`), not in the
migration.

## Rationale

- **One flag, guarded at chokepoints, not a new type.** The stock read/write
  surface already funnels through a small number of helpers
  (`_apply_line_to_stock`, `seed_branch_carriage_for_product`,
  `low_stock_rows`, `catalogue_stock_groups`, the movement form queryset). A
  boolean checked at those points gives the full "unlimited" behaviour without
  forking `Product`, the recipe model, or the mixing service.
- **`default=True` is a no-op migration.** Every existing row and test fixture
  stays tracked; the suite stays green; no data migration.
- **Creation-only, admin-only is honest about the danger.** Toggling an
  in-use product would strand stock. Keeping the flag off the operator form (and
  off `ProductForm` for a concrete tests-and-coercion reason) makes the unsafe
  transition impossible through the UI.
- **Component-level notes are the only faithful model.** The same raw spice
  legitimately carries different guidance in different mixtures; a product-level
  note cannot express that. No trade-off, so it rides along.
- **Right-sized.** ~6 users, ~30 products, one water row. No new screens, no new
  endpoints, no import-UI change.

## Date & by-whom

2026-07-22 — Matej (standing in for Petr), ahead of the real-recipe entry batch.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The real-recipe ORM entry batch: recipes may reference an untracked „Voda" and
  carry per-component comments and behave correctly everywhere.
- Migration `inventory/migrations/0026_*` (both fields, both DB-defaulted).

**Commits us to:**

- Keeping the untracked exclusion at every listed guard point. Adding or removing
  a guard — or exposing `is_stock_tracked` on `ProductForm`, or letting an
  untracked product into Katalog / Přehled / inventura / alerts / overdraw — is a
  **new decision**. Recorded in `.claude/rules/design-system.md`
  § "Katalog is grouped; Inventura is a nav landing".
- `RecipeComponent.note` flowing to both `recipe_pdf.html` (per-ingredient
  column) and `product_detail.html` (mixture recipe table) — keep them in sync.

**No change to:**

- [`0055`](./0055-recipe-pdf-and-notes.md)'s recipe-level `Product.notes`
  („Poznámky k míchání") — the component note is additive, not a replacement.
- [`0060`](./0060-michani-immediate-only.md)'s immediate míchání + inventura
  `?products=`/`next` contract (untracked ids are simply omitted from the jump).
- [`0072`](./0072-reorder-threshold-not-null.md) / [`0043`](./0043-reorder-threshold.md)'s
  threshold model — untracked is a *separate* axis from the threshold; a *tracked*
  empty product still groups as „Prázdné" exactly as before.
