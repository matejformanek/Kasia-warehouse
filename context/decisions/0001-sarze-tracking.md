# 0001 — Šarže (batch) tracking: optional

## Context

Šarže — the supplier-printed (or self-assigned) lot ID, optionally
paired with an expiry date — appears as an "open" or "if enabled"
field across screens 03, 05, 06, 07, 09, 11, 12, `future-misseni.md`,
`future-skart-skarty.md`, and `workflows.md`. No commitment had
landed. The question was elevated into
[`../open-questions.md`](../open-questions.md) as the first
*Decide before code* item during the round-two self-review.

Kasia vera is a B2B spice distributor; food-safety recall on a sold
batch is rare but not impossible. The owner (`owner-request.md`)
asks for "něco jednoduchého" and explicitly names B2B výdej + dodací
list email as the load-bearing flow; branch ↔ Říčany převody coexist
with that, neither subordinate. The user (acting as Petr's stand-in)
confirmed during this round that both flows are first-class.

## Options considered

- **Mandatory.** Every příjem records šarže + expiry; every výdej
  picks from a specific batch (FIFO/FEFO or manual). Recall and
  expiry visibility from day one, at the cost of friction on every
  line and a heavier schema (batch as a first-class entity, batch-
  stock table, picking UI).
- **Optional.** Šarže field present and nullable on all movement
  lines and on stock. Operator records when they have the info,
  skips otherwise. Reporting tolerates absence. Upgradeable to
  "mandatory for these product classes" later by flag, not by
  migration.
- **Absent in MVP.** No šarže concept anywhere. Simplest schema and
  UI. Re-adding it later is a migration, and the door to mixture-
  batch traceability and to any recall claim is shut until then.

## Choice

**Optional.** The system has a nullable šarže field on every
movement line (příjem, výdej, převod) and on stock-by-batch where
batches were recorded. Operators may record or skip per line.
Reporting and exports tolerate null šarže.

## Rationale

- The owner asked for *simple*. Mandatory šarže across ~6 untrained
  users on every line is friction the brief does not call for.
- The food-safety recall path is non-zero but unverified — Kasia has
  not asked for audited traceability, and the external accountant
  has not asked for batch info on the dodací list. "Absent" forecloses
  that path; "optional" keeps it open at near-zero schema cost.
- Forward path is asymmetric: "optional → mandatory-per-product" is a
  flag flip; "absent → anything" is a migration plus backfill of
  missing history. Cheaper to keep the door open.
- Mixture-batch traceability (see `future-misseni.md`) is deferred,
  but if it is ever wanted, having šarže fields already present makes
  the upgrade local rather than systemic.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Screens 06 (příjem), 07 (výdej), 12 (převod do Říčan), 11 (úprava
  pohybu): the "if batch capture is enabled" hedging is removed. Šarže
  is a present-but-optional field. Update the screen files in Phase B
  to reflect this.
- Screen 09 (detail dodacího listu) shows šarže column when any line
  has one; hides or shows-as-blank when none does.
- `future-misseni.md` keeps its current stance (no per-source-batch
  traceability in the first cut) — that remains an upgrade path, not
  a blocker.
- `future-skart-skarty.md` keeps optional šarže on odpis lines.

**Forecloses (without a follow-on decision):**

- Audited recall claims: optional šarže is not enough for "show me
  every kg from batch X with certainty". A future decision can
  promote to mandatory-per-product if the business is ever asked.
- FIFO/FEFO enforcement at výdej: optional šarže cannot enforce
  "oldest batch first" because not every line has a batch.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  code* › "Šarže (batch) tracking".

**Affects future decisions:**

- Mixture recipe data model (Phase A Q5) — recipes do not need to
  pin source batches because traceability is opt-in.
- Pack-size granularity (Phase A Q6) — orthogonal; not constrained
  by this choice.
