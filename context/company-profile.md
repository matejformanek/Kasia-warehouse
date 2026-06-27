# Kasia vera s.r.o. — company profile

Background on the customer. The point of this file is to make sure every
later design choice is grounded in what the business actually is, rather
than in a generic "warehouse for a small B2B" caricature.

## Identity

- **Legal name:** Kasia vera s.r.o.
- **IČO:** 25756729
- **Headquarters:** Říčany u Prahy (Central Bohemia)
- **Founded:** 1993
- **Headcount:** approximately 25–49 employees
- **Brand:** VERA GURMET (the customer-facing retail brand on packaged goods)

For source provenance see [`research-sources.md`](./research-sources.md).

## What they sell

- Approximately **369 spice varieties** in the raw / single-ingredient
  catalogue (whole, ground, cleaned, sorted).
- Approximately **236 finished products** under the VERA GURMET brand —
  branded retail/foodservice SKUs which include both single-ingredient
  packs and house mixtures (e.g. *Zlaté Kuře*).
- Distribution is **B2B via resellers**: wholesalers, gastro suppliers,
  retail chains buying for their own shelves. There is **no e-shop** and
  no direct-to-consumer channel of any operational weight.
- Market is the **Czech Republic**; export, if any, is not in scope for the
  warehouse system.

## What they actually do day-to-day

Kasia vera is an **importer, processor, blender, and packer**. Whole spices
arrive from origin countries (typically by sea container into a European
port, then by truck to the Czech Republic). At a branch the raw material is
**cleaned, sorted, ground or otherwise processed** as needed, **blended
into proprietary mixtures** when the recipe calls for it, and **packed**
into a range of formats — from 25 kg bulk gastro sacks down to retail jars
of around 100 g, with intermediate sizes (1 kg, 5 kg, …) for the foodservice
trade. Finished goods are then **issued to resellers** on dodací list,
which is what the warehouse tool exists to record.

The two operating branches — Týniště nad Orlicí and Sezimovo Ústí — each
handle the full cycle of receive → process / blend / pack → issue. Říčany
is the corporate seat: ownership, office, finance. Raw goods occasionally
transit through Říčany but do not stay long enough to make stock tracking
there worth its cost.

## Scale signal for the system

A company of this size, with ~369 raw spices, ~236 finished SKUs, two
operating warehouses, and ~6 expected active users on the system at any
time, is firmly in the **small-business** scale band. The design should
optimise for clarity and lightness over throughput, scalability, or
elaborate role hierarchies. See [`people-and-roles.md`](./people-and-roles.md)
for the user picture.

## How customers reach Kasia

B2B partners find and contact Kasia through its public web presence and
the phone/e-mail on it (there is no e-shop). The dated kasia.cz is being
replaced by a modern public marketing site hosted on the same domain as
the warehouse tool — public site at `/`, warehouse app under `/sklad/`.
See [`public-site.md`](./public-site.md) and
[`decisions/0050-public-site-and-sklad-split.md`](./decisions/0050-public-site-and-sklad-split.md).
