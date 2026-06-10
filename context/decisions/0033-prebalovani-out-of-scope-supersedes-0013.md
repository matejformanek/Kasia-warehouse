# 0033 — Přebalování out of scope (supersedes 0013)

## Context

Petr's 2026-06-09 reply (Czech, relayed via Matej):

> "Přebalování vůbec nemusíme řešit."

[`0013-prebalovani-via-correction.md`](./0013-prebalovani-via-correction.md)
landed přebalování as a paired-correction pattern on screen 11 —
operator writes negative on the source variant, positive on the
target variant, both rows carry `reason = "přebaleno"`. The
reasoning was that přebalování is operationally rare and a paired
correction is the smallest workable model.

Petr's reply removes the workflow entirely: it is not a real
operation for this tool. Combined with
[`0028-mass-only-supersedes-0006.md`](./0028-mass-only-supersedes-0006.md)
(no variants), there is also no source-and-target variant pair to
track — the schema cannot express přebalování even if Petr changed
his mind tomorrow, because there is no second variant to repack
*into*.

This decision supersedes
[`0013`](./0013-prebalovani-via-correction.md).

## Options considered

- **(a) Keep paired-correction pattern** per
  [`0013`](./0013-prebalovani-via-correction.md). With variants gone,
  the pattern has nothing to operate on; it would degenerate to two
  no-op corrections on the same product. Pointless.
- **(b) Remove the workflow entirely.** No přebalování concept in
  MVP. The `"přebaleno"` reason convention on screen 11 is dropped.
  The přebalení glossary entry is marked out-of-scope.

## Choice

**(b) No přebalování workflow.** Not via a dedicated screen, not via
paired corrections, not via a reason convention.

- Screen 11 (úprava pohybu) keeps free-text reason — operators can
  type whatever they need — but there is no hardcoded `"přebaleno"`
  convention.
- The `přebalení (přebal)` glossary entry is marked
  "out of scope per [`0033`](./0033-prebalovani-out-of-scope-supersedes-0013.md)".

## Rationale

- **Petr's instruction is unambiguous** ("vůbec nemusíme řešit").
- **The premise of [`0013`](./0013-prebalovani-via-correction.md) is
  gone.** [`0013`](./0013-prebalovani-via-correction.md)'s mechanism
  required two stock-bearing rows per product (source variant, target
  variant). After
  [`0028-mass-only-supersedes-0006.md`](./0028-mass-only-supersedes-0006.md)
  there is only one stock row per `(product, branch)`. The pattern
  cannot run.
- **Physical operation continues.** Kasia still physically repacks
  bulk into jars (per
  [`company-profile.md`](../company-profile.md)); the system simply
  doesn't model the act. Stock in kg is unchanged before and after
  a physical repack, which matches Petr's "celková hmotnost" view.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The next models pass writes no `Variant` table (per
  [`0028`](./0028-mass-only-supersedes-0006.md)) and consequently no
  movement-pair pattern for repacks.
- Screen 11 keeps free-text reasons; no `"přebaleno"` shortcut, no
  paired-correction UI guidance.

**Forecloses (without follow-on decisions):**

- Any in-system record of a physical repack. If Petr later wants to
  track repacks, it requires reintroducing a Variant layer (a future
  decision that would itself supersede
  [`0028`](./0028-mass-only-supersedes-0006.md)) plus a new mechanism
  to record the source→target operation.

**Supersedes:**

- [`0013-prebalovani-via-correction.md`](./0013-prebalovani-via-correction.md).
  [`0021-audit-hand-rolled.md`](./0021-audit-hand-rolled.md)'s example
  `reason = "přebaleno"` is now historical only — no movement_audit
  row will carry this reason since the workflow doesn't exist.

**Resolves:**

- The "Repack as first-class movement type" open from
  [`0006`](./0006-pack-size-product-variant.md) — now closed by
  "not in scope" rather than by "via correction".
