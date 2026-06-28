# 0053 — Existence of a `Stock` row IS the "branch carries product" flag

## Context

Reported by Matej (2026-06-28). Concrete case: **Cibule bílá minced** sits at
**0 kg on TYN** and **6 kg on SEZ**. The catalogue and the daily low-stock
e-mail both flag **TYN** as *critical* for Cibule, even though TYN does not
actually carry that product — the only reason a `Stock(TYN, Cibule)` row
exists is some long-since-consumed past movement.

The deeper issue is that the system has no notion of "this branch carries
this product." Stock rows are created lazily by `_apply_line_to_stock`
(`inventory/services.py:74-81`) the first time a movement touches a
`(product, branch)` pair, so any product that has ever moved through a
branch silently becomes a *carried* product there for threshold purposes.
`low_stock_rows` then iterates **every (product × branch) pair** and falls
back to `Decimal("0.000")` when no Stock row exists
(`inventory/services.py:1247-1249`), manufacturing phantom critical alerts
for branches that genuinely don't handle the item. The per-branch chip
computation in `catalogue_index` (`inventory/views.py:768-803`) has the
same shape.

The fix must remain **N-branch extensible** — TYN + SEZ are the seeded
branches today, but `Branch` is already DB-driven via `is_active` (no
hard-coding), and the fix should keep it that way.

## Options considered

- **A — Existence of a `Stock` row IS the flag (chosen).** No new column,
  no new model. Vlastník gets two operator actions on the product edit
  screen: *Přidat na pobočku* (creates a 0-kg row) and *Odebrat z
  pobočky* (deletes the row, warning on non-zero on-hand or
  reservations). New products are seeded with a 0-kg row for every active
  branch on creation.
- **B — Add a `Product.is_carried_at` M2M or a `ProductBranch` join
  table.** Rejected. A second source of truth invites drift (movement
  vs. carry-flag); the small-business rule
  ([`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md))
  says: no new model unless a specific requirement forces it. The sparse
  `Stock` table already encodes the relationship.
- **C — Boolean column on `Stock` (`is_carried`).** Rejected. Same
  drift risk as B, and forces every read site to check both row
  existence *and* a flag.
- **D — Leave the lazy-create behavior, just filter the low-stock report
  to "branches where the product moved in the last N days."** Rejected.
  Heuristic — would hide a genuinely-carried product that simply hasn't
  moved this month, and the catalogue chips would still lie.

## Choice

**Option A.** A branch *carries* a product iff a `Stock` row exists for
that `(product, branch)` pair. Implementation summary:

- `low_stock_rows` iterates over existing `Stock` rows (active product +
  active branch), not the `Product × Branch` cross product. Branches
  without a row do not appear.
- The catalogue per-branch chips computation flips to the same
  Stock-driven iteration.
- `product_detail` per-branch table already iterates Stock rows; only
  the template empty-state changes.
- `product_create` calls a new
  `seed_branch_carriage_for_product(product)` helper that creates a 0-kg
  `Stock` row for every active branch. Preserves today's *everywhere by
  default* behavior, but makes the carry-state explicit and editable.
- Two new vlastník-only POST views:
  - `product_branch_add(product_id, branch_id)` → `get_or_create` a
    0-kg row.
  - `product_branch_remove(product_id, branch_id)` → deletes the row
    even if `quantity > 0` or reservations exist; the UI carries a
    native `confirm()` showing both numbers. Server has no
    precondition.
- The lazy `Stock.objects.get_or_create` inside
  `_apply_line_to_stock` stays. Receiving a product at a new-to-it
  branch via *příjem* is the friendly "now we carry it" path.
- A new data migration
  (`0013_seed_stock_for_existing_products`) backfills 0-kg `Stock` rows
  for every existing `(active product × active branch)` pair on prod,
  preserving today's surface area. After deploy, vlastník curates per
  product using the new *Odebrat z pobočky* action.

The two new domain verbs are **drží / nedrží** (per
[`czech-first-domain.md`](../../.claude/rules/czech-first-domain.md), added
to `context/domain-glossary.md`).

## Rationale

- **No new model, no new column** — sparse `Stock` already encodes the
  relationship, per [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md):
  *"no new model unless a specific feature requirement justifies it."*
- **One source of truth** — row existence + quantity are read together;
  no drift risk between a carry-flag and the actual stock state.
- **Operator-visible fix for the reported bug** — vlastník removes the
  bogus TYN row for Cibule once, and the catalogue + daily mail stop
  lying about it forever.
- **N-branch friendly** — adding a third Branch row + running the
  backfill migration would not auto-add existing products to the new
  branch (no `Stock` rows seeded for pre-existing products). Vlastník
  curates explicitly via the new UI; new products created *after* the
  third branch exists are seeded into all three.

## Date & by-whom

2026-06-28 — Matej (Petr's stand-in; reported bug, picked the
sparse-Stock fix).

## Consequences

**Unblocks / does:**

- `inventory/services.py` — `low_stock_rows` flips to Stock-driven
  iteration; new `seed_branch_carriage_for_product(product)` helper.
- `inventory/views.py` — catalogue chips flip; `product_create` calls
  the seed helper; two new `@require_POST` vlastník-only views
  (`product_branch_add`, `product_branch_remove`).
- `inventory/urls.py` — two new routes under
  `katalog/<int:product_id>/pobocky/<int:branch_id>/{pridat,odebrat}/`.
- `kasia/templates/inventory/product_form.html` — new
  *Pobočky držící tento produkt* fieldset; obsluha sees badges
  read-only, vlastník sees buttons.
- `kasia/templates/inventory/product_detail.html` — replace the
  *Tento produkt zatím nikde…* paragraph with an empty-state row
  inside the per-branch table.
- `inventory/migrations/0013_seed_stock_for_existing_products.py` —
  data backfill, idempotent forward, no-op reverse.
- `inventory/tests.py` — one rewrite + seven new tests covering the
  semantics flip.
- `context/screens/04-katalog-produktu.md` +
  `05-detail-produktu.md` — mention the new *Drží / Nedrží* controls.
- `context/domain-glossary.md` — new headwords *drží / nedrží*.

**Trade-offs:**

- **Removing a non-zero `Stock` row is destructive** — no audit
  movement is generated for the lost on-hand quantity. The UI carries
  a native `confirm()` warning showing the on-hand kg and reserved kg.
  Movements that produced the stock remain in the audit log even after
  the `Stock` row is gone; only the *current quantity* disappears. We
  accept that for simplicity at ~6 users (per the small-business
  rule); reservations on a removed pair will simply fail to net out at
  read time — vlastník should cancel reservations before removing.
- **Lazy `get_or_create` on movement stays** — receiving a product at
  a new branch via *příjem* still creates a Stock row implicitly. This
  is the friendly happy path; we explicitly accept it as a way to
  re-carry a product without an extra click.
- **Per-branch low-stock recipient routing is still out of scope** —
  the single bundled daily mail per
  [`0045`](./0045-low-stock-summary-email.md) /
  [`0052-n-list-recipients-supersedes-0031.md`](./0052-n-list-recipients-supersedes-0031.md)
  stays.

**Does not supersede:** any prior decision. This refines the operational
meaning of "carries" — the sparse `Stock(product, branch)` shape and the
threshold work in [`0043`](./0043-reorder-threshold.md) are unchanged at
the schema level.
