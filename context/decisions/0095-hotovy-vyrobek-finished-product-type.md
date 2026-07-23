# 0095 — Third product type: „hotový výrobek" (finished product, unlimited, sold by the piece)

**Date:** 2026-07-23
**Decider:** Matej (standing in for Petr) — Petr requested the type directly
**Status:** Active

## Context

The Katalog has known two product kinds — `raw_spice` („surovina" / filter label
„koření") and `mixture` („směs"). A separate `is_stock_tracked=False` flag
([`0088`](./0088-recipe-component-notes-and-untracked-ingredients.md)) makes a
product **unlimited** *and* **hidden** everywhere — today only „Voda" carries it,
because a recipe needs water as an ingredient but water is never counted, never
runs out, never appears in the Katalog.

Petr now wants a **third kind, „hotový výrobek"** — a bought-in finished good
sold **by the piece** (dárková balení, hotové zabalené produkty). Its behaviour
is a mix of the two existing ideas:

- **Unlimited, like Voda** — always enough, never deducted, never blocks a výdej,
  never alerts, shown „neomezeno". Kasia does not warehouse-track these; it just
  needs to put them on a dodací list when they leave.
- **Visible and sellable, unlike Voda** — it must show and be creatable in the
  Katalog and be selectable on **výdej** so it lands on the dodák. It is **not**
  in inventura and **not** in příjem (nothing to count, nothing received into
  stock).
- **Sold by the piece („ks")**, not by mass. The piece count is stored in the
  existing `quantity_kg` column; the *display* unit is derived from the kind.

The blocker to reusing `is_stock_tracked=False` is that it also *hides* the
product. „Unlimited" (a stock **behaviour**) and „hidden" (a **visibility**
choice, Voda-only) have to be decoupled.

## Options considered

1. **Reuse `is_stock_tracked=False` like Voda.** Rejected — it hides the product,
   but a hotový výrobek must be visible and sellable.
2. **Add a `unit` schema field (`kg`/`ks`) + a `is_unlimited` column.** Rejected —
   more schema than the requirement needs. The unit is fully determined by the
   kind, and „unlimited" is fully determined by (`not is_stock_tracked` OR the new
   kind); both can be **computed properties**, no columns, no data migration.
3. **New `Kind.HOTOVY_VYROBEK` + two computed properties.** `Product.is_unlimited`
   (`not is_stock_tracked OR kind == HOTOVY_VYROBEK`) is the single "unlimited"
   concept every stock chokepoint keys on; `Product.unit` (`"ks"`/`"kg"`) drives
   display. Visibility stays on `is_stock_tracked`, so only Voda hides and Voda
   stays byte-for-byte identical under both expressions. **Chosen.**

## Choice

Add `Product.Kind.HOTOVY_VYROBEK = "hotovy_vyrobek"` and two read-only
properties:

- **`is_unlimited`** = `(not is_stock_tracked) or kind == HOTOVY_VYROBEK`. Every
  stock chokepoint (deduction, carriage seeding, overdraw pre-check, low-stock
  alert pairs, míchání consume/preview) now keys on this instead of
  `is_stock_tracked`. Voda is unchanged because it is unlimited under both.
- **`unit`** = `"ks"` for a hotový výrobek, else `"kg"`. Piece counts live in the
  existing `quantity_kg` — **no schema change** beyond widening the `kind`
  choices (a state-only `AlterField`, no DDL).

Behaviour of a hotový výrobek (`is_stock_tracked=True`, so **visible**):

- **Katalog:** its own group **„Hotové výrobky — neomezeno"** (`unlimited_rows`),
  parallel to Prázdné / Dochází / V pořádku, rendered only when no `?state=`
  stock-state filter is active. Never in `empty_rows`/`low_rows`/`ok_rows` (those
  are computed from the non-unlimited rest).
- **Výdej:** selectable; the line lands on the dodák; the row shows „ks";
  never counted in the overdraw pre-check; never blocks submit.
- **Příjem:** excluded from the product dropdown (`MovementLineForm(exclude_finished=True)`).
- **Inventura:** excluded from both querysets (`.exclude(kind=HOTOVY_VYROBEK)`).
- **Dodací list (PDF + on-screen detail):** per-line unit — „N ks" (integer) for a
  finished line, „X kg" (1 dp) otherwise.
- **Product detail:** „neomezeno" instead of the per-branch stock table / KPI /
  „Upravit stav skladu".

The `kind` choice is offered on `ProductForm` automatically (it is in
`Meta.fields`). A hotový výrobek keeps the default `is_stock_tracked=True`; the
`is_unlimited` behaviour comes from the kind, so there is no `save()` override.
On **edit**, the `kind` field is locked for any `is_unlimited` product (as it
already is once Stock/recipe references exist) — see Consequences.

## Rationale

Decoupling "unlimited" (behaviour, on `is_unlimited`) from "hidden" (visibility,
on `is_stock_tracked`) is the smallest change that satisfies both the Voda case
(unlimited + hidden) and the finished-product case (unlimited + visible), with no
new columns and no data migration. Computing the unit from the kind avoids a
`unit` field that would be redundant with the kind and could drift out of sync.
Storing pieces in `quantity_kg` keeps the movement/dodák pipeline (one numeric
quantity per line) completely unchanged — the unit is purely a display concern.

## Consequences

- **`is_unlimited` is now the canonical "unlimited stock" predicate.** Any new
  stock read/write site must guard on `is_unlimited`, never on `is_stock_tracked`
  alone. `is_stock_tracked` is now strictly a *visibility* flag.
- **Adding or removing any exclusion** (Katalog group / výdej-in / příjem-out /
  inventura-out), or **storing pieces anywhere but `quantity_kg`**, is a new
  decision.
- **`kind` is locked on edit for an `is_unlimited` product.** A hotový výrobek is
  created with zero Stock rows (the carriage seed early-returns on
  `is_unlimited`). Flipping it to a tracked kind afterwards would never re-seed
  carriage — the pre-existing behaviour that changing a product's `kind` does not
  re-run `seed_branch_carriage_for_product`. Locking the kind sidesteps that edge
  rather than adding a re-seed path. (Same reasoning already locks the kind once
  Stock/recipe references exist.)
- **Aggregate kg totals that could fold in pieces** (`DodaciList.total_quantity_kg`,
  the Historie „Množství" column) exclude `is_unlimited` lines from the kg sum, so
  a piece count is never silently added to a kg figure.
- A hotový výrobek is neither `raw_spice` nor `mixture`, so it can never be a
  recipe component or carry a recipe; the existing recipe/míchání gates already
  exclude it.
- Migration lands as `0029` (state-only `AlterField` on `kind`).
