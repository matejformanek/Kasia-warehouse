# 0040 — Operator-facing CRUD + role tiering

**Date:** 2026-06-12
**Decider:** Matej (relaying Petr / Karolína operational reality)
**Status:** Active

## Context

Up to and including Pass 4, the only way to create / edit a Branch,
Product, Supplier, Customer, or Recipe was via `/admin/` (Django
admin). Settings (screen 14) and User accounts (screen 13) already
have operator-facing UIs.

Matej's 2026-06-12 walkthrough feedback was unambiguous: Karolína
and Petr — and where reasonable the branch staff — **must be able to
do these operations from the Czech operator app, not `/admin/`**.
Workers add suppliers / customers in the moment they meet them; an
admin redirect breaks the flow.

A follow-up message emphasised:
> Per-user permissions — not all users will have all options.

The existing role model is two-tier (`vlastnik` group + the implicit
"obsluha" group; `accounts.User.is_vlastnik` / `is_obsluha`). This
decision spells out how operator-facing CRUD slots into that model
and where it leaves room for a third tier.

## Options considered

1. **Single tier — everyone can edit everything.**
   Simple. Rejected: Karolína explicitly does not want sezónní
   výpomoc adding branches or changing recipes.
2. **Hard two-tier — every CRUD is either vlastník-only or
   everyone.**
   Manageable. Rejected: adding a new supplier in the middle of a
   příjem is operationally a worker task; gating it to vlastník
   means workers wait for Karolína. Bad UX.
3. **Two-tier per entity** — each entity has its own gating
   (vlastník vs all), chosen by operational sensitivity. **Chosen.**
4. **Per-user fine-grained permissions** (Django's
   `Permission` system + custom permissions).
   Powerful but over-engineered for 6 active users. Deferred — the
   two-tier-per-entity model can be retrofitted to per-permission
   later without breaking the URL/view layout.

## Choice

**Two-tier-per-entity gating.** Each operator-facing CRUD endpoint
declares whether it's `all_authenticated` or `vlastnik_only`. The
gate is a small decorator / helper, not a separate Django group, so
adding a third tier later (e.g. `obsluha_senior`) is a one-line
change in the helper.

### Tiering matrix (MVP)

| Entity | View / list | Create | Edit | Archive (soft-delete) | Notes |
|---|---|---|---|---|---|
| **Supplier** | all | all | all | all | Workers add when receiving from new dodavatel |
| **Customer** | all | all | all | all | Workers add when issuing to new odběratel; the `is_default_recipient` flag is vlastník-only (single-row constraint) |
| **Product (surovina / směs)** | all | all | all | **vlastník** | Workers can suggest a new produkt; archiving has stock implications, vlastník-only |
| **Recipe (`RecipeComponent`)** | all | **vlastník** | **vlastník** | **vlastník** | Domain-knowledge ownership stays with Petr |
| **Branch** | all | **vlastník** | **vlastník** (name+address) | **vlastník** | Branch `code` is locked after first dodák per [0008](./0008-dodaci-list-numbering.md); only renamable until then |
| **Stock direct edit** | n/a (read-only) | n/a | **vlastník** | n/a | Per [0041](./0041-manual-stock-adjustment.md) — writes a "ruční úprava" Movement, not raw UPDATE |
| **User account** | **vlastník** | **vlastník** | **vlastník** | **vlastník** | Already gated by screen 13 |
| **Settings** | **vlastník** | n/a (singleton) | **vlastník** | n/a | Already gated by screen 14 |

### How "all" maps onto code

`all_authenticated` = any logged-in user. Obsluha is *not* a
"reduced vlastník" — for the entities flagged `all`, obsluha has
**full** create/edit/archive rights for the entity itself.
Branch-scoped data restriction (obsluha sees only own-branch stock,
own-branch movements) is independent of the entity CRUD gate.

### How "vlastník-only" maps onto code

`vlastnik_only` = `request.user.is_vlastnik`. The helper raises
`PermissionDenied` (= 403) early. Templates also gate nav links /
buttons with `{% if user.is_vlastnik %}` so the affordance is not
even shown to obsluha — preventing the "click → 403" footgun.

### Branch-staff archiving Supplier / Customer

Archiving is `is_active = False`, not a DELETE. Workers can do it
because:
- Bad-data correction is operationally a worker job ("Hospůdka U
  Lípy už neexistuje").
- The Movement audit trail FKs onto Customer.pk anyway, so an
  archived customer keeps showing on historical výdejky.
- Re-activation is also `all` — symmetric.

The `is_default_recipient` flag on Customer (single Říčany row per
[0030](./0030-vydej-default-ricany-supersedes-0004.md)) stays
**vlastník-only**. Workers can't change which customer is the
default.

## Rationale

- **Matches operational reality.** Workers shouldn't wait for
  Karolína to add a customer.
- **Protects domain knowledge.** Recipes and branch identities stay
  with Petr/Karolína — these are decisions, not facts to record.
- **Keeps Stock writes auditable.** Direct UPDATE on `Stock` would
  bypass `MovementAudit`. Per [0041](./0041-manual-stock-adjustment.md),
  every change to `Stock.quantity` goes through a Movement
  (existing flow) including the "ruční úprava" case for vlastník.
- **Two tiers are enough for ~6 users.** The per-entity matrix
  gives almost all the flexibility of permissions without the
  ceremony.
- **Forward-compatible.** A third tier becomes a one-line addition
  to the gate helper + a column on this matrix; URL layout and view
  bodies don't change.

## Consequences

### New code surface (Pass 5)

Six new operator-facing CRUD areas, each = index + create + edit +
archive views + templates + form factories:

1. Supplier — `/dodavatele/` (this commit batch).
2. Customer — `/odberatele/` (this commit batch).
3. Product (+ Recipe inline) — `/katalog/novy/`, `/katalog/<id>/upravit/`.
4. Branch — `/pobocky/` (read), `/pobocky/<code>/upravit/`.
5. Stock direct edit — `/katalog/<id>/upravit-stav/` (per 0041).
6. Recipe — sub-form of Product edit for směsi.

Each respects the tiering matrix above.

### Code-level

A new tiny helper in `accounts/permissions.py`:

```python
def require_vlastnik(request):
    if not request.user.is_vlastnik:
        raise PermissionDenied(...)
```

Already exists in two places (`accounts/views.py:_require_vlastnik`,
`inventory/views.py:_require_vlastnik`); will be promoted to a
single shared helper as part of Pass 5.

### Tests

Every new endpoint ships with tier-coverage tests: anon (302),
obsluha (200 or 403 per matrix), vlastník (200 always).

### Forward references

- [0041](./0041-manual-stock-adjustment.md) — explicit mechanism
  for the "Stock direct edit" row above.
- Future per-permission tiering decision (post-MVP, only if shadow
  run reveals two tiers are insufficient).
