# Technology options — analysed, **not yet chosen**

> **2026-06-09 note:** Petr's reply (decisions
> [`0028`](./decisions/0028-mass-only-supersedes-0006.md)–[`0034`](./decisions/0034-shadow-run-before-go-live.md))
> narrows the design materially: mass-only catalogue (no variants),
> no prices anywhere, one výdej kind (Říčany is just the default
> odběratel), e-mails internal-only, míchání in MVP, no
> přebalování. The R-requirement analysis below was written against
> the pre-supersede shape (decisions 0001–0013); requirements that
> depended on a Variant table or per-customer e-mail logic are
> annotated below. The stack chosen in
> [`0014`](./decisions/0014-language-python-uv.md)–[`0027`](./decisions/0027-hosting-hetzner.md)
> still supports the narrowed shape directly — Django + Postgres +
> WeasyPrint + HTMX is no less appropriate when the schema is
> smaller.

This file is the prepared analysis for the upcoming technology
decision. **Nothing here is itself a decision.** The first technology
decision will live in [`decisions/0011-*.md`](./decisions/) once it
lands, and only then can code-shaped files appear in the repo (per
`.claude/rules/no-premature-tech-choices.md`).

This file is structured as:

1. **Requirements derived from the design** (Phase A + Phase B
   decisions). The shopping list the stack has to satisfy.
2. **Hard preferences** from `right-sized-for-small-business.md` and
   the owner's brief.
3. **Standing pre-commitments** (only one — `uv` if Python).
4. **Candidate stacks**, each scored honestly against the
   requirements.
5. **Working recommendation** for when Petr signs off the design.

If you see a specific technology mentioned in any file outside this
one (or outside a recorded decision), that is a bug.

The scale to keep in mind: **~6 active users, two branches, ~600
products with variants, low write volume (tens of dodáky per day at
most)**. Anything benchmarked for thousands of users or millions of
rows is overkill and should be discounted on that basis.

---

## 1. Requirements derived from the design

These come from decisions 0001–0010 and the screen-by-screen design.
They are the hard "the stack must support this" list.

### R1 — Czech UTF-8 everywhere, including PDFs

Czech diacritics in UI labels, e-mail subjects/bodies, generated PDFs,
filenames, audit-trail text. Anything weak on Unicode (PDF generators
that mangle `ě`, `ř`, `š`) is out.

### R2 — Browser-first web app, mobile-usable

Per the design: holky use it at the desk and in the warehouse aisle on
phone. **No native iOS / Android app in MVP.** A responsive web view
is the deliverable.

### R3 — Relational data model with referential integrity

The schema (post-2026-06-09 narrowing — see decisions
[`0028`](./decisions/0028-mass-only-supersedes-0006.md)–[`0034`](./decisions/0034-shadow-run-before-go-live.md)):

- `product (id, kind, name_cs, …)` — products and mixtures share the
  table.
- `stock (product_id, branch_id, quantity)` — quantity in kg per
  [`decisions/0028-mass-only-supersedes-0006.md`](./decisions/0028-mass-only-supersedes-0006.md)
  and
  [`decisions/0002`](./decisions/0002-one-catalogue-branch-stock.md).
  **No `Variant` table** — superseded.
- `recipe_component (mixture_product_id, component_product_id, ratio)`
  per [`decisions/0005`](./decisions/0005-mixture-recipe-model.md).
- `movement` with kind enum (`prijem`, `vydej`) per
  [`decisions/0030-vydej-default-ricany-supersedes-0004.md`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)
  (no `prevod` value — Říčany is just a `Customer` row, the
  default odběratel on výdej).
- `movement_line (movement_id, product_id, quantity_kg, sarze NULL,
  expiry NULL, note NULL)`.
- `dodaci_list (id, cislo, branch_id, year, counter, vydej_id, …)`
  per [`decisions/0008`](./decisions/0008-dodaci-list-numbering.md).
- `dodaci_list_version (dodaci_list_id, version, pdf_blob, …)` and
  `dodaci_list_email_log` per
  [`decisions/0007`](./decisions/0007-auto-reissue-corrected-dodaky.md).
- `odberatel`, `dodavatel`, `user`, branch records.

This is **clearly relational** with foreign keys, unique constraints
(branch counter), check constraints (one bulk variant per product,
recipe ratios sum to 1.000). Document stores are wrong-shaped.

### R4 — Exact decimal arithmetic on quantities

Per [`decisions/0003`](./decisions/0003-primary-unit-kg-decimals.md):
mass in NUMERIC(10,3), 1 g precision. Floats are explicitly off the
table. Recipe ratios at 6 dp. The store must support exact decimals;
the language/ORM must not silently coerce to float.

### R5 — PDF generation with full layout control

Dodací list PDF per
[`screens/14-nastaveni.md`](./screens/14-nastaveni.md): A4 portrait,
single column, header with logo + company identity, document block,
customer block, line table with conditional šarže/note columns,
signature line, footer with page N/M. Continuation pages with
repeating header when lines overflow. Must render Czech diacritics
flawlessly.

This rules out anything that wraps a browser print API
heuristically; the PDF library must give us deterministic typeset
output.

### R6 — Outbound SMTP with attachment and templated body

Per
[`decisions/0007`](./decisions/0007-auto-reissue-corrected-dodaky.md)
and [`decisions/0031`](./decisions/0031-emails-internal-only-supersedes-0009.md):
on výdej save, the system composes an e-mail to the **fixed pair**
(Petr + Karolína from Nastavení; no per-customer remembered list,
no ad-hoc recipients), attaches the generated PDF, and sends via
SMTP. On correction the subject is prefixed `[OPRAVA]` and the body
references the change reason. Send failures surface on screens 02 / 09.

Standard requirement; any modern stack meets it.

### R7 — Audit trail with per-field diffs

Per [`decisions/0007`](./decisions/0007-auto-reissue-corrected-dodaky.md)
and `screens/11-uprava-pohybu.md`: every correction records the
original value, the new value, the editor, the timestamp, and a
mandatory free-text reason. The screen renders a per-field "byl X →
je Y" diff.

Two implementation patterns:

- **Library / framework feature**: django-simple-history, papertrail
  in Rails, etc. — record full history rows on every save.
- **Hand-rolled audit table**: small movement-audit table with
  `(movement_id, edited_at, edited_by, reason, field, old_value,
  new_value)`.

Either is fine; the stack must not make this awkward.

### R8 — Atomic transactional save

Výdej save = decrement stock + write movement + generate číslo +
render PDF + send e-mail. Per the design, **stock decrement +
movement + PDF + číslo must be atomic** (if any of those fails, no
partial state). E-mail send is allowed to fail separately (and is
surfaced — it does not roll back the výdej).

So the stack needs: real DB transactions (commit/rollback), proper
counter reservation (no two výdeje getting the same číslo under
concurrent saves). Standard SQL DB feature.

### R9 — Role-based scoping, two roles

Per [`people-and-roles.md`](./people-and-roles.md) and
[`screens/13-sprava-uzivatelu.md`](./screens/13-sprava-uzivatelu.md):

- **Vlastník / správce** (Petr, Karolína) — full access, both
  branches.
- **Obsluha pobočky** (branch staff) — scoped to exactly one branch.

Plus rule: editing historical movements is owner-only. No finer
permissions, no SSO, no SAML.

### R10 — Per-branch monotonic counter with annual reset

Per [`decisions/0008`](./decisions/0008-dodaci-list-numbering.md):
on výdej save, atomically reserve the next `(branch, year_of_issue)`
counter. Must be safe under concurrency (no duplicate numbers, no
gaps that confuse the accountant).

This is the kind of thing a Postgres `SELECT ... FOR UPDATE` on a
counter row, or `RETURNING` on a sequence variant, handles cleanly.

### R11 — Failed email visibility

When SMTP fails, the dodák and výdej still exist, the failure is
recorded, and the dodák appears on screen 02 "K vyřešení" with a
re-send action on screen 09. So there's at least a tiny job-like
mechanism (or a synchronous retry in-request that surfaces failure)
— a full background-job system (Celery, Sidekiq) is **not** required;
synchronous send with try/except and a failure row is enough.

### R12 — Immutable history, soft archival

Per the design: pohyby never deleted (closest is an audited
zero-quantity edit); dodáky never deleted; users only deactivated;
variants/products only archived. The data model and ORM should not
encourage hard deletes.

---

## 2. Hard preferences (from rules and brief)

These are taste-level, not blocking, but they break ties.

- **Boring beats clever.** Documented happy path of the chosen
  stack. (per `.claude/rules/right-sized-for-small-business.md`)
- **Two-tier architecture** — one app, one DB. No microservices, no
  message queues, no event sourcing.
- **Single VPS deploy** target. One box runs the whole thing with
  daily DB backups.
- **CZ developer pool** for handover. Avoid stacks where finding a
  Czech-speaking developer to take over in 2028 is hard.
- **No SSO, no 2FA, no OAuth integrations** in MVP. Plain
  e-mail + password.
- **No SPA framework** unless a screen specifically demands client
  state — and none in the design does. Server-rendered HTML with
  light JS for the výdej preview is enough.
- **No real-time anything** (websockets, SSE).

---

## 3. Standing pre-commitments

**If — and only if — Python is the chosen language, the toolchain is
`uv`.** Not pip, not poetry, not pipenv, not rye, not conda. Pinned
in [`.claude/rules/python-uses-uv.md`](../.claude/rules/python-uses-uv.md).
This constrains *how* Python would be used, not whether.

**No other tech is committed.**

---

## 4. Candidates

For each, I list what it gives, what it costs, and an honest
**Fit** verdict against the requirements above.

### 4.A — Build from scratch: full-stack frameworks

#### Django (Python + uv) + Postgres

**What it gives:**
- Batteries-included framework. Built-in ORM with exact decimals
  (`DecimalField` → Postgres NUMERIC), built-in auth + permissions
  (R9 covered), built-in admin (screens 13 Správa uživatelů and 14
  Nastavení come basically free), built-in CSRF / sessions,
  templated server-rendered HTML (R2), well-documented happy path.
- Transactions, `select_for_update`, sequence handling — R8 / R10
  covered.
- `django-simple-history` for R7 (audit), or a thin hand-rolled
  audit table — both well-documented patterns.
- WeasyPrint for R5 (PDF) — Python library that renders HTML+CSS to
  PDF deterministically with full Czech diacritics support. Pages,
  headers, continuation, footers — all CSS-driven.
- Built-in e-mail backend with SMTP support (R6, R11). Sync send
  with try/except → failure row → screens 02 / 09; no Celery
  needed.
- HTMX for the dodák live preview on screen 07 — keeps the stack
  server-rendered without committing to React.

**What it costs:**
- Django admin is functional, not beautiful. Custom screens
  (02 dashboard, 03 branch view, 07 výdej) need bespoke templates.
  That's the work either way.

**CZ context:** Python + Django talent is abundant in CZ. Czech
localisation is first-class (`django.conf.locale.cs`,
`Decimal`-friendly formatting, date formats).

**Fit verdict: very strong.** Hits every hard requirement directly,
all soft preferences favourable, `uv` pre-commitment aligns. Single
VPS deploy with gunicorn + nginx + Postgres + cron-driven daily
`pg_dump` backups is the standard happy path.

#### Rails (Ruby) + Postgres

**What it gives:** similar shape — full-stack framework, ORM,
templated views, mature ecosystem, audit gems (paper_trail).

**What it costs:** Czech Ruby talent pool is thinner than Python
talent. Ruby deployment story is well-trodden but the operational
familiarity in CZ small-business context is lower.

**Fit verdict: strong on capability, weaker on handover.**

#### Laravel (PHP) + MariaDB or Postgres

**What it gives:** mature framework, abundant cheap PHP hosting in
CZ, lots of developers.

**What it costs:** PHP's idioms around exact decimals and timezones
are more cumbersome than Python's or Ruby's. Audit-trail patterns
exist but are less batteries-included than Django's or Rails's. The
PDF story (dompdf / mPDF) is workable but lower quality than
WeasyPrint for typography-sensitive output (Czech diacritics render
fine, but layout fidelity is worse).

**Fit verdict: workable; weaker on PDF quality and decimal
ergonomics.**

#### Phoenix (Elixir) + Postgres

**What it gives:** server-rendered framework with LiveView for
interactivity, excellent concurrency story.

**What it costs:** concurrency story is irrelevant at this scale.
Talent pool in CZ is small. BEAM operational profile is unfamiliar
to most CZ small-business hosts.

**Fit verdict: works but buys advantages we won't use.**

### 4.B — API + frontend split

#### FastAPI (Python) + React / Vue / HTMX

More moving parts than warranted. Splitting the codebase into API
+ separate frontend adds CORS, build steps, two deploys, and
duplicate validation. **Fit verdict: over-engineered.**

#### Next.js (TypeScript) + Postgres

Workable as a monolith. JS ecosystem churn is a maintenance cost.
PDF generation in Node is weaker than in Python (Puppeteer requires
headless Chromium and ~hundreds of MB; pdfkit is lower-fidelity).

**Fit verdict: workable but no win over Django at this scale.**

### 4.C — Off-the-shelf ERPs

#### Odoo Community

**What it gives:** a full ERP with Inventory, Purchase, Sales, and
Invoicing modules; working dodací list flow out of the box (R5
partially covered, but the PDF template is opinionated); user
management (R9); reporting.

**What it costs:**
- Customising **out** ninety percent of the surface to match Kasia's
  "něco jednoduchého" brief is the real work. The screens listing
  Sales Orders, Purchase Orders, Invoices, Accounting are noise the
  holky shouldn't see.
- The product+variant model (R3) is close to Odoo's but not
  identical; mapping Kasia's specifics (bulk variant + pack variants
  + recipe attached at product level) requires custom modules.
- The auto-email of dodací list to the fixed Petr+Karolína pair per
  [`decisions/0031`](./decisions/0031-emails-internal-only-supersedes-0009.md)
  is not Odoo's default — needs customisation.
- The auto-reissue on correction per
  [`decisions/0007`](./decisions/0007-auto-reissue-corrected-dodaky.md)
  is not Odoo's default workflow either.
- Hosting / upgrade story for Odoo is non-trivial: large Postgres
  schema, Python module compatibility matrix across versions.

**Fit verdict: too heavy. The customisation cost equals or exceeds
the Django-from-scratch cost, with less control.**

#### Dolibarr

**What it gives:** open-source ERP/CRM with stock module, delivery
notes, suppliers, customers. PHP, deployable on shared hosting,
Czech localisation exists.

**What it costs:** UI is dated; customisation effort for Kasia's
exact dodák workflow and auto-email logic is real. The variant
model isn't native — requires extension.

**Fit verdict: plausible second choice if Petr really wants
off-the-shelf, but the customisation cost is not trivially less
than Django.**

#### ERPNext

**What it gives:** open-source ERP on Frappe; Stock module covers
warehouses, items, delivery notes, batch tracking.

**What it costs:** comparable to Odoo. Czech localisation is less
complete.

**Fit verdict: medium-heavy. Same problem shape as Odoo.**

### 4.D — Open-source WMS

#### GreaterWMS and similar

**What they give:** dedicated WMS UX — receive, putaway, pick,
issue, transfer, with warehouse-floor ergonomics.

**What they cost:** designed for multi-aisle warehouses with bin
locations and pickers. Kasia has two small branches with two staff
each and no bin discipline to formalise. The dodací list workflow
is secondary to these tools, not primary.

**Fit verdict: wrong shape.**

### 4.E — Headless CMS / low-code

#### Payload (TypeScript)

**What it gives:** code-first headless CMS with a generated admin
UI; custom collections become editable.

**What it costs:**
- The Payload-generated admin covers ~30% of the screens (Katalog,
  Detail produktu, Uživatelé, Nastavení); the rest (Výdej with live
  PDF preview, Přehled vlastníka, Přehled pobočky with rychlé akce,
  Úprava pohybu with audit trail rendering) is custom React.
- TypeScript everywhere; team has to be comfortable.
- PDF + auto-email + auto-reissue logic is all custom server code.

**Fit verdict: plausible but no clear win over Django; more code
once the custom logic is added.**

#### Directus

Similar shape to Payload. Same verdict.

#### NocoDB

Spreadsheet-like UI over SQL. Workflow-heavy features (PDF render
on save, conditional auto-email with `[OPRAVA]` subject, audit
trail per field) are not its natural strength. **Fit verdict:
under-shaped.**

---

## 5. Working recommendation (for when Petr signs off)

**Primary recommendation: Django (Python + uv) + Postgres +
WeasyPrint + HTMX, deployed on a single VPS.**

Concretely:

- **Language / runtime**: Python (current LTS), toolchain `uv`.
- **Web framework**: Django (current LTS).
- **Database**: Postgres (current stable), one instance, daily
  `pg_dump` backups + WAL archiving for point-in-time recovery.
- **PDF generation**: WeasyPrint. HTML/CSS-driven; Czech diacritics
  flawless; A4 portrait with page N/M and continuation handled by
  CSS.
- **E-mail**: Django's built-in SMTP backend, configured from
  screen 14 Nastavení. Synchronous send inside the výdej save with
  try/except; failure surfaces in screen 02 "K vyřešení" and
  screen 09 re-send.
- **Audit trail**: small hand-rolled audit table per movement edit.
  (django-simple-history is fine too; rolling our own avoids
  pulling a dependency for ~2 tables of audit data.)
- **Frontend**: server-rendered Django templates + HTMX for the few
  dynamic bits (live dodák preview on screen 07, search-as-you-type
  on screens 03 / 04, filter updates on screens 08 / 10). No build
  step, no SPA, no Node dependency.
- **Deployment**: single VPS (any reputable CZ / EU provider),
  Postgres on the same box, gunicorn behind nginx, systemd units,
  Let's Encrypt for TLS. Operational footprint small enough for
  Petr to host with minimal handover support.

**Why this stack:**

- Every hard requirement (R1–R12) is met directly by mainstream,
  well-documented features.
- All soft preferences (boring, single-tier, single-VPS, CZ talent
  abundance, no SPA, no real-time) are aligned.
- Django admin covers ~80% of screens 13 and 14 for free.
- WeasyPrint is the only mainstream library that handles
  PDF-from-HTML well enough for the dodací list quality bar.
- `uv` pre-commitment aligns; standardised across other projects.

**Second choice (if Petr wants off-the-shelf): Dolibarr.** Risk:
customisation cost to match Kasia's exact dodací list workflow
(auto-email with per-customer remembered + ad-hoc recipients,
auto-reissue on correction, variant model) is real and probably
equals the Django-from-scratch cost — with less direct control over
the result.

**Tertiary (if Petr wants the simplest possible code surface for a
single developer in PHP): Laravel + Postgres + Snappy/dompdf.**
Compromises mainly on PDF fidelity.

---

## 6. What is NOT yet committed

Per `.claude/rules/no-premature-tech-choices.md`, even after this
analysis no code-shaped files appear in the repo until the decision
file is recorded:

- programming language
- web framework
- database
- frontend approach (server-rendered, SPA, hybrid)
- PDF generator
- email-sending mechanism
- deployment target (cloud, VPS, on-prem)
- containerisation
- ORM, query builder, or "neither"

Any mention of a specific technology outside this file, or outside a
recorded decision in [`decisions/`](./decisions/), is a bug.

The next step is: **Petr signs off the design (the
`context/petr-summary.txt` message)**, then Matej picks the stack
(this file plus his judgement), then a decision file
`decisions/0011-tech-stack.md` lands, and only then can code be
written.

---

## 7. Public-site analytics

Added 2026-07-14, after the HTTPS / `kasia.cz` cutover
([`decisions/0056`](./decisions/0056-domain-cutover-https.md)) put the
public marketing site on unauthenticated traffic with zero visibility
into visitors. Analytics is a new layer not covered by 0014–0027, so
per `.claude/rules/no-premature-tech-choices.md` the comparison lives
here and the choice is recorded in
[`decisions/0076-public-site-analytics.md`](./decisions/0076-public-site-analytics.md).

Scope: the **public site only**. The warehouse app under `/sklad/` is
deliberately out — operators are known users with `last_login` and an
audit trail; tracking them adds GDPR surface for no insight.

| Candidate | Shape | Trade-offs |
|---|---|---|
| **Umami v2, self-hosted** (chosen) | Node.js + own Postgres container on the existing CPX22; ~150 MB RAM; Apache-2.0 | Cookie-less, daily-rotating pseudonymised visitor hash → no consent banner. €0/mo. One more container pair to patch. Covers pages / referrers / countries / realtime, which is the whole ask. |
| **Plausible CE v2, self-hosted** | Elixir + Postgres **+ ClickHouse** | Same privacy posture, but a second analytical DB engine (~1 GB+ RAM) for a handful of daily visitors — oversized for this box and this traffic. |
| **Umami Cloud / Plausible Cloud** | SaaS, ~€9/mo | Zero ops, but recurring cost roughly doubles the entire hosting bill (~€11.50/mo per [`decisions/0027`](./decisions/0027-hosting-hetzner.md)) and moves visitor data off-box. Poor fit for a cost-sensitive ~6-user business. |
| **GoAccess over persisted Caddy logs** | Log analyser, no JS tag | Requires making Caddy logs durable first; no visit sessions, no referrer parsing on bot-filtered hits, no country panel without extra GeoIP plumbing. The "cheapest" option that answers the fewest questions. |
| **Do nothing** | Status quo | Caddy logs are ephemeral stdout; Hetzner console is box-level only. Acceptable pre-cutover; not once `kasia.cz` takes real traffic. |
