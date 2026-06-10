# 0009 — Dodací list e-mail recipients

> **Superseded 2026-06-09 by [`0031-emails-internal-only-supersedes-0009.md`](./0031-emails-internal-only-supersedes-0009.md).**

## Context

[`../owner-request.md`](../owner-request.md) names the e-mail send as
the load-bearing automation:

> "z toho výdeje rovnou vypadl dodací list jako PDF, který by se mi
> automaticky poslal mailem, mně i Karolíně. Ona to potom posílá dál
> účetní. Bez toho mailu to nemá smysl."

The minimum is Petr + Karolína on every dodací list. Open in
[`../open-questions.md`](../open-questions.md) is whether the
operator can add the customer at issue time, and whether that should
persist per-customer.

[`decisions/0007-auto-reissue-corrected-dodaky.md`](./0007-auto-reissue-corrected-dodaky.md)
already establishes that corrections re-send to the **original
recipients of the prior send**; this decision determines what that
set is for the *initial* send.

## Options considered

- **(a) Fixed default + ad-hoc per issue.** Petr + Karolína always
  included. The operator can add ad-hoc recipients (typically the
  customer) per issue. Ad-hoc additions are not remembered.
- **(b) Per-customer remembered list + fixed default + ad-hoc.** The
  odběratel record carries an optional "vždy posílat na" e-mail list.
  When an odběratel with a remembered list is picked at issue, those
  addresses are pre-filled alongside Petr + Karolína. Operator can
  still add ad-hoc.
- **(c) Fully configurable per issue, no default.** Operator types the
  recipient list on every dodák. Petr + Karolína not auto-included.

## Choice

**(b) Per-customer remembered list + fixed default + ad-hoc.** The
recipient set on every dodací list is the union of:

1. **Fixed default** — Petr's e-mail and Karolína's e-mail. Stored on
   `screens/14-nastaveni.md`; cannot be empty.
2. **Per-customer remembered list** — an optional `default_recipients`
   string list on the odběratel record. When set, every dodací list
   for that customer auto-includes these addresses. Configurable on
   the odběratel record (which lives inline in the customer picker on
   `screens/07-vydej-zbozi.md` until/if a standalone customer screen
   ships).
3. **Per-issue ad-hoc** — the operator may add one or more e-mail
   addresses at issue time on `screens/07-vydej-zbozi.md`. Ad-hoc
   additions to an unsaved výdej are not persisted to the customer
   record automatically; the operator must explicitly tick "uložit
   jako stálého příjemce pro tohoto odběratele" to promote ad-hoc to
   remembered.

The full set is recorded on the dodací list as the actual recipients
of the initial send. Corrections (per
[`decisions/0007`](./0007-auto-reissue-corrected-dodaky.md)) re-send
to whatever set went out last.

## Rationale

- **Fixed default is non-negotiable.** Brief explicitly names Petr +
  Karolína as the chain. Removing them from a dodák is a foot-gun.
- **Per-customer remembered list closes a real friction.** Many
  customers will want their copy of every dodák. Asking the operator
  to type the address every time is exactly the kind of manual step
  the brief names as the failure mode of today's workflow ("polovina
  dodáků se zapomene přeposlat"). Remembering the address against the
  odběratel removes that step entirely for repeat customers.
- **Ad-hoc remains useful** for one-off scenarios: a different
  contact at the customer, the customer's accountant, etc.
- **Explicit promotion to remembered** prevents accidental persistence
  — if a branch staffer typos an address once, that typo doesn't haunt
  every future dodák for that customer.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `screens/07-vydej-zbozi.md` — the recipients block shows the union
  of (default, per-customer remembered, ad-hoc); the operator can add
  ad-hoc and tick "uložit pro tohoto odběratele" to promote.
- `screens/09-detail-dodaciho-listu.md` — the e-mail status block
  shows the actual recipient set per send. Ad-hoc additions on the
  *re-send* path remain available.
- `screens/14-nastaveni.md` — the fixed default (Petr's e-mail,
  Karolína's e-mail) is a settings field. Editing it requires owner /
  Karolína permission.
- Odběratel schema gains a `default_recipients` (e-mail list) column.
- Audit on the dodací list captures the recipient set on each send
  per [`decisions/0007`](./0007-auto-reissue-corrected-dodaky.md).

**Forecloses (without follow-on decisions):**

- Removing Petr or Karolína from the default. The system does not
  expose a "send without Karolína" toggle. If she goes on holiday,
  she catches up on inbox; if she is replaced, the default is updated
  on `screens/14-nastaveni.md`.
- Per-branch defaults (e.g. "TYN dodáky also go to TYN branch
  manager"). Not in MVP; can be added later by extending the default
  list per branch.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  MVP* › "Email recipients — configurable per dodací list or global".

**Affects future decisions:**

- A standalone customer-management screen (currently folded into 07
  per `screens/README.md`) would inherit the `default_recipients`
  field naturally.
- GDPR / data-retention policy on stored e-mail addresses — out of
  scope for this decision; the addresses are Kasia's business data
  and are not customer PII in the sensitive sense, but a future
  retention policy lives in the operational handover decision tier.
