# 0085 — Příjem defaults to a seeded „Neuveden" supplier

**Date:** 2026-07-21
**Decider:** Matej (2026-07-21, live-app review — obsluha couldn't save a příjem)
**Status:** Accepted
**Relates to:**
- [`0057-planned-order-supplier.md`](./0057-planned-order-supplier.md) +
  migration `0015_seed_order_supplier.py` — the internal-placeholder-supplier
  pattern this mirrors.
- [`0059-merge-objednavka-into-prijem.md`](./0059-merge-objednavka-into-prijem.md)
  — the planned-vs-DONE příjem split whose DONE branch this unblocks.

## Context

Logged in as an **obsluha** (branch staff), the owner found that a plain příjem
would silently refuse to save: the *Dodavatel* field is effectively required
(`Movement.clean()` + the DB `movement_counterparty_matches_kind` constraint
both demand a supplier on a DONE PRIJEM), yet the form field had no `*` marker
and no default, so the validation error („Příjem musí mít dodavatele.") was
nearly impossible to find. This is not a merge regression — příjem has always
required a supplier at the form/model/DB layers. Výdej only „works" out of the
box because its *odběratel* is pre-filled with the default recipient.

The real workflow rarely has a meaningful supplier at receive time (goods just
arrive), so forcing the operator to pick one — or create one — is friction that
blocks the primary action.

## Options considered

- **Relax the DB constraint** to allow a null supplier on DONE PRIJEM. Rejected:
  a schema/constraint change for a UX default is heavy, and it weakens an
  invariant that is otherwise sound.
- **Auto-pick the first real supplier.** Rejected: silently attributes goods to
  an arbitrary vendor.
- **Seed an internal „Neuveden" placeholder supplier and default to it.**
  Chosen — mirrors the existing „Objednávka" / „Míchárna" / „Inventura"
  internal-counterparty pattern exactly.

## Choice

Seed an internal **„Neuveden"** Supplier (`is_internal=True`, migration
`0024_seed_neuveden_supplier.py`, mirroring `0015`). The příjem supplier picker
(`PrijemForm.dodavatel` / `PrijemEditForm.dodavatel`) shows **only real
suppliers** (`is_active=True, is_internal=False`) with **„— Neuveden —"** as the
pre-selected blank option; the field stays `required=False`. A blank submit is
resolved server-side to the seeded „Neuveden" row, which satisfies
`Movement.clean()` and the `movement_counterparty_matches_kind` DB constraint
with **no schema/constraint change**. The `elif not cleaned.get("dodavatel")`
guard in `PrijemForm.clean()` is removed (blank is now legal = Neuveden).

## Rationale

Right-sized: one seed row + a queryset filter + a server-side fallback unblocks
the operator's primary action without touching the schema or weakening the
constraint. Filtering internal placeholders out of the picker (a side benefit)
also stops Míchárna/Inventura/Objednávka from ever appearing as pickable
suppliers on the příjem form.

## Consequences — things this now blocks or unblocks

- **Unblocks:** an obsluha (or anyone) can save a příjem out of the box; the
  saved movement's `dodavatel.name == "Neuveden"` when none was picked.
- **Commits us to:** the „Neuveden" internal row existing in every environment
  (seeded by migration; re-seeded in `conftest.py` for `transaction=True`
  tests). Like the other internal placeholders it is `is_internal=True`, so it
  never appears in the picker and never triggers a dodák/e-mail (PRIJEM never
  does anyway).
- **No** DB constraint or schema change.
