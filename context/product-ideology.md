# Product ideology — the hardest open area

This file describes the design tensions around how products are modelled.
It is **descriptive**, not prescriptive. None of what follows is a
decision. Decisions go in [`decisions/`](./decisions/) and currently
there are none.

The reason this matters: almost every screen — catalogue, příjem, výdej,
the lines on the dodací list, the accountant export — is shaped by how
we model goods. Pick the wrong model and the entire UI fights us. Pick
late and we redo screens. Pick well and the rest is small work.

## Two ideologies live in the catalogue

Kasia's catalogue contains two fundamentally different kinds of thing.

### (a) Raw spices

Pure single-ingredient material: sůl, mletý černý pepř, oregano,
sladká paprika. Approximately 369 entries in this group. The
ingredient identity is the primary anchor — "oregano is oregano" —
and the question is **how much** and **in what packaging**.

Raw spices come in (at minimum):

- 25 kg bulk gastro sacks for resale to large foodservice buyers
- ~5 kg / ~10 kg intermediate gastro packs
- 1 kg packs for smaller gastro and gourmet trade
- ~100 g retail jars under the VERA GURMET brand

The open question is: do we track "X kg of oregano" as a single pool of
mass, where pack size is a packaging concern resolved at the moment of
issue, or do we treat each (oregano × pack size) as a separate stocked
item?

### (b) Mixtures / blends

Branded house recipes — *Zlaté Kuře* is the worked example the owner
gave. A mixture is a deterministic recipe: N raw spices combined in
fixed ratios. The catalogue holds ~236 finished VERA GURMET products,
of which some non-trivial fraction are mixtures (the rest being
branded single-ingredient packs).

A mixture is **produced** from raw-spice stock by a **mixing job**:
the branch takes N kg from each source spice as the recipe dictates,
combines them, and the result is M kg of mixture stock (with M usually
equal to the sum of inputs, minus rounding / dust loss).

## The mixing job — future workflow shape

Not in MVP, but the data model has to anticipate it. Sketch only:

- A **recipe** is a list of `(raw spice, ratio)` pairs. Ratios sum to 1
  (or 100 %). The recipe lives in the catalogue attached to the mixture.
- A **mixing job** (výrobní dávka) is one execution: branch, date,
  operator, target quantity. The system consumes source stock per
  recipe and produces mixture stock.
- There is probably value in an **intermediate / in-progress state**:
  raw spices are reserved or consumed when the job starts, mixture
  stock appears only when the job is closed. Mixing physically takes
  time and the operator may want a "started but not yet done" state
  rather than an atomic flip. Open whether to bother.
- **Batch traceability** is an open question of its own. Two
  positions:
  - **Full traceability:** the produced mixture batch records which
    source-spice batches were consumed. Supports recall, satisfies
    food-safety auditors, costs complexity in the schema and UI.
  - **No traceability:** the mixture is just stock that appeared from
    a job, sources are aggregated. Much simpler. Acceptable if the
    business has not been asked for recall traceability and does not
    expect to be.

Petr has not asked for traceability. He also has not said it's
unwanted. Defer to a real conversation.

## Pack-size ideology — three candidate models

These are mutually exclusive at the data-model layer. Pick one and
the catalogue, příjem UI, výdej UI, and dodací list lines all follow.

### Model 1 — Mass-only

The stock unit is mass (kg or g). The catalogue has one row per
ingredient: "oregano, 1 250 kg on hand". Pack size is a concern at
the moment of issue: the operator picks an amount and optionally
notes a pack format on the dodací list line.

- **Pros:** small catalogue, no SKU sprawl, naturally handles
  weird custom quantities, mirrors how the owner thinks ("máme
  kila").
- **Cons:** the dodací list cannot truthfully say "12 ks 100 g jars"
  without extra logic; the difference between selling a 25 kg sack
  unopened and selling 25 kg loose disappears; retail packaging
  consumed during issue is invisible to the system.

### Model 2 — SKU-per-pack-size

Every (ingredient × pack size) is a separate SKU with its own
stock. Oregano-25kg, oregano-1kg, oregano-100g are three rows.

- **Pros:** the dodací list line is literal — "5 ks oregano 100 g
  dóza" maps to one SKU and a count. Inventory of physical packs
  matches what's on the shelf. Easy for the operator at výdej.
- **Cons:** catalogue size grows by the number of pack formats —
  potentially many times 369. Příjem of bulk material that will
  later be packed has to be modelled (raw oregano arrives in a
  500 kg lot, gets split into the SKUs) — that "splitting" is
  effectively a small production job.

### Model 3 — Product + variant

The catalogue has one **product** per ingredient (or per mixture)
with N **variants** per pack format. Stock lives on the variant.
This is the middle path: catalogue browsing is by product (oregano);
stock and issue happen at variant grain (oregano 100 g jar).

- **Pros:** clean UX in the catalogue (one card per spice) without
  losing pack-level stock. Familiar pattern from e-commerce.
- **Cons:** still need to model the "bulk arrives, gets packed"
  step. Two levels of identity to think about everywhere
  (product vs variant). Reporting has to choose a level.

## What the choice blocks

Until pack-size ideology is decided, the following cannot be drawn or
built without rework:

- **Catalogue UI** (`screens/04-katalog-produktu.md` + `screens/05-detail-produktu.md`) — list one row per ingredient, per SKU, or product-with-variants?
- **Příjem UI** (`screens/06-prijem-zbozi.md`) — what does the
  operator pick from?
- **Výdej UI** (`screens/07-vydej-zbozi.md`) — same.
- **Dodací list line format** — quantity + unit, or count + pack
  spec, or both?
- **Accountant export shape** — line granularity must match what the
  accountant expects on the faktura.

These are tracked in [`open-questions.md`](./open-questions.md). A
recorded decision in [`decisions/`](./decisions/) on this single
question unblocks the largest amount of subsequent work.
