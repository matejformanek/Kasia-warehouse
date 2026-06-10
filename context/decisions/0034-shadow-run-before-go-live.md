# 0034 — 14-day shadow run before go-live

## Context

Petr's 2026-06-09 reply (Czech, relayed via Matej):

> "14 dnů nanečisto, pak naostro."

The first real deploy of Kasia-warehouse will run **14 days in
shadow mode** before cutover to operational use by branch staff.
During the shadow window, Petr (and Karolína) use the system on
real data without operational reliance — branch staff continue to
work as they do today. The point is to surface bugs, workflow
mismatches, and missing affordances against real volume before the
business depends on the system.

This is operational guidance, not an architectural choice. It's
recorded as a decision because (i) it constrains the deploy timeline
(no "ship and call done" cutover), (ii) it sets an explicit
sign-off gate before branch staff onboard, and (iii) it shapes the
first feedback loop with Petr.

This decision is **new** — it does not supersede any prior entry.

## Options considered

- **(a) Ship to prod and onboard branch staff immediately.** Standard
  small-business cutover. Contradicts Petr's instruction.
- **(b) 14-day shadow window with Petr + Karolína only.** Per Petr's
  reply. Real data, no operational reliance, bug list collected over
  the window. Cutover after Petr signs off.
- **(c) Phased rollout by branch (TYN first, SEZ second).** Slower;
  Petr's reply doesn't ask for it and the two branches are
  operationally symmetric per
  [`warehouses.md`](../warehouses.md).

## Choice

**(b) 14-day shadow run.**

- Deploy date = day 0; shadow window = day 0 → day 14.
- Users during shadow: Petr and Karolína only. Branch staff are not
  yet onboarded.
- Real data: every dodák Petr or Karolína records during the shadow
  is a real dodák. Číslování counters per
  [`0008`](./0008-dodaci-list-numbering.md) start from `0001` as
  designed; the dodáky from the shadow window are kept (not reset
  at cutover).
- Cutover criteria at day 14: Petr's explicit sign-off after the
  shadow run. Bug list resolved or triaged. See
  [`open-questions.md`](../open-questions.md) § Decide later for the
  detailed criteria entry.

## Rationale

- **Petr's instruction is unambiguous** ("14 dnů nanečisto, pak
  naostro").
- **Right-sized for the operation.** Per
  [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md):
  backups matter more than uptime. A 14-day shadow lets the system's
  durability story (daily restic snapshots per
  [`0027`](./0027-hosting-hetzner.md)) be validated before branch
  staff commit to using it.
- **Surfaces workflow mismatches early.** Petr is the only person
  with the full mental model of how the operation actually runs;
  having him use the system on real data for two weeks is the
  cheapest possible "did we get it right" check.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The deploy plan in
  [`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md) gets a "shadow
  run" gate between first deploy and "open to branch staff".
- [`context/state.md`](../state.md) carries a milestone: deploy day
  0; cutover day 14.

**Forecloses (without follow-on decisions):**

- A same-day branch-staff onboarding. The 14-day gate is mandatory.

**Resolves:**

- Nothing in [`open-questions.md`](../open-questions.md) directly; it
  adds a new "14-day shadow run cutover criteria" item to *Decide
  later* — what specific criteria count as "ready to go live"
  (resolved bug list? Karolína sign-off? a minimum number of real
  dodáky issued?).

**Affects future decisions:**

- The first production rollout plan, once written, references this
  decision for the timing gate.
