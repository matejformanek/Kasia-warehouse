# 0013 — Přebalování via paired corrections (not a first-class movement type)

> **Superseded 2026-06-09 by [`0033-prebalovani-out-of-scope-supersedes-0013.md`](./0033-prebalovani-out-of-scope-supersedes-0013.md).**

## Context

[`0006-pack-size-product-variant.md`](./0006-pack-size-product-variant.md)
§ New opens introduced **repack as first-class movement type** as a
*Decide before MVP* slot. The variant layer makes repacking
modellable — decrement one variant, increment another — but the
question was whether to ship a dedicated *Přebalit* screen and a
new movement kind, or handle it via paired corrections on
[`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md).

Kasia repacks (per [`../company-profile.md`](../company-profile.md):
"importer, processor, blender, **and packer**" — bulk 25 kg sacks
become 100 g retail jars). The relevant question is **frequency**:
common enough to need a dedicated screen, or rare enough that a
paired correction is fine?

Operationally at Kasia, repacking is rare. The owner does not call
it out as a daily workflow in
[`../owner-request.md`](../owner-request.md); the dominant flows
are B2B výdej + dodací list and branch ↔ Říčany převod. Repacking
sits beside those, not at their volume.

Matej is acting as Petr's stand-in for this close-out (2026-06-04
design-phase sign-off; Petr is hard to reach asynchronously, so
Matej accepts the residual rework risk).

## Options considered

- **(a) First-class movement kind + dedicated *Přebalit* screen.**
  New enum value (`prebal`); a screen that prompts source variant,
  source quantity, target variant, target count, optional šarže, an
  optional yield-loss field. The system writes a single paired
  movement, linked. Heaviest option; mirrors how a real packing
  operation would look in a Series-B ERP.
- **(b) First-class movement kind, no dedicated screen.** A new
  `prebal` kind, but the operator records it via úprava pohybu
  with explicit source / target variant pickers. Lighter UI; still
  a new enum.
- **(c) Two paired corrections on úprava pohybu** —
  `reason = "přebaleno"`. Operator writes minus on source variant,
  plus on target variant; both records carry the same free-text
  reason. No new screen, no new movement type.

## Choice

**(c) Two paired corrections.** Přebalování is not a first-class
movement kind in MVP. The operator records:

1. A correction on the source variant (typically bulk `kg`):
   negative quantity, reason `"přebaleno"` (plus any helpful
   detail — e.g. *"přebaleno do 100 g dóz, šarže X"*).
2. A correction on the target variant (typically a pack `ks`):
   positive quantity, same reason text.

Both rows surface in
[`../screens/10-historie-pohybu.md`](../screens/10-historie-pohybu.md)
and can be filtered by the `"přebaleno"` reason convention.

## Rationale

- **Frequency does not justify a dedicated screen.** Per the
  first-instinct check in
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md):
  reject the enterprise-shaped suggestion when the simpler version
  works. (c) is the simpler version.
- **Schema already supports it.** Variants are independent stock
  rows per [`0006`](./0006-pack-size-product-variant.md); the
  correction workflow already writes signed quantity adjustments
  per variant. No schema change needed.
- **Audit trail is sufficient.** Two correction rows with the same
  `"přebaleno"` reason text are findable, filterable, and explain
  the operation. The accountant export (if it ever cares) can
  group by reason.
- **(a) and (b) buy linkage.** A first-class `prebal` movement
  links the two halves into one transaction record. That's nice to
  have but not required at MVP scale — and adding it later is a
  promotion of two existing correction rows into one new row, not
  a destructive migration.
- **Schema is forward-compatible.** If přebalování turns out to be
  frequent in operation, a future decision can introduce a `prebal`
  movement kind and a *Přebalit* screen without rewriting the
  variant table or the correction history. Historical pairs stay
  as corrections; new ones use the new kind.

## Date & by-whom

2026-06-04 — Matej (acting as Petr's stand-in for the design-phase
close-out).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The first tech decision (`0014+`) can proceed without an open
  repack-screen slot. The movement-kind enum in MVP is the existing
  set: příjem, výdej, převod, oprava (correction). No `prebal`.
- No new screen file in [`../screens/`](../screens/).

**Forecloses (without follow-on decisions):**

- Yield-loss tracking on a repack (e.g. "decanted 25 kg bulk, only
  yielded 24.6 kg in jars — 0.4 kg loss"). The operator can encode
  this informally by writing the loss in the reason text or as a
  separate small correction; the system does not compute it.
- Linked source ↔ target movement audit (single record per repack).
  In MVP, the linkage is two records sharing the `"přebaleno"`
  reason.

**Resolves:**

- The *Repack as first-class movement type* open from
  [`0006`](./0006-pack-size-product-variant.md) § New opens.

**Affects future decisions:**

- If a future decision promotes přebalování to a first-class
  movement kind, this decision is superseded. The two-correction
  pattern from MVP is the migration baseline — old pairs stay as
  corrections; the new kind takes effect forward only.
