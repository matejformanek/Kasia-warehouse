# 0031 — Dodací list e-mails internal only (supersedes 0009)

> **Superseded in part 2026-06-28 by [`0052-n-list-recipients-supersedes-0031.md`](./0052-n-list-recipients-supersedes-0031.md)** — the "fixed pair `[Petr, Karolína]`" shape under § Choice is replaced by an operator-managed N-list; the "internal only / never to customers" intent stands.

## Context

Petr's 2026-06-09 reply (Czech, relayed via Matej):

> "I dodací listy na jiné odběratele ať odchází pouze na náš email,
> ne koncovým zákazníkům."

[`0009-dodaci-list-email-recipients.md`](./0009-dodaci-list-email-recipients.md)
landed a union model: fixed default (Petr + Karolína) + per-customer
remembered list on the `Customer` record + ad-hoc per-issue additions
promotable to remembered via a checkbox. The reasoning was that
many customers would want a copy of every dodák and asking the
operator to type the address every time would reproduce the manual
step the brief named as the failure mode.

Petr's reply removes that assumption. He wants every dodák — *even
on výdej to other customers* — sent only to himself and Karolína. The
customer receives the dodák through the existing channel (Karolína
forwarding to the účetní; the účetní handling whatever the customer
needs), not through the system's auto-send.

This decision supersedes
[`0009`](./0009-dodaci-list-email-recipients.md).

## Options considered

- **(a) Keep the union model** per
  [`0009`](./0009-dodaci-list-email-recipients.md). Contradicts Petr.
- **(b) Fixed pair, hardcoded from Nastavení.** Every dodák send
  goes to exactly `[Petr, Karolína]` from
  [`screens/14-nastaveni.md`](../screens/14-nastaveni.md). No
  per-customer remembered list; no ad-hoc additions on issue; no
  ad-hoc additions on re-send.
- **(c) Fixed pair plus the customer's email if set on the Customer
  record.** Tempting middle ground — operator records the customer's
  email "for our records", but the send code still bccs Petr +
  Karolína only. Rejected because it muddles the wire: a `Customer.email`
  field exists in many ERPs for contact-management purposes (Karolína
  may want a phone-or-email column) without being a send target.
  Better to keep the field for contact use and have the dodák-send
  code ignore it.

## Choice

**(b) Fixed pair from Nastavení; ignore `Customer.email`.**

- The dodák send code reads exactly two addresses from
  [`screens/14-nastaveni.md`](../screens/14-nastaveni.md) (`Petr's
  e-mail`, `Karolína's e-mail`) and sends to that pair on every
  dodák — initial send and `[OPRAVA]` re-send per
  [`0007-auto-reissue-corrected-dodaky.md`](./0007-auto-reissue-corrected-dodaky.md).
- **`Customer.email` field exists** on the `Customer` model for
  contact-record purposes (Karolína may want an email column on a
  customer for her own reference). The dodák-send code **never
  reads** it. There is no UI affordance on screen 07 or screen 09 to
  add ad-hoc recipients or to promote the customer's address to a
  remembered list.
- The `Customer` model **does not** carry a `default_recipients`
  list — that column from
  [`0009`](./0009-dodaci-list-email-recipients.md)'s schema is not
  added.

The fixed pair on screen 14 still cannot be empty (the system must
always send to at least one address per
[`workflows.md`](../workflows.md) — "Bez toho mailu to nemá smysl").

## Rationale

- **Petr's instruction is unambiguous** ("pouze na náš email, ne
  koncovým zákazníkům").
- **Matches the operation today.** Per
  [`workflows.md`](../workflows.md) the chain is dodák → Petr +
  Karolína → účetní → faktura → customer. The customer does not
  routinely need the dodák email — they need the goods and the
  faktura. The previous design's per-customer remembered list was
  speculative; Petr's reply confirms it shouldn't be built.
- **Cheapest implementation.** The send code reads two settings
  values and ships. No customer-record schema, no ad-hoc UI on
  screens 07 / 09, no promotion checkbox.
- **`Customer.email` retained** for contact-record use. A future
  decision can opt to bcc the customer without schema migration —
  just flip the send code to also read `Customer.email`. Reversible.
- **(a) was operationally heavier** (UI on three screens for an
  ad-hoc-and-promotion model Petr does not want) and is now
  superseded.
- **(c) was tempting** but introduces a "field exists but is not used
  for the obvious purpose" gotcha. Cleaner to either send to the
  customer or not; (b) picks "not" per Petr's instruction.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The dodák send code: two settings reads, one SMTP send. No
  customer-record lookup, no ad-hoc-list union.
- Screen 07's recipients block becomes a read-only display of the
  Petr+Karolína pair — no "Přidat příjemce", no "uložit pro tohoto
  odběratele" checkbox.
- Screen 09's e-mail status block displays the fixed pair and offers
  "Znovu odeslat" (re-sends to the same pair). The "Přidat příjemce
  a odeslat" ad-hoc action is removed.
- Screen 14's e-mail recipients section becomes simple: two address
  fields (Petr, Karolína), both required, no per-customer remembered
  tab.
- `Customer` schema: a `name`, `IČO`, `DIČ`, `address` block plus an
  optional `email` (and possibly `phone`) for contact-record use.
  **No `default_recipients` column.**

**Forecloses (without follow-on decisions):**

- Per-customer remembered recipients on dodáky.
- Ad-hoc per-issue or per-re-send recipients.
- Sending the dodák to the customer automatically. If Petr ever asks
  for this, a future decision either (i) adds a "bcc customer" toggle
  reading `Customer.email`, or (ii) re-introduces the per-customer
  remembered list. Either is a small schema-light change.

**Supersedes:**

- [`0009-dodaci-list-email-recipients.md`](./0009-dodaci-list-email-recipients.md).
  The `Customer.default_recipients` schema column from
  [`0009`](./0009-dodaci-list-email-recipients.md) is **not** added
  to the next models pass.

**Resolves:**

- The "Email recipients" entry in
  [`open-questions.md`](../open-questions.md), now simplified.

**Affects future decisions:**

- [`0007-auto-reissue-corrected-dodaky.md`](./0007-auto-reissue-corrected-dodaky.md)
  is simplified by this: the "re-send to original recipients" rule
  collapses to "re-send to the fixed pair", because the original
  recipients are always the fixed pair. No recipient-union to
  recompute per send.
