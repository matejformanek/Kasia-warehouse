# 0030 — Výdej with default odběratel Říčany (supersedes 0004)

## Context

Petr's 2026-06-09 reply (Czech, relayed via Matej):

> "Defaultně bude nastaven jako příjemce Říčany, lištu převod můžeme
> úplně vynechat."

[`0004-ricany-transfer-model.md`](./0004-ricany-transfer-model.md)
landed *first-class převod* as a distinct movement type with its own
screen (12), the rationale being "převod do Říčan" reads
distinctly from "výdej" in the history and reports. Petr's reply
collapses that distinction: as far as he is concerned, sending stock
to Říčany is just a výdej where the appropriate odběratel happens to
be Říčany. The UI surface for převod (the mode toggle on screen 07,
the dedicated screen 12) is removed.

This decision supersedes
[`0004`](./0004-ricany-transfer-model.md) in its **UI distinctness**
and **schema split**. The internal-vs-external nature of a goods
issue lives on the **odběratel record** (Říčany is an internal
customer), not on the movement type.

## Options considered

- **(a) Keep first-class převod** per
  [`0004`](./0004-ricany-transfer-model.md). Two movement kinds
  (`vydej`, `prevod`), two screens, mode toggle. Contradicts Petr's
  "lištu převod můžeme úplně vynechat".
- **(b) One movement kind (výdej) for all goods-out.** The customer
  picker on screen 07 carries a default = Říčany. The "Říčany"
  customer is a seeded `Customer` row, flagged internal, treated like
  any other odběratel by the schema. Other customers chosen explicitly
  override the default.
- **(c) Model Říčany as a Branch row** (like Týniště and Sezimovo
  Ústí), with the výdej picker accepting either a Branch or a
  Customer. Rejected because
  [`warehouses.md`](../warehouses.md) is explicit that Říčany **does
  not hold tracked stock** — making it a Branch would re-open that
  decision.

## Choice

**(b) One movement kind, default odběratel = Říčany.**

- Single movement kind for goods-out: `výdej`. No `prevod` enum
  value.
- `Customer` model gains a seeded row **`Říčany`** (the canonical
  internal odběratel). It is just a row; the `Customer` model itself
  has no `is_internal` flag in MVP (a future flag is reachable
  without migration if Petr ever needs to distinguish internal vs
  external customers programmatically).
- Screen 07's customer picker is pre-filled with the Říčany row by
  default; the operator overrides by picking another customer.
- Screen 12 (the dedicated *Převod do Říčan* screen) and the mode
  toggle at the top of screen 07 are both removed.
- Říčany is **not** a `Branch` row; per
  [`warehouses.md`](../warehouses.md) it does not hold tracked stock.
  There is no paired inbound on a výdej to Říčany.
- The dodací list / e-mail logic still runs on every výdej, including
  výdej to Říčany. Per
  [`0031-emails-internal-only-supersedes-0009.md`](./0031-emails-internal-only-supersedes-0009.md)
  recipients are the fixed Petr+Karolína pair from Nastavení, so a
  Říčany výdej emails the dodák to Petr+Karolína just like any other
  výdej — internally consistent.

## Rationale

- **Petr's instruction is unambiguous** ("lištu převod můžeme úplně
  vynechat"). The mental model is "every goods-out is a výdej; some
  go to Říčany, some go to customers".
- **One enum value beats two for ~6 users.** The audit-clarity
  argument in [`0004`](./0004-ricany-transfer-model.md) (převod reads
  at a glance) is real but small: Říčany shows in the *odběratel*
  column on screen 10 instead of in the *type* column. Same
  information, one fewer surface.
- **Schema growth is straightforward.** If branch ↔ branch transfers
  ever land (still tabled per [`open-questions.md`](../open-questions.md)),
  they can be modelled as a paired výdej-příjem or as a new kind at
  that point; this decision doesn't pre-commit either way.
- **(c) was tempting** because it would unify "goods-out destinations"
  but it re-opens the explicit "don't track Říčany" decision, which
  Petr's reply doesn't touch. Keeping Říčany as a Customer row
  preserves that.
- **The dodací list on a Říčany výdej is harmless.** With
  [`0031`](./0031-emails-internal-only-supersedes-0009.md) recipients
  fixed to Petr+Karolína, the email is internal anyway. Petr seeing
  a PDF of his own internal transfer is operationally fine and may
  even be useful as a paper record.

## Date & by-whom

2026-06-09 — Petr (via Matej).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Movement schema: enum `kind ∈ {prijem, vydej}` (plus future `oprava`
  / write-off / mixing kinds if/when those decisions land). No
  `prevod` value.
- `Customer` table is seeded with a `Říčany` row at first migration.
- Screen 07 customer picker defaults to Říčany; switching customers
  is one click. The "Odběratel / Převod do Říčan" mode toggle is
  removed.
- Screen 12 is deleted.
- Screens 03's quick-action "Převod do Říčan" becomes a normal "Nový
  výdej" — the operator lands on screen 07 with the Říčany default
  already selected. (Or just keeps "Nový výdej"; the quick-action is
  redundant.)
- Screen 10's filter on "type" drops the `převod` value; the way to
  see internal flows is to filter by `odběratel = Říčany`.

**Forecloses (without follow-on decisions):**

- A distinct `prevod` movement kind. Anything that wanted to
  semantically distinguish internal transfers from external sales
  on the movement record itself now needs a fresh decision.
- The "no dodací list on převod" optimisation from
  [`0004`](./0004-ricany-transfer-model.md). Every výdej, including
  to Říčany, generates a dodací list and an internal email (per
  [`0031`](./0031-emails-internal-only-supersedes-0009.md)).

**Supersedes:**

- [`0004-ricany-transfer-model.md`](./0004-ricany-transfer-model.md)
  in its **UI distinctness** and **movement-kind split**. The
  underlying "Říčany is destination-only, not a tracked location"
  rule from
  [`warehouses.md`](../warehouses.md) is preserved.

**Resolves:**

- The "Říčany transfer" entry in
  [`open-questions.md`](../open-questions.md), reopened by Petr's
  brief. Now closed by being folded into výdej.

**Affects future decisions:**

- Branch ↔ branch transfers (still tabled in
  [`open-questions.md`](../open-questions.md)) — if they ever
  materialise, the natural fit is a new `prevod` kind *then*, when
  the case is concrete. Not now.
