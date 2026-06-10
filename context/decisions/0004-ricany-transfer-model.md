# 0004 — Říčany transfer model: first-class převod

> **Superseded 2026-06-09 by [`0030-vydej-default-ricany-supersedes-0004.md`](./0030-vydej-default-ricany-supersedes-0004.md).**

## Context

When a branch (Týniště, Sez. Ústí) ships stock to Říčany HQ — for
office consumption, samples, or onward dispatch from there —
the system has to record the event. Říčany is **not a tracked
location** ([`../warehouses.md`](../warehouses.md),
[`../owner-request.md`](../owner-request.md): "Říčany bych do toho
zatím netahal, tam zboží dlouho neleží"), so the transfer is
one-sided: stock leaves the branch and is not recorded anywhere as
incoming.

The round-one scaffold drafted `screens/12-prevod-do-rican.md` as a
dedicated screen with a dedicated movement type, but did not record
the data-model commitment. The question was listed in
[`../open-questions.md`](../open-questions.md) and the user
confirmed during this self-review that both customer výdej and
branch-to-Říčany převod are first-class daily flows.

## Options considered

- **(a) First-class převod.** Distinct movement type with destination
  metadata. Decrements branch stock; produces no dodací list, no
  email, no inbound at Říčany. Reports and filters discriminate on
  type, not on a reason string.
- **(b) Internal převodka document.** Additive on top of (a) or (c):
  generate a PDF receipt for the owner's records / for the driver
  to carry to Říčany.
- **(c) Plain výdej with reason = "transfer to Říčany".** No new
  movement type; a reason field on výdej discriminates. Reports and
  emails consult the reason string to know how to behave.

## Choice

**(a) First-class převod.** A převod is its own movement type with
destination metadata (`destination = "Říčany"` in MVP; the schema
permits other destinations if the deferred branch ↔ branch case ever
lands). Saving a převod decrements branch stock and writes one
movement record; there is no matching inbound movement and no
dodací list and no email is sent on save.

**(b) printed převodka PDF — NO in MVP.** The owner sees převody in
`Historie pohybů` and on `Přehled vlastníka`. A printed PDF can be
added later on screen 12 without schema impact. Revisit if Petr asks
for paper at Říčany handover.

## Rationale

- **Customer výdej and Říčany převod are semantically distinct.**
  Customer výdej generates a dodací list and auto-emails it to the
  owner + Karolína (who feeds the accountant); převod does neither.
  Forcing them into one type pushes the distinction into a reason
  string that every report and email path must consult.
- **Audit clarity.** "převod do Říčan" in `Historie pohybů` reads at
  a glance. Under (c), the row reads "výdej" and the reader has to
  open and read the reason field to learn it was internal.
- **Forward path.** If branch ↔ branch transfers ever materialise
  (deferred in [`../open-questions.md`](../open-questions.md)),
  převod extends naturally with `destination = <branch>`. (c) would
  either keep the reason-string forever or migrate to (a) at a
  later, more painful date. The decision-log-discipline preference
  is to pick the option that does not lock out a likely future.
- **Říčany stays untracked.** No matching inbound, no stock figure
  at Říčany. The owner's brief is explicit on this.
- **No email on převod.** Customer výdej feeds the accountant via
  Karolína; internal převody do not. Screen 12 already reflects this.
- **(b) deferred** because the brief does not ask for a printed
  document and the cost of adding one later is local.

## Date & by-whom

2026-06-02 — owner stand-in (acting for Petr), recorded by the
design agent during the round-two self-review.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `screens/12-prevod-do-rican.md` stays as drafted — first-class
  movement type, no PDF, no email, no matching inbound. The screen
  file does not need rewriting under this decision (light edits only,
  to drop the "open" qualifier on the model and to convert the
  "internal převodka PDF" sub-question into a noted future option).
- Movement schema gains a `kind` (or `type`) enum that includes at
  least `příjem`, `výdej`, `převod`. Destination metadata is a
  column on převod rows.
- `screens/10-historie-pohybu.md` filter on movement type can list
  `převod do Říčan` as a first-class option, distinct from `výdej`.
- `screens/02-prehled-vlastnik.md` can show převody and customer
  výdej as separate counts in the daily summary.

**Forecloses (without follow-on decisions):**

- Modelling Říčany as a tracked location. If that ever becomes
  desired, this decision is superseded by a new one that introduces
  a paired inbound movement.
- Storing transfer events as výdej variants. Any future destination
  (branch ↔ branch, supplier-return, etc.) lives on the same
  movement type with appropriate destination metadata, not as a
  výdej-with-reason.

**Resolves:**

- [`../open-questions.md`](../open-questions.md) — *Decide before
  code* › "Říčany transfer — tracked movement or stock-out-and-gone".

**Affects future decisions:**

- Q5 (mixture recipes) — orthogonal.
- Q6 (pack-size granularity) — orthogonal; převod uses the same
  unit-of-measure handling as příjem and výdej.
- Branch ↔ branch transfers
  ([`../open-questions.md`](../open-questions.md) → *Decide later*) —
  becomes a small extension of this decision rather than a new model.
- Inventura workflow ([`../open-questions.md`](../open-questions.md)
  → *Decide before MVP*) — the movement-kind enum should be
  considered when designing reconciliation, in case stock-take
  adjustments also become a first-class kind.
