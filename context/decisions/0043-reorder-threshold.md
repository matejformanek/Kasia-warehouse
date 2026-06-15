# 0043 — Reorder threshold per product, with per-branch override

**Date:** 2026-06-14
**Decider:** Matej (relaying Petr's 2026-06-14 ask)
**Status:** Active

## Context

Petr (via Matej, 2026-06-14): the warehouse system must give him an
**advance** view of stock. Today every flow (`apply_movement`,
`start_mixing_job`) decrements stock the instant the operator clicks
"vystavit / spustit". There is no per-product reorder point. Result:
Petr finds out about low oregano *after* it has already left the shelf.

This decision answers the storage + lookup + semantics of the
threshold. The reservation half of the story
(*committed-but-not-yet-gone* stock) lands in
[`0044`](./0044-reservations-planned-states.md); the daily e-mail
summary lands in [`0045`](./0045-low-stock-summary-email.md). The three
decisions ship together — a threshold without reservations triggers too
late, and reservations without a panel surface are invisible.

## Options considered

1. **Per-product default only.** One number per product, applied
   identically across branches. Simplest, but loses the (real) case
   where TYN sells fast and needs a higher threshold than SEZ for the
   same product.
2. **Per-branch only.** Forces every product × branch combination to
   have its own row. ~30 products × 2 branches = 60 numbers Petr fills
   in. Too much typing for the common case where TYN and SEZ have the
   same threshold.
3. **Per-product default + per-branch override.** Single number on the
   product covers the common case; a narrow override table covers the
   exception. **Chosen.**
4. **No threshold; rely on shadow-run instinct.** Rejected — Petr's
   ask was explicit: "ráno přijde e-mail s tím, co dochází".

## Choice

**Option 3: per-product default + per-branch override.**

### Storage

- `Product.reorder_threshold_kg: DecimalField(max_digits=10,
  decimal_places=3, null=True, blank=True)` — the per-product default.
- `StockThresholdOverride(product, branch, threshold_kg)` — a separate
  model holding per-branch overrides. `UniqueConstraint(fields=
  ["product", "branch"])` + `CheckConstraint(threshold_kg >= 0)`.
- Lookup helper `threshold_for(product, branch) -> Decimal | None`
  returns override-row if present, else `product.reorder_threshold_kg`,
  else `None`.

### `None` semantics

`None` means **no threshold set, do not alert**. Zero is meaningful
(alert at literal empty), so the field is nullable rather than
defaulting to 0. New products start with `None` — Petr fills numbers
in as he understands each spice's reorder point.

### Effective stock formula

`effective_kg(product, branch) = Stock.quantity − reserved_kg(product,
branch)` — see [`0044`](./0044-reservations-planned-states.md) for
`reserved_kg`. Dashboard, detail page, and e-mail summary all read this
same helper. **No denormalised "effective" column** — computed on read.

### Tier

Editing the product threshold and branch overrides is **vlastník-only**,
consistent with
[`0040-operator-crud-tiering.md`](./0040-operator-crud-tiering.md)'s
planning-vs-execution split. Obsluha sees the badge ("dochází
oregano"), doesn't change the number.

## Rationale

- **Common case stays cheap.** One number per product covers most
  spices; only branches whose throughput differs need an override row.
- **Two-table shape, not denormalised.** Computing `effective_kg` on
  read at ~6 users is trivially fast (a few dozen Stock rows). A
  materialised column would need an invariant-keeping cron + every
  Stock-mutation path would have to update it.
- **`None` ≠ `0`.** Some products (seasonal) are deliberately let to
  zero between Christmas runs. Conflating "no alert" with "alert at
  zero" would surface noise for products Petr explicitly doesn't
  track.
- **Vlastník-only.** Threshold is planning data — same tier as the
  recipe (per
  [`0005`](./0005-mixture-recipe-model.md) +
  [`0040`](./0040-operator-crud-tiering.md)). Obsluha shouldn't
  silently retune the alert level.

## Date & by-whom

2026-06-14 — Matej (relaying Petr's ask).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `inventory.Product.reorder_threshold_kg` and
  `inventory.StockThresholdOverride` ship in the next migration.
- `inventory/services.py` gains `threshold_for(product, branch)` and
  `effective_kg(product, branch)` helpers; see
  [`0044`](./0044-reservations-planned-states.md) for the dependency
  on `reserved_kg`.
- Owner dashboard, branch dashboard, product detail page, and the
  e-mail summary all read these helpers via `low_stock_rows()`.
- `inventory/forms.py` `ProductForm` gains the threshold field;
  inline `ThresholdOverrideFormSet` renders on the product-edit page
  (vlastník-only block in `product_form.html` per the existing
  `{% if user.is_vlastnik %}` precedent).

**Forecloses (without follow-on decision):**

- Per-month / seasonal thresholds (winter pepř threshold ≠ summer
  pepř threshold). Out of MVP; if Petr asks, a new decision adds a
  `valid_from / valid_to` window column to the override model.
- Threshold editing by obsluha. To open, supersede this decision and
  update [`0040`](./0040-operator-crud-tiering.md) at the same time.

**Resolves:**

- The "ráno přijde e-mail s tím, co dochází" half of Petr's
  2026-06-14 ask — the threshold + helpers feed the panel & e-mail.
  Reservations + e-mail live in 0044 + 0045.

**Cross-cutting:**

- Branch dashboard's hardcoded `quantity < 1` status logic
  (views.py ~327–368) is replaced by `threshold_for` + `effective_kg`
  per-(product, branch). Three states: `prázdné` (effective ≤ 0),
  `dochází` (effective < threshold), normal.
