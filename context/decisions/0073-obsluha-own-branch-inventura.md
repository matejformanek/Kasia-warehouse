# 0073 — Obsluha may run inventura for their own branch (amends 0040 + 0065)

**Date:** 2026-07-04
**Decider:** Petr via Matej (obsluha-parity walkthrough)
**Status:** Active

## Context

Comparing what a branch operator (`obsluha`) sees against the owner
(`vlastník`) surfaced that **inventura is entirely vlastník-only**: the
`inventura_edit` view is gated by `_require_vlastnik` and the sidebar/mobile nav
item is wrapped in `{% if user.is_vlastnik %}` (per
[`0065`](./0065-inventura-sidebar-nav.md)). Under
[`0040`](./0040-operator-crud-tiering.md) "vlastník … edits stock" and ordering
is owner-only (`can_order = is_vlastnik`), so stock-taking was reserved for the
owner.

In practice the branch operator is the person physically counting the shelves.
Petr confirmed the operator should be able to **run inventura for their own
branch** — count, correct the stock, and (per the fork below) place replenishment
orders — without being able to see or touch the other branch or the cross-branch
roll-ups.

## Options considered

1. **Read-only inventura for obsluha.** Let them view counts but not write
   `[STAV]` corrections. Rejected — the whole point of inventura is to correct
   what the count found; a read-only view is just the Katalog they already have.
2. **Full inventura, all branches (same as vlastník).** Rejected — an operator
   must not see or edit the other branch's stock (consistent with the own-branch
   scoping the rest of their surface already enforces — movements, dodáky,
   Přehled).
3. **Own-branch inventura only.** Obsluha reaches inventura solely for
   `code == their branch`; the cross-branch **"Vše"** (`code=vse`) and **"Dochází
   zboží"** (`code=dochazi`) views and any other branch code return **403**. The
   single-branch **"Dochází" toggle** (client-side row filter) stays available —
   it is scoping the visible rows, not a separate view. **Chosen.**

### Sub-fork — the objednávka (Příjezd) column

The per-branch inventura also lets a row carry a **Příjezd** date, which creates
a **planned příjem** (objednávka) instead of an immediate correction — a power
previously owner-only (`can_order`). **Petr chose: obsluha gets the full
per-branch inventura including the objednávka column** (not a stock-correction-
only variant). Branch staff may thus place replenishment orders for their own
branch.

## Choice

**Obsluha may open `inventura_edit` only for their own branch** (the full
editor: `[STAV]` corrections **and** dated objednávky). `inventura_edit` grows a
role guard: a non-vlastník must be `obsluha` with a `branch`, `code` must equal
their branch code, and `cross_branch` (`vse` / `dochazi`) is refused — otherwise
`PermissionDenied` (403). The sidebar + mobile **Inventura** nav item now renders
for `is_vlastnik or is_obsluha` (obsluha always has a branch, so its href points
at their branch code). The inventura template's **branch switcher / Vše / Dochází
zboží links stay vlastník-only** (obsluha would 403 on them). The branch **Přehled**
(`branch_dashboard`) gains a top-right **Inventura** button pointing at
`inventura_edit code=branch.code`.

This **amends [`0040`](./0040-operator-crud-tiering.md)** ("vlastník edits stock"
/ owner-only ordering): branch staff may now correct **and order for their own
branch** via inventura. It **amends [`0065`](./0065-inventura-sidebar-nav.md)**
(inventura nav is no longer vlastník-only; it is own-branch for obsluha). The
cross-branch views, `stock_adjust_edit` (per-product across all branches), and
every other tier gate in 0040 are unchanged.

## Rationale

- **The counter should do the count.** The branch operator is the person at the
  shelf; forcing every correction through the owner is friction with no control
  benefit — the correction is audited (`[STAV]` movement + reason) regardless of
  who saves it.
- **Own-branch scoping is already the operator contract.** Movements, dodáky and
  the Přehled already scope obsluha to their branch; inventura now matches. No
  operator can see or edit another branch.
- **Ordering with it is Petr's call.** He explicitly opted obsluha into the
  objednávka column so a branch can order its own replenishment during the count.

## Consequences

- Obsluha can write `[STAV]` stock corrections and create planned objednávky
  **for their own branch**; both remain audited exactly as for vlastník.
- Cross-branch inventura (`vse` / `dochazi`) and other-branch codes stay
  owner-only (403 for obsluha). The single-branch "Dochází" toggle is available
  to obsluha.
- The nav gate + `branch_dashboard` Inventura button are now visible to obsluha.
- `.claude/rules/design-system.md`'s "Inventura is a nav landing" note and
  `context/screens/03` / the inventura screen doc are updated to match.
- No schema change, no migration.
