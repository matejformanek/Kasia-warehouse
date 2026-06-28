# Warehouses (locations)

Kasia vera operates from three physical locations. Only two of them hold
tracked stock in this system.

> **Note (2026-06-28):** the **public marketing site** (`web` app) lists
> **four** provozovny — Říčany (sídlo), Sezimovo Ústí, Toužim, and Týniště
> nad Orlicí — sourced from kasia.cz (decision 0052). That is curated public
> content and is **decoupled** from this operational model: stock is still
> tracked only at TYN + SEZ, and Říčany is still a destination-only
> `Customer`. Toužim is a public-facing location that this warehouse system
> does not track.

## The three locations

### Říčany u Prahy — headquarters (HQ)

Corporate seat. Office, ownership, finance. The owner and Karolína are
based here. Goods occasionally pass through Říčany — a sample for a
buyer, a small quantity for office consumption, a shipment dispatched from
HQ rather than from a branch — but the dwell time is short and the
volumes are small relative to the branches.

**Stock at Říčany is not tracked in this system.** That is a deliberate
choice from the owner's request, not an oversight. Anything that arrives
at Říčany either is consumed quickly or leaves again, and the cost of
maintaining accurate records there is judged to exceed the value of
having them.

This means Říčany functions in the system as a **destination only**:
goods can be sent there but its on-hand quantity is never queried or
reported. Per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)
Říčany is modelled as a **seeded `Customer` row** (the default
odběratel on výdej), **not** as a `Branch` row. There is no separate
"převod" movement type — sending stock to Říčany is just a výdej
with the default-selected odběratel.

### Týniště nad Orlicí — branch warehouse

Operating branch, in the Hradec Králové region. Holds tracked stock.
Approximately two staff. Full operating cycle: **receives goods** from
suppliers (raw spice imports and any other inbound material),
**processes / blends / packs** as needed, **issues goods** to B2B
customers on dodací list, and **transfers** to Říčany when HQ needs
material.

### Sezimovo Ústí — branch warehouse

Operating branch, in the Tábor region (South Bohemia). Holds tracked
stock. Approximately two staff. Identical role to Týniště.

The two branches are operationally symmetric. Nothing in the design should
privilege one over the other.

## Physical flow of goods

The typical lifecycle of a unit of spice from the system's point of view:

1. **Inbound.** Raw spice (or other purchased material) arrives at one of
   the two branches from a supplier. Branch staff record a **příjem**:
   stock at that branch goes up.
2. **Processing, blending, packing.** Inside the branch, raw material may
   be cleaned, ground, blended into a mixture, and packed into one or
   more sale formats. The catalogue treats this as **product + variants**
   per [`decisions/0006-pack-size-product-variant.md`](./decisions/0006-pack-size-product-variant.md):
   one product per ingredient (or mixture), N variants per pack format,
   with stock attached to each variant. Mixing of a směs from raw spices
   per a recorded recipe is a future workflow per
   [`decisions/0005-mixture-recipe-model.md`](./decisions/0005-mixture-recipe-model.md)
   (the data model is settled; the screen ships later).
3. **Outbound to customer.** Finished goods are issued to a B2B reseller
   on **výdej**. The system generates a dodací list PDF and emails it
   to the owner and Karolína. Stock at the branch goes down.
4. **Outbound to Říčany.** When the owner needs material at HQ — for
   office consumption, samples, or to dispatch from there — the branch
   records an issue with destination = Říčany. Stock at the branch goes
   down. The goods leave the tracked system: there is no corresponding
   "příjem at Říčany" on the other side, because Říčany does not hold
   tracked stock.

## Branch → Říčany transfer, modelled

In system terms, a transfer to Říčany is a **výdej with default
odběratel = Říčany** per
[`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md).
There is no paired inbound movement and no Říčany on-hand figure.
A dodací list **is** generated and the internal Petr+Karolína
e-mail per
[`decisions/0031-emails-internal-only-supersedes-0009.md`](./decisions/0031-emails-internal-only-supersedes-0009.md)
**does** fire — internally consistent with every other výdej. The
goods then exit the system's worldview at Říčany.

The reason for spelling this out: an instinct from generic WMS designs
would be to model every transfer as a paired (out, in) and to track
on-hand at every named location. Kasia's owner has explicitly chosen
not to do that for Říčany. Respect that.

## Branch codes

Per [`decisions/0008-dodaci-list-numbering.md`](./decisions/0008-dodaci-list-numbering.md),
each branch has a stable three-letter code used in dodací list
numbering and elsewhere:

- **Týniště nad Orlicí** — `TYN`
- **Sezimovo Ústí** — `SEZ`

Codes are set at first install on `screens/14-nastaveni.md` and cannot
be changed after the first dodací list is issued from that branch.

## Open: branch ↔ branch transfers

It is not yet established whether goods ever move directly between
Týniště and Sezimovo Ústí — and if so, whether the system should model
that as a paired (out, in) movement (since both ends hold tracked stock),
or whether it should be handled as an issue from one and a separate
receipt at the other. This is parked in [`open-questions.md`](./open-questions.md).
