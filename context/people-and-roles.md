# People and roles

Who uses the system, and what they can do. Roles are deliberately few —
this is a small business and the owner is allergic to ceremony.

## The humans

### Petr — owner

Owner of Kasia vera s.r.o. Has **full access** across both branches. Sees all
movements, all stock, all dodací listy, all audit-trail entries. Receives
every dodací list email automatically. Treats the system as the authoritative
record of stock but explicitly reserves the right to **correct any historical
entry** (with audit trail) — see the correction workflow in
[`workflows.md`](./workflows.md). Likely the heaviest reader, lightest writer.

### Karolína — co-admin

Owner-equivalent in the system. **Full access**, identical scope to Petr.
Receives every dodací list email — she is the link to the external accountant
and forwards dodáky onward. The owner's instruction is explicit: do not
introduce a finer permission than "same as me" for her. She is the second
trusted pair of eyes on everything.

### Týniště nad Orlicí branch staff — approximately 2 people

Scoped to the Týniště branch. Can:

- Receive goods (příjem) into Týniště stock.
- Issue goods (výdej) from Týniště stock, triggering generation of a
  dodací list and the outbound email.
- View Týniště stock and Týniště movement history.

Cannot see Sezimovo Ústí stock or movements. Cannot edit historical entries
(that is owner / Karolína only).

### Sezimovo Ústí branch staff — approximately 2 people

Same as Týniště, scoped to Sezimovo Ústí.

### Říčany HQ staff

The owner and office staff are physically at Říčany, but **Říčany does not
hold tracked stock** (see [`warehouses.md`](./warehouses.md)). Office staff
who need system access get it through the owner / co-admin roles above;
there is no dedicated "Říčany operator" role.

## Capacity

- **Total user accounts:** budget for around **20**, to leave room for
  turnover and short-term help.
- **Active at any one time:** roughly **6** (owner, Karolína, ~2 per branch).

This is the scale to design for. Anything that assumes hundreds of
concurrent users or a complex role tree is over-engineered.

## Permissions matrix

| Capability                                | Petr | Karolína | Týniště staff | Sez. Ústí staff |
|-------------------------------------------|:-----:|:--------:|:-------------:|:---------------:|
| See Týniště stock & movements             |   x   |    x     |       x       |                 |
| See Sezimovo Ústí stock & movements       |   x   |    x     |               |        x        |
| Record příjem (goods in) at own branch    |   x   |    x     |       x       |        x        |
| Record výdej (goods out) at own branch    |   x   |    x     |       x       |        x        |
| Trigger dodací list PDF + email           |   x   |    x     |       x       |        x        |
| Receive dodací list email automatically   |   x   |    x     |               |                 |
| Initiate transfer to Říčany (own branch)  |   x   |    x     |       x       |        x        |
| Edit historical movement (with audit)     |   x   |    x     |               |                 |
| Manage catalogue (spices, products, mixes)|   x   |    x     |               |                 |
| Manage users                              |   x   |    x     |               |                 |
| View audit trail                          |   x   |    x     |               |                 |

Notes:

- "Own branch" means the branch the user is scoped to. A Týniště user
  cannot record movements for Sezimovo Ústí and vice versa.
- The dodací list **email recipients** are exactly Petr and
  Karolína (read from
  [`screens/14-nastaveni.md`](./screens/14-nastaveni.md)) per
  [`decisions/0031-emails-internal-only-supersedes-0009.md`](./decisions/0031-emails-internal-only-supersedes-0009.md).
  Never per-customer remembered, never ad-hoc per-issue additions,
  never the customer themselves — Petr's 2026-06-09 brief: "i
  dodací listy na jiné odběratele ať odchází pouze na náš email,
  ne koncovým zákazníkům." Neither e-mail address may be empty.
- Whether branch staff can view (read-only) their **own historical**
  entries before they were corrected is an open detail; the current
  default assumption is yes for transparency — they see the *current*
  values plus the "editováno" marker, but the diff against original
  values is owner / Karolína only.
