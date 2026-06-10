# 0012 — Inventura via the correction workflow (no dedicated screen)

## Context

The *Inventura (stock-take) workflow shape* open in
[`../open-questions.md`](../open-questions.md) § Decide before MVP
has been sitting unresolved since the original screen pass. The
candidates were: dedicated periodic inventura screen, rolling
per-shelf inventura, mobile-assisted inventura, or **no dedicated
screen** — reconcile discrepancies via the existing correction
workflow on
[`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md).

Kasia's inventura cadence is low and informal — this is a
~30-employee company with ~6 active users on this tool, per
[`../company-profile.md`](../company-profile.md). The owner's brief
in [`../owner-request.md`](../owner-request.md) does not mention
inventura as a distinct workflow. The correction screen already
handles the shape of "the system says X, reality says Y, write the
difference with a reason."

Matej is acting as Petr's stand-in for this close-out (2026-06-04
design-phase sign-off; Petr is hard to reach asynchronously, so
Matej accepts the residual rework risk).

## Options considered

- **(a) Dedicated inventura screen.** Periodic full stock-take —
  the screen lists every variant at the branch, the operator types
  in counted quantities, the system computes deltas and writes
  correction movements. Heavy UI; meaningful only if inventura is
  frequent and structured.
- **(b) Rolling / per-shelf inventura.** Lighter version of (a) —
  count one shelf at a time, the system tracks "last counted on"
  per variant. Still a new screen plus per-variant state.
- **(c) No dedicated screen — reconcile via úprava pohybu.** When
  inventura turns up a discrepancy, the operator records a
  correction on [`11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md)
  with `reason = "při inventuře nalezeno manko / přebytek"` (or
  similar) and the physical quantity adjustment. No new screen,
  no new movement type.

## Choice

**(c) No dedicated inventura screen.** Inventura discrepancies are
reconciled via the existing correction workflow on
[`../screens/11-uprava-pohybu.md`](../screens/11-uprava-pohybu.md).

Convention: the operator writes the reason in plain Czech, using
"při inventuře" as the recognisable phrase — e.g.
*"při inventuře nalezeno manko 0,5 kg oregana, doplněno do mínusu"*
or *"při inventuře nalezen přebytek 1 ks 100 g dóza skořice"*. No
enum, no required tag — the free-text reason field on the
correction is sufficient for the audit trail and for any future
filter ("show me all 'při inventuře' corrections in Q2").

## Rationale

- **Cadence is low.** A dedicated screen carries permanent UI cost
  for a workflow that runs a few times a year at most. The
  correction workflow already handles the same shape of movement.
- **Same shape of operation.** Inventura discrepancies are
  effectively corrections: a known stock figure is wrong, the
  operator writes the right figure with a reason. The audit trail
  on úprava pohybu is exactly the audit trail an inventura needs.
- **No new movement type.** Adding an "inventura" movement kind
  would proliferate enum values without semantic benefit — the
  correction movement already records who, when, why, and the
  delta.
- **Forward path.** If Kasia's inventura grows into a structured,
  frequent activity, (a) or (b) becomes a future decision that
  supersedes this one. The correction history with `"při inventuře"`
  in the reason field is the data foundation that future screen
  would consume.
- **Right-sized.** Per
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md),
  the first-instinct check is to reject the new screen and use what
  exists.

## Date & by-whom

2026-06-04 — Matej (acting as Petr's stand-in for the design-phase
close-out).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The first tech decision (`0014+`) can proceed without an open
  inventura schema slot.
- No new screen file in [`../screens/`](../screens/); the existing
  set of 14 + 3 future screens is the full MVP design surface.

**Forecloses (without follow-on decisions):**

- Dedicated periodic inventura UI.
- Rolling per-shelf inventura with "last counted on" state.
- Mobile-assisted inventura (count via phone) — also blocked by
  the 2026-06-03 close-out on *Mobile / scanner support* in
  [`../open-questions.md`](../open-questions.md).

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  MVP* › *Inventura (stock-take) workflow shape*.

**Affects future decisions:**

- If Kasia adopts scanners or a more structured inventura cadence,
  a follow-on decision can supersede this one and introduce a
  dedicated screen. The correction history from MVP becomes the
  baseline data for that screen.
