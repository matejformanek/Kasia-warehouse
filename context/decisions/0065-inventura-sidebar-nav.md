# 0065 — Inventura as a sidebar-nav landing (IA change)

**Date:** 2026-07-03
**Decider:** Matej (sklad UX-refresh Phase 2 replace)
**Status:** Active
**Relates to:**
- [`0054-adopt-ui-directions.md`](./0054-adopt-ui-directions.md) +
  [`.claude/rules/design-system.md`](../../.claude/rules/design-system.md) —
  the sklad sidebar is the locked shell; adding a nav item is an IA change.
- [`0060-michani-immediate-only.md`](./0060-michani-immediate-only.md) — the
  inventura `?products=`/`next=` contract (unchanged).

## Context

Before this change, Inventura (hromadná úprava stavu skladu) had no top-level
nav entry — it was only reachable from the Katalog "Inventura" button and the
Přehled/low-stock jumps. The locked mockups (`01b`, `02a`, `03`, …) all show an
**Inventura** item in the sidebar's Provoz group, right under Katalog. Adding it
makes the most-used stock-correction workflow directly reachable.

## Options considered

- **New chooser view** ("which branch?") behind the nav item. Rejected — an
  extra click and a new view for something the existing per-branch /
  all-branch inventura already covers.
- **Nav item with a conditional href, reusing the existing views.** Chosen.

## Choice

- Add an **Inventura** item to the sklad sidebar + mobile nav, in the Provoz
  group under Katalog.
- **Vlastník-only** — `inventura_edit` is gated by `_require_vlastnik`, so the
  item renders only for a vlastník (obsluha never sees it, matching the view).
- **Conditional href, no new view:** it points at the user's own branch
  (`inventura_edit code=<user.branch.code>`) when the user has an assigned
  branch, otherwise at the all-branch **"Vše"** inventura
  (`inventura_edit code='vse'`). In practice the vlastník has no branch FK, so
  it lands on "Vše" — the same all-branch mode the Katalog button already uses.
- The item is **not** required by any earlier swap step; Přehled's per-branch
  Inventura buttons keep using the per-branch URL.

## Rationale

Reusing the existing per-branch + "Vše" inventura modes (no chooser) is the
smallest change that satisfies the locked mockups' IA. The href logic lives
entirely in `base.html`; no view, URL, or permission changes.

## Consequences

- `base.html` gains one nav entry (desktop + mobile), gated `user.is_vlastnik`.
  It joins the locked sidebar shell; removing/renaming it is a nav-IA change.
- No new view, URL, model, or migration. `inventura_edit`'s permission and the
  0060 `?products=`/`next=` contract are untouched.
