# Project state

> The cold-start anchor. Updated at the end of every working session.
> See `.claude/rules/state-file-discipline.md`.

## Done

- **2026-06-02** — Repository created (initial commit).
- **2026-06-02** — Scaffold pass complete. Directory structure created:
  `context/`, `context/decisions/`, `context/screens/`, `.claude/rules/`,
  `.claude/skills/`.
- **2026-06-02** — Root agent instructions written: `CLAUDE.md`.
- **2026-06-02** — Foundational `context/*.md` files written: `README.md`,
  `owner-request.md`, `company-profile.md`, `people-and-roles.md`,
  `warehouses.md`, `domain-glossary.md`, `workflows.md`,
  `product-ideology.md`, `open-questions.md`, `research-sources.md`,
  `tech-options.md`. Plus `context/decisions/README.md` (decision-log
  format; no decisions recorded yet).
- **2026-06-02** — Agent rules written under `.claude/rules/`:
  `no-premature-tech-choices.md`, `python-uses-uv.md`,
  `language-conventions.md`, `right-sized-for-small-business.md`,
  `decision-log-discipline.md`, `state-file-discipline.md`,
  `czech-first-domain.md`. Plus `.claude/skills/README.md` placeholder.
  No `.claude/settings.json` (deferred until commands are known).
- **2026-06-02** — Screen-by-screen functional design written under
  `context/screens/`: `README.md`, `_template.md`, 01 → 14 (login, owner
  dashboard, branch view, catalogue, product detail, příjem, výdej,
  seznam dodacích listů, detail dodacího listu, historie pohybů, úprava
  pohybu, převod do Říčan, správa uživatelů, nastavení), plus three
  future-* screens (míchání, export pro účetní, skartace).
- **2026-06-02** — Cross-reference reconciliation: drifted screen
  filenames in `workflows.md` and `product-ideology.md` rewritten to the
  canonical names listed in `screens/README.md`. Tech-name grep confirms
  framework/DB names only appear in `tech-options.md` (plus negative
  mentions in `CLAUDE.md` and `no-premature-tech-choices.md`, where they
  belong). No code-shaped files in the repo.
- **2026-06-02** — Round-two self-review kicked off. Pre-step:
  promoted *šarže tracking* (Decide before code) and *auto re-issue /
  re-email of corrected dodáky* (Decide before MVP) into
  `context/open-questions.md`.
- **2026-06-02** — Owner name corrected. Scaffold pass had fabricated
  "Tomáš"; the real owner is **Petr** (Matej's dad). Renamed across all
  17 affected files in `context/` and `.claude/`. Grep clean.
- **2026-06-02** — Phase A Q1 landed:
  [`decisions/0001-sarze-tracking.md`](./decisions/0001-sarze-tracking.md)
  — **šarže is optional**. Nullable field on movement lines and on
  stock. Closes the šarže entry in `open-questions.md`.
- **2026-06-02** — Phase A Q2 landed:
  [`decisions/0002-one-catalogue-branch-stock.md`](./decisions/0002-one-catalogue-branch-stock.md)
  — **one catalogue, branch-specific stock**. Global product table;
  stock keyed by `(product, branch)`. Closes the one-vs-per-branch
  entry in `open-questions.md`.
- **2026-06-02** — Phase A Q3 landed:
  [`decisions/0003-primary-unit-kg-decimals.md`](./decisions/0003-primary-unit-kg-decimals.md)
  — **primary mass unit is kg with 3 dp** (NUMERIC(10,3), 1 g
  precision). Count-stored stock uses `ks` independently where Q6
  introduces it. Closes the primary-unit entry in `open-questions.md`.
- **2026-06-02** — Phase A Q4 landed:
  [`decisions/0004-ricany-transfer-model.md`](./decisions/0004-ricany-transfer-model.md)
  — **first-class převod**. Distinct movement type with destination
  metadata; no dodací list, no email, no matching inbound at Říčany.
  Printed převodka PDF deferred. Closes the Říčany-transfer entry in
  `open-questions.md`.
- **2026-06-02** — Phase A Q5 landed:
  [`decisions/0005-mixture-recipe-model.md`](./decisions/0005-mixture-recipe-model.md)
  — recipes are first-class `(mixture, component, ratio)` rows;
  mixtures & raw spices share the products table by `kind`; recipe
  versioning is **snapshot at mixing-job start**; actual consumption
  may differ from recipe target; source-batch traceability is opt-in.
  Reserve-vs-consume and after-the-fact recording stay operational
  opens on the future míchání screen. Closes the mixture-recipe
  entry in `open-questions.md`.
- **2026-06-02** — Phase A Q6 landed (last *Decide before code*):
  [`decisions/0006-pack-size-product-variant.md`](./decisions/0006-pack-size-product-variant.md)
  — **product + variant**. One product per ingredient, N variants
  per pack format, stock on the variant. Mass-only ruled out (Kasia
  repacks). Recipes attach at product level; mixing job resolves
  variant at consume time. New *Decide before MVP* opens introduced:
  repack as a movement type, variant pricing model. Closes the
  pack-size entry in `open-questions.md`. **Phase A complete.**
- **2026-06-02** — Phase B walkthrough complete: all 18 files edited.
  *Decide before MVP* decisions landed inline:
  [`0007`](./decisions/0007-auto-reissue-corrected-dodaky.md) (auto
  re-issue / re-email of corrected dodáky),
  [`0008`](./decisions/0008-dodaci-list-numbering.md) (numbering
  scheme `<BRANCH>-<YYYY>-<NNNN>`),
  [`0009`](./decisions/0009-dodaci-list-email-recipients.md) (default
  + per-customer remembered + ad-hoc recipients),
  [`0010`](./decisions/0010-prices-on-dodaci-list.md) (no prices on
  MVP dodací list). PDF template structural rules locked on
  `screens/14-nastaveni.md`; visual finalisation deferred to Petr's
  brand assets. Login identifier locked as e-mail. Šarže "if enabled"
  hedging removed across screens 03, 05, 06, 07, 11, 12, future-míšení,
  future-skart. Variant model applied across screens 02, 03, 04, 05,
  06, 07, 08, 09, 10, 11, 12, future-míšení, future-skart. Říčany-as-
  first-class-převod language applied across `workflows.md` and
  screens 07, 10, 12. Auto re-email plumbing applied across `workflows.md`
  and screens 09, 11.
- **2026-06-02** — Phase C cross-reference + glossary sweep complete.
  Drift grep clean (placeholder filenames absent). Tech-name grep
  clean (matches confined to `tech-options.md`, `CLAUDE.md`,
  `.claude/rules/no-premature-tech-choices.md`, plus the known
  "payload" / "API payloads" false positive in
  `.claude/rules/language-conventions.md`). No code-shaped files.
  Glossary additions: `varianta`, `přebalení (přebal)`; existing
  entries `balení`, `šarže`, `převod`, `jednotka` updated to reference
  the landed decisions. **Round-two self-review complete.**
- **2026-06-02** — End-of-design Czech summary message for Petr
  drafted at `context/petr-summary.md` (markdown copy) and
  `context/petr-summary.txt` (plain-text sendable copy). Matej sent
  the plain-text version to Petr. Awaiting Petr's response on the
  open questions (scope sign-off, brand assets, e-mail tone,
  accountant export format, inventura cadence, ceník depth,
  přebalení frequency, drobnosti).
- **2026-06-02** — While waiting on Petr: foundational files
  refreshed against landed decisions —
  `context/people-and-roles.md` (recipient model now references
  [`0009`](./decisions/0009-dodaci-list-email-recipients.md)),
  `context/warehouses.md` (variant model, převod as first-class,
  TYN/SEZ branch codes added). `context/tech-options.md` restructured
  into a proper analysis: requirements R1–R12 derived from the
  design, candidates scored against them, a primary recommendation
  drafted plus second / tertiary fallbacks. Specific stack names live
  only in `context/tech-options.md` per
  `.claude/rules/no-premature-tech-choices.md`. The recommendation
  does not land as a decision yet — the first tech decision is gated
  on Petr's design sign-off.
- **2026-06-03** — Triage of Petr's open-question block from
  `context/petr-summary.txt` § OTÁZKY PRO TEBE. Matej (acting as
  Petr's stand-in during design) closed four sub-questions and
  deferred a fifth; the residual list for Petr shrank from ~8 to ~3.
  Closures landed in `context/open-questions.md` and
  `context/screens/14-nastaveni.md`:
  - **PDF brand defaults ratified** — typography family (sans-serif
    with full Czech diacritic coverage, embeddable, free for
    commercial use), signature-line wording ("Předal / Převzal" +
    datum + podpis), default short footer text (`Kasia vera s.r.o.
    · IČO 25756729 · Říčany u Prahy`). Only Petr's logo files (Kasia
    vera + VERA GURMET) remain open under this sub-question; not a
    hard blocker.
  - **E-mail templates ratified** — Czech subject + body wording for
    the initial dodací list send and the `[OPRAVA]` re-send (per
    [`0007`](./decisions/0007-auto-reissue-corrected-dodaky.md))
    locked verbatim into `screens/14-nastaveni.md` § Šablony e-mailů
    as MVP defaults. Karolína / Petr can tweak the tone in-place
    via the settings screen later.
  - **Mobile / scanner support closed** — barcodes / QR not used at
    Kasia today; MVP = responsive web view, no native app, no
    scanner integration.
  - **Accountant export format deferred** — not on Petr's critical
    path. MVP delivers CSV + PDF download via
    `screens/future-export-uctarne.md`; specific format (Pohoda XML
    / Money S3 / plain CSV) negotiated with the external účetní
    after the first month of real operation. No outreach now.
  Residual Petr asks: scope sign-off, ceník depth (variant pricing
  model), inventura cadence, přebalování frequency, branch ↔ branch
  transfer existence, logo files. No new decisions (0011+) landed;
  the first tech decision is still gated on Petr's scope sign-off.
- **2026-06-04** — Residual design-phase close-out. Petr is hard to
  reach asynchronously; Matej, acting as Petr's stand-in, accepted
  the residual rework risk and locked the six remaining residual
  asks so the project can move from design into tech-stack
  decisions. Locked answers and landing locations:
  - **Scope sign-off — accepted in full.** The 14 screens + decisions
    0001–0010 + the wording in `context/petr-summary.txt` are the
    MVP target.
  - **Ceník depth — single nullable `cena` per variant.**
    [`decisions/0011-variant-pricing-single.md`](./decisions/0011-variant-pricing-single.md);
    references added in
    `context/screens/04-katalog-produktu.md`,
    `context/screens/05-detail-produktu.md`; `context/screens/14-nastaveni.md`
    *Variant pricing* open removed.
  - **Inventura — no dedicated screen.** Reconcile via
    [`screens/11-uprava-pohybu.md`](./screens/11-uprava-pohybu.md)
    with a "při inventuře" reason convention. Landed in
    [`decisions/0012-inventura-via-correction.md`](./decisions/0012-inventura-via-correction.md);
    closed the *Inventura* entry in `context/open-questions.md`.
  - **Přebalování — paired corrections, not a first-class movement.**
    Landed in
    [`decisions/0013-prebalovani-via-correction.md`](./decisions/0013-prebalovani-via-correction.md);
    closes the *Repack as first-class movement type* open from
    [`0006`](./decisions/0006-pack-size-product-variant.md).
  - **Mezi-pobočkové převody (TYN ↔ SEZ) — can happen, want the
    option later.** No dedicated UI in MVP; stays on *Decide later*
    in `context/open-questions.md` with an explicit forward-compat
    requirement on the movement-kind enum (added 2026-06-04).
  - **Loga — text placeholder.** PDF template renders
    `Kasia vera s.r.o.` as the logo area until SVG/PDF files are
    supplied; noted in `context/screens/14-nastaveni.md` § Hlavička
    and § Open questions. Not a hard blocker.
- **2026-06-08** — Tech-stack landed in 14 decision files
  (0014–0027). Stack: **Python 3.14 / uv / Django 5.2 LTS /
  PostgreSQL 18 / psycopg 3 / WeasyPrint 69 / htmx 2 + django-htmx
  1.27 + WhiteNoise / Django SMTP sync / Django auth + groups /
  hand-rolled `movement_audit` table / multi-stage Dockerfile on
  `python:3.14-slim-trixie` / Docker Compose v2 / Caddy 2 HTTP-only
  for MVP / Terraform `hcloud` + cloud-init / GitHub Actions
  push-to-main → GHCR → SSH deploy / Hetzner Cloud CPX22 Falkenstein
  + Storage Box BX11**, ~€11.50/mo. One file per layer:
  [`0014`](./decisions/0014-language-python-uv.md) language,
  [`0015`](./decisions/0015-framework-django.md) framework,
  [`0016`](./decisions/0016-database-postgres.md) database,
  [`0017`](./decisions/0017-pdf-weasyprint.md) PDF,
  [`0018`](./decisions/0018-frontend-htmx.md) frontend,
  [`0019`](./decisions/0019-email-smtp-sync.md) e-mail,
  [`0020`](./decisions/0020-auth-django-builtin.md) auth,
  [`0021`](./decisions/0021-audit-hand-rolled.md) audit,
  [`0022`](./decisions/0022-container-image.md) container image,
  [`0023`](./decisions/0023-runtime-orchestration-compose.md) compose,
  [`0024`](./decisions/0024-tls-caddy.md) TLS/proxy,
  [`0025`](./decisions/0025-iac-terraform-hcloud.md) IaC,
  [`0026`](./decisions/0026-ci-cd-github-actions.md) CI/CD,
  [`0027`](./decisions/0027-hosting-hetzner.md) hosting + backups.
- **2026-06-08** — IaC scaffolded:
  `Dockerfile` + `.dockerignore` + `compose.yaml` + `Caddyfile` +
  `.env.example` at repo root; `infra/terraform/{versions,variables,main,outputs}.tf`
  + `infra/terraform/cloud-init.yaml`;
  `.github/workflows/{ci,deploy,terraform}.yml`;
  `infra/RUNBOOK.md` covering bring-up, deploy, rollback, restore
  drill, and domain cutover.
- **2026-06-08** — Django skeleton scaffolded. `pyproject.toml` +
  `uv.lock` + `.python-version` (3.14) committed; `manage.py`,
  `kasia/{settings/base.py, urls.py, wsgi.py, asgi.py}`,
  `inventory/` app stub (no models yet). Verified locally: `uv
  sync` clean, `uv run python manage.py check` clean,
  `uv run python manage.py migrate` clean (sqlite fallback),
  `uv run pytest` passes (1 test: `/healthz` → 200), `uv run ruff
  check` clean. Container build + compose stack verification is in
  `infra/RUNBOOK.md` for the migration-day run.
- **2026-06-08** — Development workflow locked to **local Docker
  Compose first; Hetzner box only at migration time.** The same
  `Dockerfile` + `compose.yaml` ship to prod; no separate dev
  compose file. `.github/workflows/deploy.yml` is scaffolded but
  dormant until the box exists per
  [`infra/RUNBOOK.md`](../infra/RUNBOOK.md).
- **2026-06-08** — `.claude/rules/` refreshed:
  `no-premature-tech-choices.md` now carries a status banner
  (gate lifted for 0014–0027, still applies to any new layer);
  `python-uses-uv.md` switched to active voice referencing 0014;
  new `.claude/rules/infra-as-code.md` covers IaC discipline (no
  console clicks, no `docker run` ad-hoc, `.env` out of git, push
  to main is the only deploy path, image-tag rollbacks, manual
  `terraform apply`).
- **2026-06-08** — `context/open-questions.md` § Decide later
  gained two new items: backup retention SOP (under existing
  Backup entry, per [`0027`](./decisions/0027-hosting-hetzner.md)),
  and Domain name (deferred per Matej; Caddyfile carries the
  cutover comment per [`0024`](./decisions/0024-tls-caddy.md), no
  decision file needed when it lands).
- **2026-06-09** — **Petr's real answer received** (relayed via
  Matej). 7 decisions landed superseding parts of the residual
  close-out:
  [`0028`](./decisions/0028-mass-only-supersedes-0006.md)
  mass-only catalogue (no variants),
  [`0029`](./decisions/0029-no-prices-supersedes-0011.md) no prices
  anywhere,
  [`0030`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)
  one výdej kind with default odběratel Říčany (no separate
  převod surface),
  [`0031`](./decisions/0031-emails-internal-only-supersedes-0009.md)
  dodák e-mails go to Petr+Karolína only (never to customers),
  [`0032`](./decisions/0032-mixing-in-mvp.md) míchání in MVP
  (~25 mixtures ≤15 components),
  [`0033`](./decisions/0033-prebalovani-out-of-scope-supersedes-0013.md)
  no přebalování workflow,
  [`0034`](./decisions/0034-shadow-run-before-go-live.md) 14-day
  shadow run before cutover. Screens swept: screen 12 deleted,
  `future-misseni.md` renamed to `15-michani.md`, screens 02–11
  + 14 + README sweep. Glossary, open-questions,
  people-and-roles, warehouses, workflows, tech-options,
  petr-summary updated. Future readers: to know what's actually
  being implemented in MVP, read decisions in numeric order —
  0028–0034 supersede parts of 0001–0013; the tech stack
  0014–0027 supports the superseded shape directly.

- **2026-06-10** — First real models pass landed. New `accounts/`
  app with custom `User` (e-mail login, nullable `branch` FK) per
  [`0020`](./decisions/0020-auth-django-builtin.md); `AUTH_USER_MODEL
  = "accounts.User"` set in `kasia/settings/base.py`. `inventory/`
  models filled in: `Branch`, `Customer` (with
  `is_default_recipient` partial-unique per
  [`0030`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)),
  `Supplier`, `Product` (`kind ∈ {raw_spice, mixture}`,
  active-name partial-unique) per
  [`0005`](./decisions/0005-mixture-recipe-model.md) +
  [`0028`](./decisions/0028-mass-only-supersedes-0006.md), `Stock`
  (`(product, branch)` unique, `NUMERIC(10,3)`, non-negative check)
  per [`0003`](./decisions/0003-primary-unit-kg-decimals.md), and
  `RecipeComponent` (per-row ratio bounds + `clean()` kind/cycle
  checks; sum-to-one deferred to mixing-job form). Migrations:
  `inventory/0001_initial`, `accounts/0001_initial`,
  `inventory/0002_seed_branches_and_ricany` (TYN, SEZ, Říčany
  default-recipient row per
  [`0030`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)
  + [`0031`](./decisions/0031-emails-internal-only-supersedes-0009.md)),
  `accounts/0002_seed_groups` (`vlastnik`, `obsluha`). Admin
  registered for all seven models with `RecipeComponent` inline on
  `Product`. 17 pytest tests pass (model constraints, custom auth,
  seed migrations); ruff clean; `ruff per-file-ignores` extended to
  exempt Django-generated `**/migrations/*.py` from `E501`/`I001`.
  **Postgres verification deferred** — `compose.yaml` `db` service
  fails to start on Postgres 18 due to a pre-existing
  `/var/lib/postgresql/data` volume-layout incompatibility unrelated
  to this pass; logged as a follow-up. SQLite migrate is clean.

## In progress

_(nothing — first real models landed; ready for movement tables
+ audit + dodací list pass)_

## Next

1. **Movement tables + audit + dodací list** —
   `inventory.Movement` (kind ∈ {prijem, vydej} per
   [`0030`](./decisions/0030-vydej-default-ricany-supersedes-0004.md)),
   `MovementLine`, `MovementAudit` per
   [`0021`](./decisions/0021-audit-hand-rolled.md), `DodaciList` +
   `DodaciListVersion` + `DodaciListEmailLog` per
   [`0007`](./decisions/0007-auto-reissue-corrected-dodaky.md) +
   [`0008`](./decisions/0008-dodaci-list-numbering.md) +
   [`0031`](./decisions/0031-emails-internal-only-supersedes-0009.md);
   `Settings` singleton for Petr+Karolína recipient pair + PDF
   defaults per `screens/14-nastaveni.md`. Also: a small management
   command to render one výdej as PDF to smoke-test WeasyPrint
   before screen 07 lands.
2. **Fix the compose Postgres 18 volume layout** — `compose.yaml`
   currently mounts `pgdata:/var/lib/postgresql/data`, which
   `postgres:18-trixie` refuses (it wants the mount one level up).
   Surfaced 2026-06-10 during the models pass. Small infra fix;
   does not require a new decision.
3. **Provision the Hetzner box** —
   `cd infra/terraform && terraform apply` from Matej's
   workstation, populate `/srv/kasia/.env`, set GH Actions
   secrets (`SSH_HOST`, `SSH_USER`, `SSH_KEY`), push to `main` to
   trigger the first deploy. Verify against
   [`../infra/RUNBOOK.md`](../infra/RUNBOOK.md). First production
   use runs **14 days in shadow** (Petr + Karolína only, real
   data, no operational reliance) per
   [`0034`](./decisions/0034-shadow-run-before-go-live.md), then
   branch-staff cutover.
