# 0071 — Block duplicate products on the příjem form (mirror výdej)

**Date:** 2026-07-04
**Decider:** Matej (from the live walkthrough feedback)
**Status:** Active

## Context

During the live walkthrough of the deployed sklad app, an operator logged
in-app feedback (12:08) that the **příjem** (receipt) form lets you pick the
**same product on two different lines**. The **výdej** (issue) form already
prevents this: its `refreshProductOptions()` helper disables an
already-chosen product in every other line's dropdown, so a product can only
be issued once per doklad.

Příjem deliberately allowed repeats — the original reasoning (documented in
`.claude/rules/design-system.md`) was "keeps repeatable products for multiple
batches". But the catalogue is **mass-only** (per
[`0028`](./0028-mass-only-no-packs.md)): a spice is a single tracked mass, not
a set of distinct batches with their own SKUs. Receiving the same spice twice
on one doklad is therefore an error far more often than an intent — the two
lines should be one line (summed), or a second příjem.

## Options considered

1. **Leave příjem as-is (repeats allowed).** Zero work, but the walkthrough
   showed it reads as a bug — an operator can silently double-enter a product.
2. **Block duplicates client-side, like výdej.** Run `refreshProductOptions()`
   on the příjem form too: a product picked on one line is disabled in every
   other line's dropdown. **Chosen.**
3. **Enforce uniqueness on the server (form/model validation).** Heavier —
   a posted duplicate is *harmless* (two received lines just add up), so a
   hard server error would reject data that is arithmetically fine and annoy
   the operator on the round-trip. Rejected.

## Choice

**Option 2: block duplicate products on příjem client-side, exactly like
výdej.** `refreshProductOptions()` runs on **both** movement forms — picking a
product on one line disables it in every other line's product dropdown. This is
**client-side only**: the server adds **no** guard, mirroring výdej. A posted
duplicate (e.g. JS disabled) remains harmless — two received lines that sum.

This **reverses** the "keeps repeatable products for multiple batches" line in
`.claude/rules/design-system.md`.

## Rationale

- **Mass-only catalogue.** Per [`0028`](./0028-mass-only-no-packs.md) a product
  is one mass; two batches of one spice belong on one line (summed) or on a
  second příjem, not as two lines of the same product.
- **Consistency with výdej.** Operators already learn the "a product disables
  itself elsewhere" behaviour on výdej; making příjem match removes a
  surprising asymmetry the walkthrough flagged.
- **Client-side is enough.** A duplicate posted anyway is not corrupting — it
  is two additive received lines. A server guard would reject harmless data and
  cost a round-trip, for no durability benefit.

## Date & by-whom

2026-07-04 — Matej (from the live walkthrough feedback).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `refreshProductOptions()` in `kasia/templates/inventory/_movement_form_lines.html`
  moves out of the výdej-only `{% if show_stock_warn %}` block into an
  always-rendered IIFE, so it runs on **both** the příjem and výdej forms
  (wired on `#lines-body` `input`/`change`/`htmx:afterSwap` + delegated
  `.row-delete-btn` + once on load). `show_stock_warn` still gates only the
  výdej over-stock check.
- `.claude/rules/design-system.md` drops "Příjem does not run any of this — it
  keeps repeatable products for multiple batches" and notes the helper is no
  longer výdej-only.

**Forecloses (without follow-on decision):**

- Multi-line entry of the same product on one příjem doklad. If a real batch
  workflow ever needs it, a new decision reopens it (and would likely need the
  pack-as-SKU model 0028 rejected).

**No change to:**

- Server, models, or forms — the dedup is client-side, exactly like výdej.
- `movement_edit.html` — it has its own `lines-body` and does not include the
  shared partial, so it is untouched.
