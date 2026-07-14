# Open questions

Living list of unresolved design questions. Grouped by **when** the
question blocks progress, not by topic. Each item: what's the question,
what it blocks, who needs to weigh in.

When a question is answered, it does not get edited out of this file —
it gets a short closing note and a link to the
[`decisions/`](./decisions/) entry that resolved it.

---

## Decide before code

These block the data model and therefore everything downstream.

### Pack-size granularity model

What is the unit of stock — mass only, SKU-per-pack-size, or
product-with-variants? See [`product-ideology.md`](./product-ideology.md)
for the three candidate models laid out. **Blocks:** catalogue UI,
příjem UI, výdej UI, dodací list line format, accountant export.
**Needs:** owner (Petr) to describe how he wants to think about
inventory; Karolína to weigh in on accountant compatibility.

> **Closed 2026-06-02 → [`decisions/0006-pack-size-product-variant.md`](./decisions/0006-pack-size-product-variant.md):** *product + variant*.
> One product per ingredient; N variants per pack format; stock on the variant. Recipes attach at product level. Mass-only ruled out because Kasia repacks bulk → retail jars. New opens introduced: repack-as-movement-type, variant pricing model — both for *Decide before MVP*.
>
> **Reopened and re-closed 2026-06-09 → [`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md):** Petr's brief explicitly narrows the model to **mass-only** — "neřeším druh balení, zajímá mne jen celková hmotnost". No `Variant` table, no pack format, stock in kg only. Variant-pricing open dropped along with the Variant table. Repack-as-movement-type open closed by [`0033`](./decisions/0033-prebalovani-out-of-scope-supersedes-0013.md): no přebalování workflow.

### Říčany transfer — tracked movement or stock-out-and-gone

A transfer from a branch to Říčany leaves the system. Is it a
first-class **převod** with destination metadata, an internal
převodka document for the owner's records, or simply a výdej with
reason = "transfer to Říčany"? **Blocks:** výdej screen, movement
history filters, the question of whether to email anything on a
Říčany transfer. **Needs:** owner.

> **Closed 2026-06-02 → [`decisions/0004-ricany-transfer-model.md`](./decisions/0004-ricany-transfer-model.md):** *first-class převod*.
> Distinct movement type with destination metadata; no dodací list, no email, no matching inbound at Říčany. Printed převodka PDF deferred (no in MVP).
>
> **Reopened and re-closed 2026-06-09 → [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md):** Petr's brief: "lištu převod můžeme úplně vynechat" — one movement kind for goods-out (`výdej`). Říčany is just a seeded `Customer` row, default-selected. Screen 12 deleted; the dodák+e-mail does fire on a Říčany výdej (internal pair only per [`0031`](./decisions/0031-emails-internal-only-supersedes-0009.md)).

### Mixture recipe data model

How is a recipe stored, and how is a mixing job recorded? See the
mixing-job sketch in [`product-ideology.md`](./product-ideology.md).
**Blocks:** catalogue model for mixtures, future mixing-job screen,
whether mixture stock and raw-spice stock share a table or live
separately. **Needs:** owner to describe how recipes change over
time (are they fixed once defined, or do batches drift?), and
whether traceability of mixture batch back to source-spice batches
is required.

> **Closed 2026-06-02 → [`decisions/0005-mixture-recipe-model.md`](./decisions/0005-mixture-recipe-model.md):** recipe = first-class `(mixture, component, ratio)` rows; mixtures & raw spices share the products table by `kind`; **recipe versioning = snapshot at mixing-job start**; actual consumption may differ from recipe target; source-batch traceability opt-in (per [`0001`](./decisions/0001-sarze-tracking.md)). Reserve-vs-consume and after-the-fact recording remain operational opens for the future míchání screen.

### Primary unit of measure

Is the canonical stored unit kg with decimals, grams as integers,
or per-pack ks? Tied to pack-size model but worth its own slot
because it affects rounding, display, and recipe arithmetic.
**Blocks:** every quantity field. **Needs:** owner + Karolína.

> **Closed 2026-06-02 → [`decisions/0003-primary-unit-kg-decimals.md`](./decisions/0003-primary-unit-kg-decimals.md):** *kg with decimals (NUMERIC(10,3))*.
> Mass-stored quantities are kilograms with 1 g precision. Count-stored (ks) coexists where Q6 introduces it. Display unit ≠ storage unit.

### One product across branches, or one per branch?

When Týniště and Sezimovo Ústí both stock oregano, is that one
catalogue entry with two stock figures, or two catalogue entries?
Default expectation is "one product, branch-specific stock", but
the question deserves an explicit nod because the alternative
exists in some ERP modelling. **Blocks:** catalogue schema, reports.
**Needs:** owner.

> **Closed 2026-06-02 → [`decisions/0002-one-catalogue-branch-stock.md`](./decisions/0002-one-catalogue-branch-stock.md):** *one catalogue, branch-specific stock*.
> Global product table; stock keyed by `(product, branch)`. Catalogue management stays with the owner / Karolína.

### Šarže (batch) tracking

Surfaces in seven screen files (03, 05, 06, 07, 12, both futures)
without ever being committed to. Three positions worth naming:
**mandatory** (every príjem records a batch ID + expiry, every výdej
picks from a batch, FIFO/FEFO enforced), **optional** (batch fields
exist but can be left blank; reporting tolerates absence), **absent**
(no batch concept at all; quantity-only). Food-safety recall and
expiry visibility argue for mandatory; ergonomics for ~6 users argue
for absent or optional. **Blocks:** príjem/výdej/převod field shape,
product-detail metadata, mixing-job traceability (see also the
mixture-recipe entry above). **Needs:** owner — and a quick check
on whether the external accountant or any customer ever asks for
batch / lot info on a dodací list.

> **Closed 2026-06-02 → [`decisions/0001-sarze-tracking.md`](./decisions/0001-sarze-tracking.md):** *optional*.
> Nullable šarže field on movement lines and stock. Operator records when known, skips otherwise.

---

## Decide before MVP

These block first usable release but not the data model.

### Dodací list numbering scheme

Per-branch annual sequence (`TYN-2026-0001`)? Global sequence?
Annual reset or continuous? Czech accounting practice and the
accountant's expectations both matter here. **Blocks:** dodací
list generation. **Needs:** Karolína + the external accountant.

> **Closed 2026-06-02 → [`decisions/0008-dodaci-list-numbering.md`](./decisions/0008-dodaci-list-numbering.md):** *per-branch annual sequence* `<BRANCH>-<YYYY>-<NNNN>` (e.g. `TYN-2026-0042`). Year segment = issue date's year. Internal correction versions per [`0007`](./decisions/0007-auto-reissue-corrected-dodaky.md) do not change the číslo.

### Email recipients — configurable per dodací list or global

Default: owner + Karolína on every dodací list. Should the
operator be able to add the customer to the recipient list on
issue? Should it remember per-customer? **Blocks:** výdej screen,
notification template. **Needs:** owner.

> **Closed 2026-06-02 → [`decisions/0009-dodaci-list-email-recipients.md`](./decisions/0009-dodaci-list-email-recipients.md):** fixed default (Petr + Karolína) + per-customer remembered list on the odběratel record + ad-hoc per-issue additions promotable to remembered via an explicit "uložit pro tohoto odběratele" tick.
>
> **Reopened and re-closed 2026-06-09 → [`decisions/0031-emails-internal-only-supersedes-0009.md`](./decisions/0031-emails-internal-only-supersedes-0009.md):** Petr's brief: "i dodací listy na jiné odběratele ať odchází pouze na náš email, ne koncovým zákazníkům." The recipient set on **every** dodák is the fixed Petr+Karolína pair from Nastavení. No per-customer remembered list. No ad-hoc additions. `Customer.email` exists for contact-record use only — the send code does not read it.

### PDF template

Logo, IČO + DIČ block, customer block, line table, signature line,
footer. Probably one A4 page, possibly with a continuation rule.
**Blocks:** PDF generation. **Needs:** owner to provide brand
assets and approve a draft layout; Karolína on legal completeness.

> **Partially closed 2026-06-02 → [`screens/14-nastaveni.md`](./screens/14-nastaveni.md) `PDF šablona — struktura`:** structural rules locked (A4 portrait, single column, header + document block + customer block + line table without prices per [`0010`](./decisions/0010-prices-on-dodaci-list.md) + signature line + footer; continuation pages with repeating header).
>
> **Further narrowed 2026-06-03 (Matej-ratified MVP defaults):** typography = sans-serif with full Czech-diacritic coverage, embeddable, free for commercial use (concrete font name follows from stack/PDF-library choice); signature wording = "Předal / Převzal" with `datum` + `podpis` fields under each label; default footer text = `Kasia vera s.r.o. · IČO 25756729 · Říčany u Prahy` (long contact footer available later if Petr wants it); default e-mail templates for initial send and `[OPRAVA]` re-send ratified verbatim (texts now live in `screens/14-nastaveni.md` § Šablony e-mailů). **Remaining open:** Petr's logo files (Kasia vera + VERA GURMET; SVG/PDF preferred). Captured as the sole brand-asset sub-question for the end-of-design Petr summary; not a hard blocker.

### Accountant export format

CSV? Pohoda XML? Money S3 import? Plain emailed PDFs as today?
The system's value to the accountant depends on this. **Blocks:**
the export workflow and possibly the accountant export screen.
**Needs:** the external accountant directly.

> **Deferred 2026-06-03 (Matej):** not on the critical path for
> Petr's design sign-off. MVP delivers CSV + PDF download from the
> [`screens/future-export-uctarne.md`](./screens/future-export-uctarne.md)
> surface; the specific format (Pohoda XML, Money S3 import, plain
> CSV) is negotiated with the external účetní after the first month
> of real operation, not before. No outreach to the účetní (via
> Karolína or otherwise) right now — the question remains formally
> open but blocks nothing in the design phase.

### Auto re-issue / re-email of corrected dodáky

Surfaces in screen files 09, 11 and in `workflows.md` without a
landed answer. When a movement that's already on a sent dodací list
is corrected, does the system **auto-regenerate** the PDF and
**auto-email** the new version to the original recipients, or does
the operator have to trigger both manually? In-between option:
auto-regenerate the PDF, but require a confirm before re-sending.
Tied to the embedded judgement call that "PDF re-render uses the
current template + corrected data" — that judgement is upstream of
this one. **Blocks:** correction UX on screens 09 and 11,
notification template, audit trail of "what was sent when".
**Needs:** owner — driven by how he wants Karolína and the
accountant to learn about corrections.

> **Closed 2026-06-02 → [`decisions/0007-auto-reissue-corrected-dodaky.md`](./decisions/0007-auto-reissue-corrected-dodaky.md):** *auto-regenerate + auto-email* with `[OPRAVA]` subject prefix and a per-dodák version+send audit table on screen 09. Internal version counter is per-dodací-list and does not interact with the (still-open) numbering scheme.

### Inventura (stock-take) workflow shape

Full periodic? Rolling per shelf? Mobile-assisted? Or out of MVP
scope entirely with a manual reconciliation route via the
correction workflow? **Blocks:** inventura screen. **Needs:**
owner + branch staff.

> **Closed 2026-06-04 → [`decisions/0012-inventura-via-correction.md`](./decisions/0012-inventura-via-correction.md):** *no dedicated screen*.
> Inventura discrepancies are reconciled via the existing correction workflow on [`screens/11-uprava-pohybu.md`](./screens/11-uprava-pohybu.md) with a `"při inventuře"` reason convention. Closed by Matej as Petr's stand-in during the residual close-out pass.

---

## Decide later

These can be deferred without blocking MVP.

### Mobile / scanner support

Are barcodes or QR codes used today on incoming or outgoing
material? If so, scanning at příjem and výdej is worth designing
for; if not, a phone-friendly responsive web view may be enough.
**Blocks:** nothing in MVP, blocks meaningful warehouse-floor
ergonomics. **Needs:** branch staff observation.

> **Closed 2026-06-03 (Matej confirmed):** barcodes / QR codes are
> not used at Kasia today on either příjem or výdej. MVP target =
> responsive web view sized for desktop + tablet; no native mobile
> app, no scanner integration, no camera-based code reading. Revisit
> only if branch staff adopt scanners in regular operation — at
> which point this becomes a new open question with concrete
> hardware in scope.

### Branch ↔ branch transfers

Currently assumed not to happen. If they do, decide whether to
model them as paired (out, in) movements or two unrelated events.
**Blocks:** transfer screen extensions only. **Needs:** owner
confirmation.

> **2026-06-04 note (Matej, as Petr's stand-in):** they *can*
> happen between TYN and SEZ, and we want the option to support them
> properly later. **No dedicated UI in MVP.** Operationally handled
> today as a pair of manual výdej + příjem rows. Stays on
> *Decide later*. **Forward-compat requirement on the movement
> model:** the schema must be able to add a paired-transfer
> movement kind (analogous to převod do Říčan per
> [`decisions/0004-ricany-transfer-model.md`](./decisions/0004-ricany-transfer-model.md))
> without rewriting the movement table or backfilling history. The
> existing movement-kind enum is the natural growth point.
>
> **2026-06-09 update (Petr via Matej):** Petr's brief did not
> mention branch ↔ branch transfers. **Tabled** — revisit only if
> Petr asks. After [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)
> the movement-kind enum is just `{prijem, vydej}`; if a
> paired-transfer kind ever lands, it's a fresh decision then.

### Multi-warehouse expansion beyond the two branches

If a third branch opens, is the system structurally ready? Likely
yes if branches are first-class, but worth explicit confirmation.
**Blocks:** nothing today. **Needs:** owner if/when it arises.

### Backup and retention strategy

How long is movement history kept, how is the dataset backed up,
how is data restored. **Blocks:** operational handover. **Needs:**
whoever ends up hosting.

> **2026-06-08 partial close →
> [`decisions/0027-hosting-hetzner.md`](./decisions/0027-hosting-hetzner.md):**
> daily restic-encrypted backups (Postgres dump + `pgdata` snapshot)
> to a Hetzner Storage Box BX11. **Still open:** retention SOP
> (how many daily / weekly / monthly snapshots) and restore-drill
> cadence — to be written into
> [`../infra/RUNBOOK.md`](../infra/RUNBOOK.md) § 4 once operating
> history accumulates. Movement history itself is never deleted
> per the data-model rule (see R12 in `tech-options.md`).

### Domain name

Public hostname for the deployed app + TLS cutover.
**Blocks:** TLS (HTTPS) — until a domain lands, the system serves
HTTP on IP only. **Needs:** Petr / Matej to register a domain.

> **2026-06-08 (Matej):** deferred. IP-only initially; Caddy stays
> configured for HTTP per
> [`decisions/0024-tls-caddy.md`](./decisions/0024-tls-caddy.md).
> The `Caddyfile` and
> [`../infra/RUNBOOK.md`](../infra/RUNBOOK.md) § 5 document the
> exact two-line cutover when the A-record lands. **No decision
> file needed** — the cutover is a config edit, not a stack
> change.

### Public-site analytics

Opened in effect alongside the public marketing site
([`decisions/0050`](./decisions/0050-public-site-and-sklad-split.md) +
[`0051`](./decisions/0051-public-site-ia-and-content.md)) but not logged
here at the time: once `kasia.cz` takes unauthenticated traffic, is
there any visibility into visitors — how many, from where, on which
pages, with which referrer? Caddy logs are ephemeral stdout; the
Hetzner console is box-level only. **Blocks:** nothing operational;
blocks any informed iteration on the public site. **Needs:** Matej.

> **Closed 2026-07-14 → [`decisions/0076-public-site-analytics.md`](./decisions/0076-public-site-analytics.md):**
> self-hosted **Umami v2** on the existing CPX22 at
> `analytics.kasia.cz` (own compose service pair + own Postgres,
> `profiles: [prod]`), tracker tag on the public base template only,
> with a request-path privacy gate so `/sklad/…` (incl. the login
> page, which reuses the public chrome) never ships the tracker.
> Cookie-less → no consent banner. Candidates compared in
> [`tech-options.md`](./tech-options.md) § 7.

### Operator-usage tracking on `/sklad/`

Opened in effect alongside the public-site analytics question but for
the other surface: once real operators work in `/sklad/`, is there any
visibility into *which operator uses which screen, and when*? Umami
(0076) deliberately cannot see `/sklad/`; `last_login` covers logins
only and `MovementAudit` covers writes only — nothing records reads.
**Blocks:** nothing operational; blocks any informed iteration on the
warehouse screens. **Needs:** Matej.

> **Closed 2026-07-14 → [`decisions/0077-sklad-usage-tracking.md`](./decisions/0077-sklad-usage-tracking.md):**
> first-party, server-side `ScreenVisit` log — one row per
> authenticated full-page GET under `/sklad/` (who / which screen /
> when; no IP, no User-Agent, no client JS), written by the project's
> first custom middleware, append-only, kept forever, surfaced on a
> vlastník-only „Aktivita" Správa page. Operators are informed
> (employment-context transparency note in 0077).

### Shrinkage / damage as first-class movement type

Make **odpis** a first-class movement with reason codes, or
continue to handle it through the correction workflow? Becomes
relevant once there is enough operating history to see how often
it happens. **Blocks:** future odpis screen. **Needs:** owner.

### User-facing language

Czech-only is the default and the owner's expectation. If a
Polish supplier or Slovak buyer ever gets system access — unlikely
— a language toggle becomes interesting. **Blocks:** nothing today.

### 14-day shadow run cutover criteria

Per [`decisions/0034-shadow-run-before-go-live.md`](./decisions/0034-shadow-run-before-go-live.md)
the first deploy runs 14 days in shadow (Petr + Karolína only,
real data, no operational reliance) before branch staff onboard.
**What counts as "ready to go live"?** Candidates:

- Petr's explicit sign-off after the 14 days.
- A resolved (or triaged) bug list collected during the window.
- A minimum number of real dodáky issued (e.g. ≥ 10 per branch)
  so the workflow has actually been exercised.
- Karolína's sign-off that the dodák → účetní hand-off works.

**Blocks:** the production cutover gate. **Needs:** Petr + Matej
to agree before day 14 of the shadow run.
