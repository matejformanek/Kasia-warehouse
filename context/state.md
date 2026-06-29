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
  SQLite migrate clean.
- **2026-06-11** — Movement + audit pass 1 of 2 landed (per
  `state.md` § Next item 2 forward pointer). Audit-shape extension
  recorded as
  [`0035`](./decisions/0035-audit-line-events.md) (supersedes the
  column list in
  [`0021`](./decisions/0021-audit-hand-rolled.md); 0021 banner
  added). New models: `inventory.Movement`
  (kind ∈ {prijem, vydej} per
  [`0030`](./decisions/0030-vydej-default-ricany-supersedes-0004.md),
  named counterparty CHECK constraint, `clean()` mirror, delete
  disabled in admin), `MovementLine` (positive-quantity CHECK,
  šarže ≤64, expiry, `signed_quantity` property), `MovementAudit`
  (target_kind ∈ {movement, line}, event ∈ {field_changed,
  line_added, line_removed}, line_id non-FK so audit survives line
  delete, non-empty `reason` CHECK).
  `inventory/services.py` introduced with the single create / edit
  write path: `apply_movement(...)` (atomic; no audit on insert)
  and `edit_movement(...)` (atomic; one audit row per changed field
  + per line lifecycle event; reason mandatory; kind-change
  forbidden; `# TODO Pass 2 — DodaciList re-render hook`). Stock
  mutation wraps `stock.save()` in a nested `transaction.atomic()`
  savepoint so a `stock_non_negative` violation converts cleanly to
  `ValidationError` without breaking the outer transaction.
  `MovementAdmin` registered with `MovementLineInline` and a
  `save_related` override that calls `apply_movement` /
  `edit_movement` (no DB writes in `save_model` per the user's
  option (I) choice on 2026-06-11); `MovementAuditAdmin` is
  read-only. Migration `inventory/0003_movement_and_audit.py`
  generated and renamed. 21 new tests appended in
  `inventory/tests.py` (schema constraints + apply / edit service
  + admin smoke); `inventory/conftest.py` introduced with
  seed-aware fixtures (`tyn`, `sez`, `ricany`, `pepper`, `paprika`,
  `supplier`, `user_tyn`, `user_vlastnik`, `admin_user`) that
  `.objects.get(...)` against already-seeded rows. Full suite: 38
  pytest tests green; ruff clean; SQLite migrate clean. Pass 2
  (DodaciList + Settings + WeasyPrint + e-mail) deferred to a
  fresh plan per the original split.
- **2026-06-10** — `compose.yaml` `db` service volume mount moved
  from `/var/lib/postgresql/data` to `/var/lib/postgresql` so
  `postgres:18-trixie` starts cleanly (PG18+ stores data under a
  major-version-specific subdirectory and refuses the old layout —
  see docker-library/postgres#1259). Backup-service mount path
  updated to match. End-to-end verification: with the locale flags
  temporarily neutralised to `C.UTF-8` (to isolate the layout fix
  from the second, unrelated locale issue below),
  `docker compose up -d db && uv run python manage.py migrate`
  applies all migrations against PG18, and the full 17-test suite
  passes against Postgres. Locale flags restored after verification.
  **Latent issue still blocking compose: `cs_CZ.UTF-8` is not
  available in the `postgres:18-trixie` base image** (`initdb:
  error: invalid locale name "cs_CZ.UTF-8"`), so the stack currently
  still cannot bring `db` up with the locale settings required by
  [`0016`](./decisions/0016-database-postgres.md). Promoted to
  § Next item 1 — needs a planning step (extend the image with
  `locales-all` vs. switch to ICU locale provider).

- **2026-06-11** — Pass 2 (DodaciList + Settings + WeasyPrint +
  e-mail) landed. Two new decisions:
  [`0036`](./decisions/0036-dodaci-list-shape.md) (two tables, not
  three: `DodaciList(current_version)` + `DodaciListEmailLog`; per-
  (branch, year) `DodaciListNumberSequence` row allocated under
  `SELECT … FOR UPDATE`; live FK to Customer, no snapshot fields —
  supersedes the three-table hint in
  [`0007`](./decisions/0007-auto-reissue-corrected-dodaky.md) §
  Consequences; 0007 banner added),
  [`0037`](./decisions/0037-settings-singleton.md) (singleton via
  `singleton_key` + `UniqueConstraint`; `Settings.load()`
  classmethod; plaintext `smtp_password` with
  `PasswordInput(render_value=False)` and "empty input keeps
  existing value" semantics; `FileField` logo under `MEDIA_ROOT`).
  New models: `inventory.DodaciList` (cislo unique,
  `(branch, year_issued, counter)` unique, counter/version
  positive checks, `is_edited` + `total_quantity_kg` properties,
  live FK to Customer per 0036),
  `DodaciListEmailLog` (status ∈ {sent, failed}, version positive
  check, ordering `(dodaci_list_id, sent_at, id)` for screen 09),
  `DodaciListNumberSequence` ((branch, year) unique;
  internal — not registered in admin),
  `Settings` (singleton; full field list per `screens/14`; defaults
  Matej-ratified — recipient pair left blank intentionally).
  `inventory/services.py` extended with `_assert_recipients_set`,
  `_reserve_dodak_number`, `_create_dodaci_list_for_movement`,
  `render_dodaci_list_pdf` (WeasyPrint 69, CSS Paged Media,
  DejaVu Sans), `send_dodaci_list_email` (try/except wrapped per
  [`0019`](./decisions/0019-email-smtp-sync.md) — failure writes a
  FAILED log row, never re-raises). `apply_movement` for kind=vydej
  reserves cislo + creates dodák + renders PDF inside the atomic
  block; the SMTP send fires from `transaction.on_commit` so a
  later rollback never sends. `edit_movement` replaces the
  `# TODO Pass 2` marker: on a linked dodák, bumps
  `current_version`, re-renders, queues `[OPRAVA]` send. Template
  `kasia/templates/inventory/dodaci_list.html` with embedded CSS
  Paged Media (header + N/M footer + signature line "Předal /
  Převzal"); conditional šarže / poznámka columns computed in the
  service. Management command `generate_dodaci_list <movement_id>
  [--output path]` — auto-creates the dodák row if missing
  (WeasyPrint smoke before screens 07 / 09 land). Admin: `DodaciListAdmin`
  read-only + "Znovu odeslat" action, `DodaciListEmailLogAdmin`
  read-only, `SettingsAdmin` (singleton — add gated on row count,
  delete forbidden; password field write-only; fieldsets per
  screen 14). `MEDIA_URL` / `MEDIA_ROOT` added to
  `kasia/settings/base.py`. Migrations:
  `inventory/0004_dodaci_list_and_settings`,
  `inventory/0005_seed_settings`. Tests: 25 new in
  `inventory/tests.py` (schema constraints, numbering atomicity
  across branches/years, vydej auto-create + PDF render + outbox
  + sent log + failed-send fallback, edit re-issue + rollback
  guard, prijem skips hook, management cmd PDF bytes, admin add
  forbidden / resend action / read-only logs). `conftest.py` adds
  `settings_with_recipients` autouse fixture (sets recipient pair
  for all tests) and converts `tyn` / `sez` / `ricany` fixtures to
  `get_or_create` so `transaction=True` tests survive flush.
  Full suite: **63 pytest tests green**; ruff clean; SQLite
  migrate clean; management-cmd smoke `TYN-2026-0001.pdf` =
  12 228 B starting `%PDF-1.7`. Pass 1's vydej-touching tests
  pick up the recipient fixture transparently — no assertions
  weakened.

- **2026-06-12** — Pass 3a (view layer foundation + screens 06 +
  07) landed. Auth path: Django built-in `LoginView` +
  `LogoutView` at `/login/` and `/logout/`; new
  `LoginRequiredMiddleware` (Django 5.1+) makes every URL
  protected by default — `healthz` opts out via
  `@login_not_required`. `LOGIN_URL`, `LOGIN_REDIRECT_URL`,
  `LOGOUT_REDIRECT_URL` set in `kasia/settings/base.py`.
  URL conf: `inventory/urls.py` with `app_name = "inventory"`;
  routes `/` (home), `/prijem/novy/`, `/vydej/novy/`,
  `/pohyby/<pk>/` (saved confirmation), plus
  `/_partials/line-row/` and `/_partials/stock-warn/` for HTMX
  endpoints. `inventory/views.py` filled with `home`,
  `prijem_create`, `vydej_create`, `movement_saved`,
  `line_row_partial`, `stock_warn_partial`. `inventory/forms.py`
  introduced: `PrijemForm`, `VydejForm`, `MovementLineForm` +
  `formset_factory(min_num=1, validate_min=True, can_delete=True)`;
  branch staff have their branch FK pre-filled + disabled, výdej
  defaults to the `is_default_recipient=True` Customer (Říčany).
  Templates under `kasia/templates/`: `base.html` (Czech header
  nav, flash messages, htmx attribute defaults for CSRF), Czech
  `registration/login.html`, `inventory/home.html`,
  `inventory/movement_saved.html`, `inventory/prijem_form.html`,
  `inventory/vydej_form.html`, `_movement_form_lines.html`
  formset partial, `_line_row.html` (one row — `hx-get` stock
  warn on výdej only), `_stock_warn.html` (HTMX swap target).
  htmx 2.0.4 vendored at `kasia/static/vendor/htmx.min.js` per
  [`0018`](./decisions/0018-frontend-htmx.md) +
  `kasia/static/vendor/README.md` (source + licence).
  Smoke-tested end to end against a local SQLite dev server:
  anon `/` → 302 to login → POST → 302 home; příjem POST →
  Movement #1 + Stock incremented + `/pohyby/1/` confirmation;
  výdej POST → Movement #2 + `DodaciList(TYN-2026-0001)` +
  e-mail queued + confirmation page renders the dodák číslo;
  HTMX partials return correct fragments (add-row at index N,
  stock-warn with on-hand from DB). 14 new tests in
  `inventory/tests.py` (anon redirect, healthz public, login
  Czech text + success redirect, home + prijem GETs, prijem
  POST creates movement / empty lines error, vydej POST creates
  dodák / overdraw keeps form, line-row partial echoes index,
  stock-warn partial over+under cases, partial routes require
  login). Full suite: **77 pytest tests green** (63 → 77); ruff
  clean; system check clean; makemigrations --check clean.

- **2026-06-12** — Pass 3b (dodák list / detail / PDF / resend +
  movement edit) landed. New URL routes under `inventory:`:
  `/dodaky/` (`dodaci_list_index`), `/dodaky/<cislo>/`
  (`dodaci_list_detail`), `/dodaky/<cislo>/pdf/`
  (`dodaci_list_pdf`), `/dodaky/<cislo>/znovu-odeslat/`
  (`dodaci_list_resend`, POST-only), `/pohyby/<pk>/upravit/`
  (`movement_edit`). `vydej_create` now redirects to the dodák
  detail per screen 07 spec ("Lands the user on Detail dodacího
  listu"). Forms: `MovementEditLineForm` (subclass of
  `MovementLineForm` adding a hidden `line_id` field for diffs),
  `MovementEditLineFormSet` (extra=1, can_delete=True),
  `PrijemEditForm` + `VydejEditForm` (share `_MovementEditBaseForm`
  with mandatory `reason`). View logic: `_movement_field_changes`
  + `_line_changes` diff the bound formset against the live
  Movement and produce the `changes` / `line_changes` shape
  `edit_movement` expects; service-layer
  `ValidationError` (e.g. stock overdraw) surfaces as non-form
  errors on the formset. Templates:
  `inventory/dodaci_list_index.html` (filter strip — branch /
  year / "Pouze editované" — and table with PDF quick-link),
  `inventory/dodaci_list_detail.html` (metadata, lines, "Verze a
  odeslání" audit table from `email_logs`, "Editováno" banner,
  "Stáhnout PDF" + "Znovu odeslat" + "Otevřít výdej" controls),
  `inventory/movement_edit.html` (header + linked-dodák
  `[OPRAVA]` warning, edit form, full audit trail from
  `MovementAudit`). Nav extended with "Dodací listy" link;
  `movement_saved` page links to `movement_edit`. End-to-end
  smoke against the dev server: výdej POST → 302 to
  `/dodaky/TYN-2026-0001/`; detail page renders + links to PDF +
  edit; PDF route returns `Content-Type: application/pdf` +
  `Content-Disposition: inline; filename="TYN-2026-0001.pdf"` +
  `%PDF-1.7` magic; edit POST with `reason=oprava hmotnosti`
  bumped `current_version` 1 → 2, wrote a `MovementAudit` row,
  and queued the `[OPRAVA]` send (logged as `version=2,
  trigger_reason="oprava: oprava hmotnosti"`); Znovu odeslat POST
  wrote a `trigger_reason="ruční opětovné odeslání"` row.
  14 new tests in `inventory/tests.py` (dodák list empty / lists
  dodák / branch filter, detail renders, PDF download header +
  bytes, resend writes log row, login-required gate on
  /dodaky/* routes, 404 for unknown číslo, movement_edit GET
  renders + linked-dodák warning, POST bumps version + audits +
  queues OPRAVA send, no-op edit writes no audit, overdraw keeps
  form, 404 for unknown pk, vydej_create now redirects to dodák
  detail). Full suite: **91 pytest tests green** (77 → 91);
  ruff clean; system check clean; makemigrations --check clean.

- **2026-06-12** — Pass 3c (screen 02 dashboard) landed. The
  post-login landing replaces the placeholder home view with a
  real owner dashboard per `screens/02-prehled-vlastnik.md`:
  - **Top action strip** with "K vyřešení: N" (or "K vyřešení
    dnes nic není" on a clean morning) + Nový příjem / Nový
    výdej quick actions.
  - **K vyřešení** section — only rendered when there is
    something to surface. Two buckets:
    - *Nedoručené e-maily* — dodáky whose latest send attempt at
      `current_version` is `FAILED` and where no `SENT` log
      exists at `current_version` (drops out automatically once
      a successful re-send lands; matches screen 02's
      "auto-resolution" expectation).
    - *Nedávno editované dodáky* — `DodaciList.current_version
      > 1`, latest 5, with `v{N}` marker.
  - **Two branch panels side-by-side** (TYN + SEZ) — product
    count, total mass on hand (`floatformat:"3"` so kg always
    shows 3 dp under the Czech locale, which otherwise trims
    trailing zeros), top-5 stocks by quantity, last 5 movements
    each linking to `movement_edit`. Empty-state placeholders
    ("Zatím žádné zboží na skladě" / "Zatím žádné pohyby").
  - **Dodací listy k revizi** table — latest 10 across both
    branches, columns Číslo / Datum / Pobočka / Odběratel /
    Verze, with the edited-version cell highlighted; "Celý
    seznam" link to `dodaci_list_index`.
  No role gating yet — every authenticated user lands on this
  dashboard. Branch-staff routing to screen 03 is a future pass
  (the screen exists in the design but isn't built; shadow-run
  per [`0034`](./decisions/0034-shadow-run-before-go-live.md)
  only has Petr + Karolína, both owner-level). Fixed `dodaci_list_index`'s
  awkward triple-form `pluralize` ("dodác{í,ích} list{,y}") to a
  plain "N záznamů"; same for the dashboard "K vyřešení" count.
  6 new view tests in `inventory/tests.py` (clean-morning
  placeholders, branch stock + top products, recent dodáky
  feed, edited-dodák flagged in "K vyřešení", failed-send bucket
  populates / drops on successful re-send, login-required gate
  on `/`). Full suite: **97 pytest tests green** (91 → 97);
  ruff clean; system check clean; makemigrations --check clean.
  End-to-end smoke against the dev server with seeded TYN (2
  products, total 33 kg) + SEZ (1 product, 3,5 kg) + 1 výdej
  edited to v2: dashboard rendered "K vyřešení: 2" with both
  failed-send + editováno entries, both branch panels with top
  stocks, dodáky table with `v2` flag.

- **2026-06-12** — DB locale gate closed. Decision
  [`0038`](./decisions/0038-db-locale-icu.md) picks **ICU
  (`cs-CZ`)** over an extended `locales-all` image, partially
  superseding the LC_COLLATE/LC_CTYPE specifics of
  [`0016`](./decisions/0016-database-postgres.md) (Czech-sort
  intent preserved; mechanism is ICU instead of libc; 0016
  banner added). `compose.yaml` `db` service updated:
  `POSTGRES_INITDB_ARGS` switched to
  `--locale-provider=icu --icu-locale=cs-CZ --locale=C.UTF-8 --encoding=UTF8`,
  the standalone `LANG: cs_CZ.UTF-8` env var dropped. Image stays
  stock `postgres:18-trixie` — no `Dockerfile.db`, no image to
  manage. Verified directly via `docker run` with the new init
  args:
  - `initdb` reports `locale provider: icu`,
    `default collation: cs-CZ`, `LC_*: C.UTF-8` and exits 0 (no
    "invalid locale name" error);
  - `psql … ORDER BY` on the catalogue-shaped sample
    `[Skořice, Anýz, Česnek, Bazalka, Žampion, Šafrán, Řepík,
    Pepř]` returns `Anýz, Bazalka, Česnek, Pepř, Řepík, Skořice,
    Šafrán, Žampion` — correct Czech alphabetic order (Č after
    C, Ř after R, Š after S, Ž after Z);
  - `docker compose config` parses cleanly.
  Operational note: existing `pgdata` volumes initialised under
  the 2026-06-10 neutralised-locale workaround need
  `docker compose down -v` once before the next `docker compose
  up -d db` so the cluster is initialised with the new ICU
  provider. No production cluster exists yet, so this is a
  clean re-initialisation (0038 § Consequences).

- **2026-06-12** — Pass 3d (role gating + branch dashboard,
  screen 03) landed. `accounts.User` grew two properties:
  - `is_obsluha` — `True` iff the user is in the seeded
    `obsluha` group (and not a superuser);
  - `is_vlastnik` — `True` for superusers, for users in
    `vlastnik` (implicit via "not obsluha"), and for the
    *unassigned* default (no group) — so existing admin-created
    accounts continue to land on the owner dashboard without an
    explicit migration step. Branch staff get the `obsluha`
    group explicitly on account creation.

  `inventory.home` now checks role + branch FK and redirects
  `obsluha + has branch` users to `/pobocka/<branch.code>/`
  (screen 03); everyone else still sees the owner dashboard
  (screen 02) — matches the screen-02 spec "branch staff who try
  to reach it are redirected to their own Přehled pobočky".

  New route `/pobocka/<code>/` (`branch_dashboard`) — branch
  name + address, "Stav skladu" table with product search
  (`?q=…` icontains), "nízký stav" / "prázdné" markers on
  small / zero rows, "Nedávné pohyby" (last 15) each linked to
  `movement_edit`, quick-action buttons (Nový příjem / Nový
  výdej). Access rules: vlastník / superuser users may open
  either branch; obsluha users on the other branch see a 403
  with the Czech "Nemáte oprávnění zobrazit tuto pobočku"
  placeholder per the screen-03 spec.

  New conftest fixtures `user_obsluha_tyn` + `user_obsluha_sez`
  (branch-scoped, in `obsluha` group); the existing `user_tyn`
  is now documented as a "generic logged-in user → default
  vlastník" fixture (kept stable so Pass 3a/b/c tests still
  pass). Owner dashboard branch-panel headers are now clickable
  links into the per-branch view.

  13 new tests: `is_vlastnik` / `is_obsluha` property semantics
  (unassigned default, group membership, superuser),
  obsluha-to-branch-dashboard redirect, owner-to-owner-dashboard
  landing, branch dashboard renders with stock + recent
  movements, stock list scoped strictly to this branch (SEZ
  stock invisible on TYN), search filters by product name,
  obsluha forbidden on the other branch (403 + Czech text),
  vlastník can view either branch, 404 on unknown code,
  login-required gate. Full suite: **110 pytest tests green**
  (97 → 110); ruff clean; system check clean;
  makemigrations --check clean. End-to-end smoke against the
  dev server: obsluha login redirects to /pobocka/TYN/; obsluha
  GET /pobocka/SEZ/ returns 403; vlastník login lands on owner
  dashboard with "K vyřešení" + "Dodací listy k revizi".

- **2026-06-12** — Pass 3e (movement history, screen 10) landed.
  New route `/pohyby/` (`movement_history`) — chronological list
  of all movements with full filter strip:
  - branch (vlastník-only; obsluha is silently scoped to their
    own branch and the dropdown is not rendered);
  - kind (`prijem` / `vydej`);
  - date range (`date_from`, `date_to` — ISO format,
    `__gte` / `__lte`);
  - "Pouze editované" — `audit_entries__isnull=False`
    distinct, the surrogate audit-log per the
    `screens/README.md` reconciliation;
  - free-text search across `odberatel.name`,
    `dodavatel.name`, `lines.product.name_cs`, and `note` —
    icontains, distinct.
  Result table: date, kind (color-coded), branch code, line
  summary (first product `+N dalších` for multi-line),
  counterparty, operator, "editováno (N×)" marker, dodák
  číslo (linked) for výdeje. Rows link to `movement_edit`.
  Capped at 200 newest first; the count notes "(omezeno na 200
  nejnovějších)" when the cap kicks in.
  Nav extended with a "Historie" link; branch dashboard gains a
  "Celá historie" link at the bottom of the recent-movements
  block (per screen 03 spec). 10 new view tests: login gate;
  empty state; lists movement with dodák číslo; obsluha strictly
  scoped to own branch (SEZ movements invisible on TYN); kind /
  branch / date-range / "Pouze editované" / search filters;
  obsluha passing `?branch=` is silently ignored. Full suite:
  **120 pytest tests green** (110 → 120); ruff clean; system
  check clean.

- **2026-06-12** — Pass 3f (catalogue, screens 04 + 05,
  read-only) landed. Two new routes under `inventory:`:
  - `/katalog/` (`catalogue_index`) — browse with `q`
    (icontains on `name_cs`), `kind` (raw_spice / mixture),
    `status` (active / archived / all, default active). Per-row
    stock column adapts: vlastník sees "Skladem celkem" summed
    across branches; obsluha sees "Skladem v <branch.code>"
    scoped to their own branch. Mixtures with a recipe show a
    "má recepturu" badge.
  - `/katalog/<int:pk>/` (`product_detail`) — header with type +
    archived marker; per-branch stock table + total row (scoped
    for obsluha); for mixtures, the recipe rendered as
    surovina+podíl with links to each component; for raw spices,
    a "Použito v směsích" section listing mixtures whose recipe
    references this product; recent movements involving this
    product (top 20, branch-scoped for obsluha) linked into
    `movement_edit`.
  Nav extended with a "Katalog" link (leftmost item). Write +
  edit affordances deferred — admin still covers product
  create / archive / recipe edit for the shadow run; pass 3f is
  the read-only operator-facing browse surface. 13 new tests:
  login gate; default active-only filter; archived filter;
  search; kind filter; vlastník total kg vs obsluha branch kg;
  mixture "má recepturu" badge; product detail render for raw
  spice / mixture; "Použito v směsích" cross-link from a raw
  spice; 404 on unknown pk; obsluha stock scoping on the detail
  page. Full suite: **133 pytest tests green** (120 → 133);
  ruff clean; system check clean. End-to-end smoke against the
  dev server: katalog lists 5 seeded products including
  Gulášové koření with the "má recepturu" badge; ?kind=mixture
  filters down to 1; product detail for Oregano shows TYN +
  SEZ stock + "Použito v směsích → Gulášové koření".

- **2026-06-12** — Decision
  [`0039`](./decisions/0039-mixing-job-shape.md) drafted —
  resolves the three operational opens from
  [`../screens/15-michani.md`](./screens/15-michani.md) before
  the míchání code lands:
  - **Reserve vs. consume at start → consume.** Start step
    writes the consume `Movement` immediately; cancel is an
    audited correction. Avoids introducing a "reserved" stock
    concept that has zero other uses.
  - **After-the-fact recording → allow.** UI exposes a
    "Zaznamenat dokončenou dávku" one-shot affordance with
    optional `as_of`; default two-step start → finish still
    the primary path.
  - **Yield loss → delta on produced movement.** Operator
    enters `actual_produced_kg`; loss is `target - actual` and
    derived, not stored separately. Future explicit column is
    an additive migration if reporting needs it.
  Locked-in implementation notes (`MixingJob` +
  `MixingJobLine` tables; recipe ratios snapshotted at start
  per [`0005`](./decisions/0005-mixture-recipe-model.md);
  internal "Míchárna" Customer + Supplier with new
  `is_internal` boolean; `apply_movement` vydej path skips the
  dodák PDF + e-mail hook when
  `movement.odberatel.is_internal`; three new services
  `start_mixing_job` / `finish_mixing_job` /
  `cancel_mixing_job` + a `record_completed_mixing_job`
  one-shot helper) anchor the next code pass; no model /
  service code in this commit. Builds on Pass 1's
  `apply_movement` / `edit_movement` services + the existing
  audit-trail infrastructure.

- **2026-06-12** — Dockerfile hotfix
  ([`4e0216c`](https://github.com/matejformanek/Kasia-warehouse/commit/4e0216c)):
  `COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION}` failed on the
  push-to-main `deploy` workflow with "variable expansion is not
  supported for --from". Fix per the buildx error message:
  pull the uv image into a named stage
  (`FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv_stage`) and
  `COPY --from=uv_stage`. ARG survives in `FROM`, so the version
  pin stays externally configurable. Verified with a local
  `docker build --target runtime .` → all stages exported
  cleanly. The build + push to GHCR now succeeds on CI; the
  remaining `deploy` failure ("missing server host") is the
  expected pre-provisioning state — no `SSH_HOST` secret until
  the Hetzner box exists.

- **2026-06-12** — Pass 4 (míchání, screen 15) landed per
  [`0039`](./decisions/0039-mixing-job-shape.md). Two new
  models in `inventory/0006_mixing_job`:
  - `MixingJob` (branch + mixture + target_qty +
    actual_produced_qty + state ∈ {running, done, cancelled} +
    started_at + finished_at + cancel_reason + note +
    consume_movement FK + produce_movement FK + created_by) with
    CHECK constraints (target > 0, actual_produced >= 0,
    cancel_reason required iff state=cancelled);
  - `MixingJobLine` (per-component snapshot: ratio_at_start
    copied from RecipeComponent at start, derived_qty +
    actual_qty + sarze) with unique (mixing_job, component) +
    positive-qty CHECKs.
  Customer + Supplier each gain an `is_internal` boolean (default
  False). Seed migration 0007 inserts the internal Míchárna
  Customer + Supplier rows. `apply_movement` vydej path gains a
  guard: when `movement.odberatel.is_internal`, the dodák PDF +
  e-mail hook is skipped — mixing-job consume Movements still
  decrement stock and appear in screen 10 history, but no
  customer-facing dodák is generated.
  Four new services in `inventory/services.py`:
  - `start_mixing_job(branch, mixture, target_qty, user, …)` —
    snapshots the recipe, writes the consume Movement via
    `apply_movement` (kind=vydej to Míchárna internal customer),
    stores `consume_movement` on the job, returns
    `state=running`. Refuses non-mixture products, mixtures
    without a recipe, or zero/negative target. Stock-overdraw
    refusal is the existing `_apply_line_to_stock` invariant.
  - `finish_mixing_job(mixing_job, actual_produced_qty,
    line_actuals, user)` — operator-edited line actuals (≠
    derived) get applied via `edit_movement` on the consume
    Movement so the audit trail captures them; if
    `actual_produced_qty > 0`, writes the produce Movement
    (kind=prijem from Míchárna internal supplier) and stores it
    on the job; marks the job done. Handles full-loss case
    (actual_produced = 0 → no produce Movement, still done).
  - `cancel_mixing_job(mixing_job, reason, user)` — calls
    `edit_movement` with line_changes that remove every consume
    line; stock returns to the branch atomically; reason
    required; state → cancelled.
  - `record_completed_mixing_job(...)` — one-shot path per 0039
    that calls start + finish in a single transaction; used for
    after-the-fact recording when the operator forgot to open the
    screen at start.
  Six new URL routes (`/michani/`, `/michani/novy/`,
  `/michani/<pk>/`, `/michani/<pk>/dokoncit/`,
  `/michani/<pk>/zrusit/`, `/_partials/mixing-preview/`),
  templates `mixing_job_index.html` + `mixing_job_create.html`
  (HTMX preview on branch+mixture+target change; start /
  record-completed mode toggle) + `mixing_job_detail.html`
  (finish form with per-line actual edits and produce qty;
  cancel form with required reason) + `_mixing_preview.html`
  (derived consumption table with nedostatek flags). Branch
  scoping: obsluha can only see their own branch's jobs and gets
  403 on the other branch's detail. "Míchání" nav link added
  between Výdej and Dodací listy.
  Admin: read-only `MixingJobAdmin` (no add, no delete; system
  state machine owns writes); read-only `MixingJobLineAdmin`.
  Screen 15 markdown gains a banner pointing at 0039 as
  resolving its three operational opens.
  23 new tests (12 service + 11 view): seed rows exist; internal
  customer skips dodák; start writes consume + snapshot; start
  rejects overdraw / non-mixture / no-recipe; finish writes
  produce + done; finish with line_actuals corrects consume via
  audit; finish with zero produce skips Movement; finish rejects
  non-running; cancel restores stock; cancel requires reason;
  one-shot record_completed; mixing routes require login;
  index empty; create lists only mixtures-with-recipe; start
  POST + record POST + overdraw form-keeps; finish POST; cancel
  POST requires reason; obsluha forbidden on other branch;
  preview partial flags nedostatek. Full suite **156 pytest
  tests green** (133 → 156); ruff clean; system check clean;
  makemigrations --check clean.

- **2026-06-12** — Kasia brand logo landed.
  `kasia/static/brand/kasia-logo.jpg` (white "KASIA" on green
  with a leaf/flag mark; supplied by Petr 2026-06-09). Wired
  into two places:
  - `kasia/templates/base.html` nav: anchored `<a class="brand"
    href="home">` with `<img>` + "sklad" subtitle, replacing
    the plain "Kasia vera · sklad" text.
  - `kasia/templates/inventory/dodaci_list.html`: the bundled
    logo is the new PDF fallback when `Settings.logo` is empty
    (a Petr-uploaded operator override still wins). The path is
    computed in `render_dodaci_list_pdf` as
    `file://{BASE_DIR}/kasia/static/brand/kasia-logo.jpg` and
    passed via `default_logo_url` context — WeasyPrint reads
    from disk, not via the static-files URL. Smoke test:
    `TYN-2026-0001.pdf` grew from 12 228 B → 54 281 B with the
    logo embedded, `%PDF-1.7` magic intact.
  Settings template placeholder text ("Kasia vera s.r.o." in
  the company-name field) is unchanged; the visual brand mark
  in the header replaces the text placeholder that was the
  Matej-ratified MVP default per
  [`screens/14-nastaveni.md`](./screens/14-nastaveni.md) §
  Hlavička. Closes the "Petr's logo files" open question for
  the JPEG; SVG/PDF marks (if Petr ever supplies them) plug in
  the same way via `Settings.logo` upload in admin.

- **2026-06-12** — Screen 13 (Správa uživatelů) landed.
  New `accounts.urls` mounted at `/uzivatele/`; views
  `user_index`, `user_create`, `user_edit`, `user_deactivate`,
  `user_reactivate`, `user_password_reset`. Owner-only:
  `_require_vlastnik` raises `PermissionDenied` (403) for
  obsluha. Forms `UserCreateForm` + `UserEditForm` enforce
  the role/branch rules from
  [`screens/13`](./screens/13-sprava-uzivatelu.md) (obsluha
  must have a branch; vlastník has none; e-mail read-only on
  edit; password mismatch + duplicate-email + Django password
  validators on create) plus the **last-vlastník protection**
  (form-level on demotion, view-level on deactivate). Role
  maps onto Django group membership via `_sync_role` (presence
  of the `obsluha` group ↔ obsluha; absence ↔ vlastník).
  Password reset is handled by Django's built-in
  `PasswordResetForm.save()`. New Czech `registration/`
  templates wired in `kasia/urls.py` for the full reset flow
  (form / done / confirm / complete / email / subject), each
  reachable without login via `@login_not_required`. Nav
  `"Uživatelé"` link added in `base.html` under
  `{% if user.is_vlastnik %}`.
  17 new tests in `accounts/tests.py` (login gate, obsluha
  403, vlastník 200, create vlastník / obsluha / missing-branch
  reject / duplicate-email reject / password-mismatch reject,
  edit role+branch, last-vlastník demotion refused, deactivate
  success / last-vlastník refused, reactivate,
  password-reset sends mail + refused for deactivated, nav
  link shown for vlastník + hidden for obsluha). Autouse
  fixture `_view_overrides` applies plain-staticfiles +
  locmem-email so `base.html` renders under tests. Full suite:
  **173 pytest tests green** (156 → 173); ruff clean; system
  check clean; makemigrations --check clean. No new models, no
  migrations — pure views + forms + templates.

- **2026-06-12** — Screen 14 (Nastavení operator UI) landed.
  New routes under `inventory:` —
  `/nastaveni/` (`settings_edit`) and `/nastaveni/test-smtp/`
  (`settings_test_smtp`, POST-only). Owner-only via the local
  `_require_vlastnik` helper in `inventory/views.py`. Form
  `SettingsForm(ModelForm)` in `inventory/forms.py` mirrors
  `SettingsAdminForm`: excludes `singleton_key`, renders
  `smtp_password` as `PasswordInput(render_value=False)`, blank
  input on edit preserves the existing password. Template
  `kasia/templates/inventory/settings_form.html` lays out the
  four sections per
  [`screens/14`](./screens/14-nastaveni.md) (Společnost +
  hlavička / SMTP / Příjemci / Šablony e-mailů), plus three
  read-only blocks: "Otestovat odeslání" with current-user
  default, "Dodací list — formát" with a per-branch counter
  table (`DodaciListNumberSequence` lookup; "letos ještě nic"
  placeholder if no dodáky issued this year), and "Pobočky"
  with the read-only branch identity table + Říčany footnote.
  Test-SMTP path builds a one-shot `get_connection()` with the
  live `Settings` values and sends a Czech test message; any
  exception is surfaced via Django messages without leaking
  the traceback into the response body. `SmtpTestForm` rejects
  invalid e-mails without sending. Nav `"Nastavení"` link
  added in `base.html` next to "Uživatelé", still gated on
  `{% if user.is_vlastnik %}`. 11 new tests in
  `inventory/tests.py` (login gate, obsluha 403, vlastník
  renders all section headers, save updates company fields +
  preserves singleton, blank password preserves stored value,
  test-SMTP sends to target / forbidden for obsluha / rejects
  invalid e-mail, branch-counter table shows the latest číslo
  preview, nav link shown for vlastník + hidden for obsluha).
  Full suite: **184 pytest tests green** (173 → 184); ruff
  clean; system check clean; makemigrations --check clean. No
  new models, no migrations — pure views + form + template.
  Smoke-tested in the running docker stack:
  `GET /nastaveni/` returns 200, all four section headers and
  the "Otestovat odeslání" button render correctly.

- **2026-06-12** — Local dev switched to **full docker compose
  stack** (web + db + caddy proxy), not `manage.py runserver`
  against a standalone Postgres. Added top-level `Makefile`
  with `up / down / wipe / build / logs / shell / psql /
  migrate / superuser / test / ps` targets — `make up` builds
  the image (multi-stage per
  [`0022`](./decisions/0022-container-image.md)), brings up
  `db` (PG18 + ICU `cs-CZ`), runs `migrate --noinput`, then
  starts `web` + `proxy`. Local `.env` (gitignored) sets safe
  local defaults (`DJANGO_DEBUG=1`, throwaway secret key,
  blank SMTP). `make superuser` creates
  `admin@kasia.local / heslo1234`. End-to-end verified against
  the running stack: `/uzivatele/` returns 200 to the seeded
  superuser; the schema works on PG18 + ICU; Caddy proxy
  serves the app on `http://localhost/`. The runtime image is
  `--no-dev` so it has no pytest; `make test` runs the suite
  on the host (uv) against SQLite, matching existing CI
  behaviour. Same image we ship to Hetzner — local and prod
  are now byte-identical except for `.env`.

- **2026-06-12** — Local walkthrough feedback → 5 UX hotfixes
  (`b071edb` → `7b84cb3`):
  B1 příjem/výdej formset extra=0 (1 row default, not 2);
  B2 visible "× Smazat" button replacing hidden checkbox;
  B3 mixing "Nová dávka" CSS fix (.primary works on `<a>`);
  B4 HTMX previews stop sending `target_qty=undefined`
  (`hx-vals` → `hx-include="closest form"`);
  B5 stop sending CSRF token twice in HTMX URLs (drop
  body-level `hx-include` of csrfmiddlewaretoken).

- **2026-06-12** — Visible improvements batch
  (`e6d3e93` → `b3f0fed`):
  P1 required-field markers + "* povinné" legend on all 6
  operator forms; P4 whole-row clickable
  (`tr.row-link[data-href]` + delegated click handler) in
  Historie, owner + branch dashboards, Dodáky list, Katalog;
  K1 `?branch=<CODE>` filter on `/katalog/` (vlastník only;
  obsluha auto-scoped) with column header that switches to
  "Skladem v TYN (kg)" when scoped; K6 recipe scaling
  calculator on mixture detail (`/katalog/<id>/` shows
  "Spočítat dávku" with target input → live per-component
  derived kg); D1+M4 `make seed` + `seed_walkthrough_data`
  management command generating 3 příjmy + 5 výdejů + 1
  edited dodák so Historie / Dodáky have real content for
  walkthrough.

- **2026-06-12** — **Pass 5 — operator-facing CRUD**
  (`828f204` → `59a5b6b` → Pass 5e). Migrates every
  admin-only entity into the Czech operator app per walkthrough
  feedback ("everything in admin should be in the app, with
  per-user permissions"). New decisions:
  - [`0040`](./decisions/0040-operator-crud-tiering.md) —
    two-tier-per-entity gating. Suppliers / Customers /
    Products (fields) = all authenticated; Recipes /
    Branches / Stock direct edit / Product archive =
    vlastník-only. Forward-compatible to a third tier.
  - [`0041`](./decisions/0041-manual-stock-adjustment.md) —
    direct Stock edits go through a synthetic Movement with
    `[STAV] ` note prefix and an internal
    "Inventura / ruční úprava" counterparty pair (seeded by
    migration `0008_seed_adjustment_counterparty`). Never raw
    UPDATE on `Stock.quantity`; every delta flows through
    `apply_movement` → `MovementAudit` like any other movement.
    Internal `is_internal=True` so the dodák hook is skipped.

  **Pass 5a — Supplier + Customer CRUD** (all users):
  `/dodavatele/` + `/odberatele/` with create / edit /
  archive / reactivate. Soft-uniqueness on active name;
  internal Míchárna pair hidden + protected from archive;
  default-recipient Říčany protected from archive (per
  [0030](./decisions/0030-vydej-default-ricany-supersedes-0004.md)).
  Nav links "Dodavatelé" + "Odběratelé" visible to all.

  **Pass 5b — Product + Recipe CRUD**: `/katalog/novy/` +
  `/katalog/<pk>/upravit/` + archive/reactivate. Product
  fields = all users. Kind field auto-locks once Stock or
  recipe references exist. **Recipe edit (RecipeComponent
  inline formset) is vlastník-only** (per
  [0005](./decisions/0005-mixture-recipe-model.md)
  domain-knowledge ownership). Vlastník creating a mixture
  is redirected straight to recipe edit. "+ Nový produkt"
  on catalogue index, "Upravit produkt" on product detail
  (+ "Archivovat / Aktivovat" card for vlastník).

  **Pass 5c — Branch CRUD** (vlastník-only): `/pobocky/` +
  create / edit / archive. Code validates `[A-Z]{3}` and is
  locked once any DodaciList exists from that branch (per
  [0008](./decisions/0008-dodaci-list-numbering.md)). Archive
  refused when branch still has positive Stock or active
  users. "Pobočky" nav link gated to vlastník.

  **Pass 5d — Stock direct edit** (vlastník-only):
  `/katalog/<pk>/upravit-stav/` + new
  `apply_stock_adjustment(...)` service that builds a
  synthetic Movement (prijem for positive delta, vydej for
  negative; zero = noop). Internal "Inventura / ruční
  úprava" counterparty pair seeded by
  `inventory/0008_seed_adjustment_counterparty.py`.
  `conftest.py` autouse seed extended to re-seed both
  internal pairs (Míchárna + Inventura) after transactional
  flush.

  **Pass 5e — Bulk inventura editor** (vlastník-only):
  `/katalog/inventura/<code>/` — walk every product at one
  branch, type the new quantities, hit "Uložit všechny
  změny". Each non-zero delta = one `apply_stock_adjustment`
  call sharing the batch reason. Zero-deltas skipped. JS
  shows a live "Rozdíl" column. Entry point: "Inventura
  TYN" button next to "+ Nový produkt" on `/katalog/?branch=…`
  (vlastník only).

  234 → **242 pytest tests green** through the whole Pass 5
  (200 → 213 → 225 → 234 → 242 across 5a/b/c/d/e). Ruff
  clean throughout. One new data migration (`0008`).

- **2026-06-13** — Pass 5f — overdraw guided correction
  (per new decision
  [`0042`](./decisions/0042-overdraw-guided-correction.md)).
  Matej's answer to the open overdraw question: prompt the
  operator to fix stock, don't just refuse. `vydej_create`
  now pre-checks all lines against current Stock before
  calling `apply_movement` and surfaces a structured
  "Nedostatek na skladě" card listing every short item with
  current / requested / shortfall + a per-row
  "Upravit stav skladu ↗" button (vlastník-only — opens
  `/katalog/<pk>/upravit-stav/` in new tab). Obsluha sees
  the same warning without the button ("jen vlastník"
  marker). Multi-row same-product entries are aggregated so
  two 6 kg rows of Pepř against 10 kg stock surface a single
  2 kg shortfall. After running `apply_stock_adjustment` (or
  bulk inventura) the same výdej payload goes through on the
  next submit. `conftest._ensure_micharna_seed` extended to
  also re-seed the Říčany default-recipient Customer after a
  transactional flush (broke once Pass 5f tests started
  looking it up by `is_default_recipient=True` without
  naming `ricany` as a fixture argument). 247 pytest tests
  green (242 → 247).

- **2026-06-13** — Pass 5g — Historie redesign (judgment call,
  per Matej's "dle preferencí co ti budou dávat smysl").
  `/pohyby/` gets a row of **tab chips** above the filter
  card: **Vše / Příjmy / Výdeje / Inventura / úprava stavu /
  Editováno**. Each chip carries a live count badge against
  the current branch + date + q filter so the operator can
  see at-a-glance how many of each kind are in the current
  scope. Active chip styled with `.primary` color. Free-text
  q + date + branch filters still work and combine with the
  chip (the chip narrows kind). Legacy `?kind=` and
  `?edited=1` URL params still resolve to the right tab so
  bookmarked links keep working. `[STAV]` movements in the
  table get a dedicated "inventura" badge in the Druh column
  (orange, replacing the generic prijem badge) so they're
  visually distinct from regular příjmy/výdeje. The
  "Pouze editované" checkbox was removed — it's now the
  "Editováno" tab. 252 pytest tests green (247 → 252).

- **2026-06-14** — Reorder threshold + reservations (planned mixing
  + planned transfers) landed: decisions
  [`0043`](./decisions/0043-reorder-threshold.md),
  [`0044`](./decisions/0044-reservations-planned-states.md),
  [`0045`](./decisions/0045-low-stock-summary-email.md). New
  models: `inventory.Product.reorder_threshold_kg`,
  `inventory.StockThresholdOverride` (per-branch override),
  `inventory.MixingJob` extended with `PLANNED` state +
  `planned_for` field, `inventory.PlannedTransfer` (one row per
  scheduled branch↔branch transfer + `Movement.transfer` FK back),
  `inventory.Settings` gains `template_low_stock_subject` +
  `template_low_stock_body`. Two new migrations:
  `inventory/0009_threshold_and_reservations.py` +
  `inventory/0010_seed_transfer_counterparty.py` (seeds the
  "Převod mezi pobočkami" `Customer`+`Supplier` pair with
  `is_internal=False` — so the existing dodák auto-issue +
  e-mail hook fires on the výdej leg per 0007/0030/0031).
  Services: `threshold_for`, `reserved_kg`, `effective_kg`,
  `low_stock_rows`, `plan_mixing_job`, `start_mixing_job(job=…)`
  (PLANNED→RUNNING), `execute_planned_transfer`,
  `cancel_planned_transfer`, `send_low_stock_summary`.
  `cancel_mixing_job` extended to also accept PLANNED (no
  consume_movement yet, just flip state). Views: owner dashboard
  gains the "Dochází zboží" panel reading `low_stock_rows`;
  branch dashboard gets threshold-aware badges (`prázdné`/`dochází`/normal)
  replacing the hardcoded `< 1 kg` marker; product detail surfaces
  per-branch reserved + effective vs threshold; product edit form
  exposes `reorder_threshold_kg` + inline `ThresholdOverrideFormSet`
  in a `{% if user.is_vlastnik %}` block (form drops the field
  for non-vlastník so a worker POST doesn't null out the value).
  New `/prevody/` CRUD surface (index, create, detail, execute,
  cancel) — all authenticated users per Matej 2026-06-14. New
  `/michani/planovat/` + `/michani/<pk>/spustit/` for the PLANNED
  flow. Nav: "Převody" link added between Míchání and Dodací
  listy. Management command
  `inventory/management/commands/mail_low_stock_summary.py` +
  `make mail-low-stock` target. Admin: `PlannedTransferAdmin`
  (read-mostly) + `StockThresholdOverrideAdmin` (full CRUD).
  Conftest re-seeds the "Převod mezi pobočkami" pair after
  transactional flush. `seed_walkthrough_data` extended to create
  one demo PlannedTransfer + one PLANNED MixingJob + 5 kg threshold
  on Oregano (idempotent). 21 new tests appended in
  `inventory/tests.py` covering threshold lookup, reservations
  (planned/running/cancelled mixing + outgoing-only transfers),
  effective_kg, low_stock_rows sort + skip-without-threshold,
  plan_mixing_job no-stock-touch, PLANNED→RUNNING transition,
  execute_planned_transfer dodák hook, refuse-non-planned,
  cancel + no-stock-change, overdraw unchanged by reservations,
  daily summary empty/populated, threshold field tier gating,
  /prevody/ create + index, dashboard panel renders. Glossary:
  new `objednací bod` headword; `rezervace` rewritten to point
  at 0044. Screen 02 + 03 + 15 docs updated. 0039 banner added
  (only permitted edit per append-only rule). Full suite
  **273 pytest tests green** (252 → 273); ruff clean; system
  check clean; makemigrations --check clean.

- **2026-06-15** — Quality-of-life backlog landed (three small items
  off the § Next list):
  - **`[STAV]` reason surfaced in Historie** (per 0041 § Forward
    references): the Položky column now renders an italic muted
    `„<reason>` line for every `[STAV] …` movement so vlastník sees
    *why* without clicking through to detail. The existing
    "inventura" badge in the Druh column stays — this just adds the
    `note`-after-prefix on the row inline.
  - **Inline "+ Nový dodavatel" / "+ Nový odběratel" affordance** on
    the příjem/výdej forms (`prijem_form.html` + `vydej_form.html`).
    Opens `/dodavatele/novy/` or `/odberatele/novy/` in a new tab so
    the worker doesn't lose the half-filled movement form.
  - **`CLAUDE.md` (worktree root) refreshed** — previous version
    still said *"No application code exists yet"*, which became
    false at Pass 1. Rewritten to point at `context/state.md` +
    `context/decisions/` first, document the locked stack
    (0014–0027 + 0028–0034 + 0044), the `make up` posture, and that
    the Hetzner box is not yet provisioned (the failing `deploy.yml`
    SSH step is expected). Full suite **273 pytest tests green**
    (unchanged — pure template + docs edits); ruff clean; system
    check clean.

- **2026-06-16** — Hetzner provisioning **§ 1 complete**. Box is
  live at **`91.98.47.1`** (IPv6 `2a01:4f8:c012:b651::1`),
  CPX22 in `fsn1`, Ubuntu 24.04. Resources via `terraform apply`
  (saved-plan flow): `hcloud_ssh_key.admin`, `hcloud_firewall.kasia`,
  `hcloud_server.web`, `hcloud_firewall_attachment.web`.
  - Repo flipped to **public** via `gh repo edit … --visibility public`
    (no secrets in code per infra-as-code rule; cleaner than wiring
    a deploy key on the box). Cloud-init clone now works anonymously.
  - Cloud-init done (`status: done, degraded`). Recoverable warning
    only: `sudo: false` deprecated → `null`. Now fixed in
    `cloud-init.yaml` along with seeding `/home/app/.ssh/authorized_keys`
    from root's (needed because deploy.yml SSHes as `app`).
  - Firewall: SSH 22 **relaxed to 0.0.0.0/0** (key auth is sufficient
    at the small-business shape; Matej moves networks too often to
    pin source); 80, 443, ICMP open to world.
  - `/srv/kasia/.env` populated on the box. Secrets generated
    **server-side via `python3 -c "import secrets..." | sed`** —
    never round-tripped through agent context.
    - Filled: SECRET_KEY (86 chars), POSTGRES_PASSWORD (64 chars),
      ALLOWED_HOSTS=91.98.47.1, DEBUG=0, DEFAULT_FROM_EMAIL.
    - Blank pending decisions: RESTIC block (Storage Box not ordered).
  - `deploy.yml` simplified: `SSH_HOST` + `SSH_USER` removed from
    GH secrets (hardcoded `host: 91.98.47.1`, `username: app` as
    literals — non-secret). **Only `SSH_KEY` is now a GH secret;
    Matej has set it.** Re-IPing the box → edit the workflow, no
    secret rotation.
  - First terraform plan misread `185.63.99.81` as Cloudflare's
    `104.28.x.x` via `ifconfig.me` → switched to `api.ipify.org`.
    Worth knowing for future plans.

  **Pending (§ 2 follow-ups):**
  - Push these changes (cloud-init hygiene + deploy.yml literals +
    RUNBOOK + state.md) → triggers first deploy. Build → push to
    GHCR → SSH deploy as app → migrate → up -d.
  - First superuser: `docker compose run --rm web python manage.py
    createsuperuser --noinput` after deploy succeeds (Matej picks
    the admin password — never enters agent context).
  - SMTP provider decision (deferred). Without it, dodák e-mails
    and the daily low-stock summary are silent no-ops.
  - Hetzner Storage Box BX11 + restic backups (deferred).
  - Cron entry for `mail_low_stock_summary` (deferred — needs cron
    decision and a few days of real data anyway).

- **2026-06-16** — Podpora page landed (`/podpora/`). In-app docs
  (per-screen reference + 6 workflows + 11 tips in `<details>`
  accordions), feedback log model `inventory.Feedback`, vlastník-only
  resolved toggle. Decision
  [`0046`](./decisions/0046-support-page.md). Migration
  `0011_feedback` (additive, no data seed). New screen doc
  [`screens/16-podpora.md`](./screens/16-podpora.md); glossary entry
  `hlášení` added; `base.html` got the new "Podpora" nav link plus
  `<details>` accordion CSS. 9 new tests (anon redirect, GET +
  POST + validation, optional page_url, vlastník toggle resolve +
  re-open, obsluha rejection, all-users visibility). Full suite:
  **282 pytest tests green**; ruff clean; system check clean.

- **2026-06-24** — Homepage visual exploration gallery built under
  `design-options/` (exploration scratch — production `base.html` /
  `home.html` untouched). **18** fully standalone HTML mockups of the owner
  dashboard, all rendering identical realistic Czech sample data (TYN +
  SEZ, real spice products, plausible odběratelé) so Petr compares
  *style* not content. Set one (bespoke, 10): 6 minimalist (mono,
  swiss-grid, warm, green-brand, dark, airy-editorial), 2 modern
  (soft-cards, editorial-type), 2 old-school (classic-serif, bordered-erp).
  Set two (inspired by popular products, 8): Linear, Stripe, Notion,
  Vercel, Shopify, Apple, GitHub, Airbnb. Plus `index.html` two-group
  live-thumbnail gallery, `README.md`, and self-contained `assets/`
  (logo + favicon). Verified: all 20 routes 200 over `http.server`, no
  Django tags, no external refs except Google Fonts, diacritics + sample
  data consistent across all 18. Next: Petr picks a direction → log a
  `decisions/NNNN-*.md` → separate port task into the real templates.

- **2026-06-24** — Design-review gallery now served publicly on prod for
  Petr's review, per
  [`decisions/0047`](./decisions/0047-design-review-gallery.md) (amends
  [`0020`](./decisions/0020-auth-django-builtin.md)). `design-options/`
  added to `STATICFILES_DIRS` under the `navrhy` prefix → WhiteNoise serves
  it at `/static/navrhy/` (public, pre-auth); `login_not_required` redirect
  at `/navrhy/` is the shareable entry point. Source stays top-level
  (versioned design history). Verified locally with DEBUG=False: `/navrhy/`
  302→ gallery, static files 200 via WhiteNoise, real app pages still
  302→login; `collectstatic` clean; ruff clean; **282 tests green**.
  Reaches prod on next push to `main` (build runs `collectstatic`, image
  already copies `design-options/`). Temporary surface — remove the
  `navrhy` static entry + `/navrhy/` redirect when the chosen homepage
  ports into real templates.

- **2026-06-24** — XLS recipe importer landed
  (`/katalog/import-xls/`). Vlastník-only upload → editable review
  → atomic confirm; auto-creates missing raw-spice Products
  (casefold dedupe against existing catalogue). Parser handles
  `.xls` (xlrd, in-memory) + `.xlsx` (openpyxl, `data_only=True,
  read_only=True`, in-memory). Ratios computed from kg and
  normalised so the sum is exactly `Decimal("1.000000")`; rejects
  zero-ratio edge cases with a Czech message naming the offender.
  Decision [`0048`](./decisions/0048-xls-recipe-importer.md)
  (originally drafted as 0047 — renumbered on merge after the
  design-review gallery shipped 0047 on `main` first; numbering is
  monotonic per `.claude/rules/decision-log-discipline.md`).
  Screen doc [`screens/17-xls-import.md`](./screens/17-xls-import.md).
  New deps `openpyxl` + `xlrd` (both pure-Python). 14 new tests
  (4 parser, 3 view-permission, 1 upload-renders-review, 1 confirm
  creates, 1 casefold-dedupe, 1 duplicate-mixture refusal, 1
  zero-ratio rejection, 2 catalogue-button visibility); full suite
  green. Fixture `inventory/tests/fixtures/touzimsky.xls` (Petr's
  real Toužimský knedlík recipe, ~33 KB).

- **2026-06-24** — In-app password change wired
  (`/accounts/zmena-hesla/` → `PasswordChangeView`,
  `/accounts/zmena-hesla/hotovo/` → `PasswordChangeDoneView`).
  Mounted in `kasia/urls.py` (NOT `django.contrib.auth.urls`
  wholesale — would collide with the custom `/login/` + `/logout/`).
  New templates under `kasia/templates/registration/`. "Změnit
  heslo" nav link added to `base.html`. 2 new tests (anon redirect,
  vlastník POST updates password). Unblocks the three real
  operators changing their initial out-of-band passwords without
  needing SMTP (which is still deferred — Matej will check
  whether the kasia.cz mail host gives SMTP creds; see
  [`0019`](./decisions/0019-email-smtp-sync.md)).

- **2026-06-24 (pending operator step, out of code scope)** — Real
  prod users to be added by Matej + Karolína: Karolína (vlastník,
  `karolina@kasia.cz`), Týniště obsluha
  (`objednavky@koreni-gastro.cz`), Sezimák obsluha
  (`obchod@cervenkajiri.cz`). Initial passwords handed
  out-of-band; users self-service via `/sklad/zmena-hesla/`
  (moved from `/accounts/zmena-hesla/` by 0049).
  `Settings.recipient_petr` = `petr@kasia.cz`,
  `Settings.recipient_karolina` = `karolina@kasia.cz` (needed
  before any real customer výdej, per the `_assert_recipients_set`
  guard in `inventory/services.py`).

- **2026-06-28** — Podpora feedback Batch D landed (Feedback #2b — N-list
  recipients) per new decision
  [`0052`](./decisions/0052-n-list-recipients-supersedes-0031.md)
  (supersedes [`0031`](./decisions/0031-emails-internal-only-supersedes-0009.md)
  in part — "internal only" intent stands; the fixed-pair UI and schema
  shape are replaced). New `SettingsRecipient` model — `(email, label,
  is_active, is_low_stock_recipient, sort_order, created_at)` with
  case-insensitive `UniqueConstraint(Lower("email"))`. Single atomic
  migration `0012_settings_recipients_table.py`:
  CreateModel → RunPython data-migration (idempotent, seeds Petr +
  Karolína from old Settings columns, sets Petr `is_low_stock_recipient
  =True` per 0045) → drops both `Settings.recipient_*` columns.
  Service refactor in `inventory/services.py`:
  - `_assert_recipients_set` now requires ≥1 active SettingsRecipient
    row; Czech error string updated.
  - `send_dodaci_list_email` ships to all active recipients ordered
    by `sort_order, id`.
  - `send_low_stock_summary` ships to all active recipients with
    `is_low_stock_recipient=True`; returns `None` (no raise) when
    none are subscribed (matches `_assert_recipients_set`'s no-raise
    posture for the daily cron path).
  UI: `/nastaveni/` "Příjemci dodacího listu" block becomes a
  modelformset using the project's existing JS-clone `<template>`
  add-row pattern from `product_form.html:159-214` (NOT HTMX). Per-row
  controls: email, label, is_active, is_low_stock_recipient,
  sort_order, "× Smazat" button. Read-only `SettingsRecipientAdmin`
  added.
  Conftest autouse fixture rewritten to seed Petr + Karolína as
  SettingsRecipient rows. 6 existing test references migrated
  (`tests.py:855`, `:2576`, `:3093-3163`, `:4993`, `:5752`) +
  `seed_walkthrough_data` + `mail_low_stock_summary` management
  command + `inventory/admin.py` fieldset.
  9 new tests: case-insensitive uniqueness; iterates all active;
  skips inactive; refuses zero-active (ValidationError); low-stock
  targets subscribed only; low-stock returns None with no
  subscribers; formset renders existing rows; formset creates new
  row via POST; data-migration helper is idempotent.
  Screen docs `14-nastaveni.md` + `09-detail-dodaciho-listu.md`
  updated. Full suite **321 pytest tests green** (312 → 321 = 1
  removed via Batch C cleanup + 1 removed `recipient_petr` test +
  9 new + 0 net = math check below). Ruff clean; system check clean;
  makemigrations --check clean.

- **2026-06-28** — Podpora feedback Batch B landed (Feedback #4 — catalogue
  per-branch low-stock visibility, N-branch ready). `catalogue_index` view
  collects `low_branches` per row (branches where `effective < threshold`).
  Template gains a new "Nízký na" column rendering one branch-code chip
  per failing branch, but only when no single branch is in scope (the
  existing "dochází" badge already covers the single-branch case). Copy:
  "obě pobočky" → "všechny aktivní pobočky" in three places (filter
  option, "Zobrazit ..." link, scope hint). Reuses the same
  `reserved_kg` + `threshold_for` helpers that feed the dashboard "Dochází
  zboží" panel; no new services. Existing test at `:2421` updated
  ("obě pobočky" → "všechny aktivní pobočky"). 4 new tests: chip shows
  for failing branch only; third active branch proves N-branch genericity
  (creates HRA); `?branch=` filter empties the chip column; obsluha
  (implicit single-branch) empties the chip column. Screen doc
  `04-katalog-produktu.md` updated. Full suite **312 pytest tests green**
  (308 → 312); ruff clean; system check clean.

- **2026-06-28** — Podpora feedback Batch C landed (Feedback #2a — settings
  recipient save bug). Root cause: `settings_form.html` renders fields via
  per-section whitelists (`{% if f.name == "..." %}`). The
  `template_low_stock_subject` + `template_low_stock_body` fields added in
  decision [`0045`](./decisions/0045-low-stock-summary-email.md) were in
  none of the four sections, so the browser's POST stripped them; ModelForm
  flagged both required (no `blank=True`); validation silently failed
  (errors weren't visible because the fields are also iterated nowhere);
  Karolína's recipient change never persisted and no error appeared.
  Fixes:
  - Added both `template_low_stock_*` fields to the "Šablony e-mailů"
    section's whitelist (their natural home).
  - Added a defensive top-of-form `{% if form.errors %}` banner so any
    future "field added but template not updated" mistake surfaces
    immediately instead of silently failing.
  2 new tests: form-renders-every-field guard (future regressions trip
  before reaching prod); recipient change persists via browser-shaped
  POST (payload built from the form so it stays coupled to the template).
  Full suite **308 pytest tests green** (306 → 308); ruff clean.

- **2026-06-28** — Podpora feedback Batch A landed (Feedback #1 + #5):
  - **#1** Doc date defaults to today on `PlannedTransferForm.scheduled_for`
    (re-evaluated per render via `field.initial = date.today`) and
    `MixingPlanForm.planned_for` (top-level field). Příjem/výdej already
    had the default via `_MovementBaseForm`.
  - **#5** Detail dodacího listu (`screen 09`) renders a red "Poslední
    odeslání selhalo." banner above the existing "Znovu odeslat" button
    when the dodák has ≥1 FAILED log at `current_version` and no SENT
    log at `current_version`. Helper `_dl_failed_at_current_version(dl,
    logs)` in `inventory/views.py` shared with the owner-dashboard
    "K vyřešení" query (refactored to use it — DRY). Banner drops out
    the moment a re-send succeeds. Spec was already in
    `screens/09-detail-dodaciho-listu.md:97-100`.
  - 4 new view tests: today-prefill on `/prevody/novy/` +
    `/michani/planovat/`; banner shows when FAILED-no-SENT at
    `current_version`; banner hidden after a successful SENT log lands.
  - Full suite: **306 pytest tests green** (302 → 306); ruff clean;
    system check clean; makemigrations --check clean. Feedback #2/#3/#4
    deferred to subsequent batches; #3 (domain/HTTPS) waits on Matej
    picking a domain.

- **2026-06-26** — SMTP source-of-truth resolved per decision
  [`0049`](./decisions/0049-smtp-source-of-truth.md). Real dodák
  sends + low-stock summary now build their SMTP connection via a
  shared `_smtp_connection_from_settings(s)` helper in
  `inventory/services.py`. Settings DB wins for host / user /
  password (blank → `None` → Django falls back to `EMAIL_HOST*`
  env); `smtp_port` and `smtp_use_tls` are DB-only (both
  non-nullable, defaults 587 + True match the env contract — no
  migration needed for fall-through branches that don't exist at
  6 users). `settings_test_smtp`
  refactored onto the same helper so the "Otestovat odeslání"
  green ✓ now exercises the same code path as a real send.
  Refines [`0019`](./decisions/0019-email-smtp-sync.md) (sync-send
  + fail-silent + `DodaciListEmailLog` FAILED-row contract
  unchanged) and [`0037`](./decisions/0037-settings-singleton.md)
  (plaintext `smtp_password` + write-only `PasswordInput`
  unchanged). 4 new tests in `inventory/tests.py` cover helper
  kwargs (set vs blank), end-to-end wire-up, and the fail-silent
  contract. Provider details (`mail.kasia.cz:587` STARTTLS) on the
  `.env.example`; `EMAIL_HOST_PASSWORD` lands out-of-band when
  the `aplikace@kasia.cz` mailbox is created.

- **2026-06-26** — **Public marketing site at `/` + warehouse app moved
  under `/sklad/`.** Decisions
  [`0050`](./decisions/0050-public-site-and-sklad-split.md) (the split;
  second amendment of [`0020`](./decisions/0020-auth-django-builtin.md),
  extends [`0047`](./decisions/0047-design-review-gallery.md); renumbered
  from a draft 0049 after the SMTP 0049 landed first on main) and
  [`0051`](./decisions/0051-public-site-ia-and-content.md) (four-page IA +
  `ContactInquiry` durability + SEO/GDPR essentials).
  - **URL re-wire** (`kasia/urls.py`): inventory/accounts/auth/password-
    reset/password-change all moved under `/sklad/` (login at
    `/sklad/prihlaseni/`, logout `/sklad/odhlaseni/`, users
    `/sklad/uzivatele/`, password change `/sklad/zmena-hesla/`). Names
    unchanged → all `{% url %}` / `reverse()` / `LOGIN_URL` re-resolve.
    Public `web` include mounted **last** at `""`. `/admin/`, `/healthz`,
    `/navrhy/` unchanged. `LOGOUT_REDIRECT_URL` retargeted to `web:home`.
  - **Test audit:** 226 hard-coded path literals rewritten to `/sklad/…`
    (incl. `/_partials/*`, `/login/`→`/sklad/prihlaseni/`,
    `/accounts/zmena-hesla/`→`/sklad/zmena-hesla/`) across
    `inventory/tests.py` + `accounts/tests.py`. Template literal audit
    clean — every operational path uses `{% url %}` (only `/admin/` is a
    literal, correct).
  - **New `web` app:** `ContactInquiry` model (durable poptávka store,
    email-only string never linked to User; e-mail best-effort
    try/except per 0019, routed through the shared
    `_smtp_connection_from_settings` helper so it honours the SMTP
    source-of-truth from 0049) + read-only `ContactInquiryAdmin`; views
    all `@login_not_required`; a hidden honeypot spam-gate on the form;
    curated content in `web/content.py` (decoupled from warehouse DB).
    Migration `web/0001_initial`. Separate public
    `kasia/templates/web/base.html` (no htmx; SEO + OG + JSON-LD
    Organization; footer with contact/IČO/hours + Czech consent note +
    discreet "Sklad / Přihlášení" link) + `home` / `o_nas` / `provozovny`
    / `kontakt` / `kontakt_ok` + hand-rolled `robots.txt` + `sitemap.xml`.
    TYN/SEZ addresses + phones are placeholders ("doplnit od Petra").
  - **Stale-doc sweep:** 0020 preamble (2nd amendment banner), settings
    comment, `right-sized-for-small-business.md` (one Django *project*),
    `decision-log-discipline.md` (user-submitted-data models),
    `CLAUDE.md`, `company-profile.md`, `infra/RUNBOOK.md` (CSRF note for
    HTTPS cutover), this file. New
    [`context/public-site.md`](./public-site.md) + README pointer.
  - **Verification:** full suite green; ruff clean; `manage.py check`
    clean; `makemigrations --check` clean (only the new `web` migration).
    Production-like smoke + full docker stack (`make up`): public pages
    200, `/sklad/*` 302→`/sklad/prihlaseni/`, `/admin//healthz//navrhy/`
    intact, kontakt POST persists a `ContactInquiry` in Postgres, manifest
    `{% static %}` resolves. Hardened via `/pr-harden` (honeypot + CSRF
    RUNBOOK note); PR #3.
  - **Next (deferred, gated on Petr):** build `design-options/public/`
    mockup gallery + SVG logo concepts → Petr picks → log a decision →
    port the winner into the real `web/` templates. Add deferred pages
    (Sortiment, Encyklopedie, …) as later passes.

- **2026-06-28** — Design-gallery round 2 (both surfaces; on
  `ft_web_public_site`; exploration only, live templates untouched).
  - **Sklad** (`design-options/`): narrowed to the 4 chosen directions
    (01 mono, 02 swiss, 04 green-brand, 07 soft-cards); deleted the other
    14 (03,05,06,08–18); added 10 new in the same light/minimalist/modern
    feel (11 indigo, 12 slate-amber, 13 sidebar-app, 14 teal-calm,
    15 data-numerals, 16 pastel-cards, 17 outline-lineart, 18 sand-minimal,
    19 compact-pro, 20 green-pro). `index.html` rebuilt into two groups.
  - **Public** (`design-options/public/`): kept all four originals (01–04)
    + 05-kontakt; **deleted `logos.html`**; added 10 new homepage designs
    (06–15) — **all logo-image-free** (text wordmark "Kasia vera"),
    minimalistic & modern, anchored on the current green/clean look +
    02-clean-green. `public/index.html` rebuilt (logo card removed,
    header wordmark-only).
  - Both gallery sets share identical locked content (sklad dashboard /
    public homepage copy from `web/content.py`); only styling differs.
  - **Verification:** all gallery + 24 variant routes 200 over `http.server`;
    deleted files 404; no Django tags; public new designs reference no logo
    image; sample data + public copy consistent across all new files.
  - **Next:** Petr reviews → pick keepers per surface → cull rejects,
    iterate on picks + his requested changes → eventually log a decision +
    port winners into real templates.
- **2026-06-28** — **Kontakt + Provozovny rebuilt from real kasia.cz data;
  contact form removed** (on `ft_web_public_site`). Decision
  [`0052`](./decisions/0052-kontakt-info-only-drop-contactinquiry.md)
  (partially supersedes 0051).
  - **Removed the poptávkový formulář entirely:** `ContactInquiry` model
    (+ `0002_delete_contactinquiry` migration DROPs the table), `web/forms.py`,
    `ContactInquiryAdmin`, the `kontakt_ok` view/route/template,
    `_notify_inquiry` + `_CONTACT_RECIPIENTS`, and the
    `CONTACT_INQUIRY_RECIPIENTS` setting. **`web` is now a clean leaf app**
    (no `web → inventory` imports, no models).
  - **Kontakt** is info-only: contact panel (incl. new fax +420 323 602 077),
    a 3-person exec directory (Šulc/Prodej, Kovačková/Administrativa,
    Formánek/Nákup — photos from kasia.cz; per-person e-mail/phone are
    placeholders), and an embedded cookie-free **OSM map** of the sídlo.
  - **Provozovny** now lists **4** real locations (Říčany sídlo + Sezimovo
    Ústí, Toužim, Týniště nad Orlicí) with real addresses, per-branch phones,
    building photos, and per-card OSM maps. Coords geocoded once (Nominatim),
    hardcoded in `web/content.py`. Public content stays decoupled from the
    warehouse DB (stock tracking still TYN + SEZ only).
  - Discreet **"Přihlášení"** link added to the header (muted, not a CTA);
    "Sklad" still absent from the marketing nav. Footer privacy note updated
    for the OSM embed (IP exposure to map host). 7 images in
    `kasia/static/web/`.
  - **Verification:** 16 web tests green, ruff clean, `manage.py check` clean,
    `makemigrations --check` clean. Local `make up` + prod deploy pending.
  - ⚠ **Carry-over:** the one-line fix to
    `.claude/rules/decision-log-discipline.md` (drop the `ContactInquiry per
    0051` example) was blocked by the auto-mode classifier (rules-file
    self-modification) — apply manually before merge.

- **2026-06-28** — **Doc-creation forms now pre-fill today's date in the
  browser** (follow-up to Batch A in PR #4). Root cause: `<input type="date">`
  only honours ISO `YYYY-MM-DD` for its `value=` attribute, but Django was
  rendering `28.06.2026` from the Czech locale, which browsers silently drop.
  Fix in `inventory/forms.py`: added `format="%Y-%m-%d"` to all four
  `DateInput` widgets (`_MovementBaseForm.date_issued`,
  `MovementLineForm.expiry`, `PlannedTransferForm.scheduled_for`,
  `MixingPlanForm.planned_for`). Added `DATE_INPUT_FORMATS` to
  `kasia/settings/base.py` so the ISO value POSTed back by the browser still
  parses (Czech locale's formats remain first for hand-typed input).
  Affects `/sklad/prijem/novy/`, `/sklad/vydej/novy/`,
  `/sklad/pohyby/<pk>/upravit/`, `/sklad/prevody/novy/`,
  `/sklad/michani/planovat/`. Batch A regression tests flipped from Czech
  to ISO assertion; two new positive tests added for prijem + vydej (the
  forms the user actually complained about). 339 tests green, ruff clean,
  `manage.py check` clean.

- **2026-06-28** — **Per-branch product availability landed**
  ([`0053`](./decisions/0053-stock-row-is-branch-carry.md)). Fixes the
  Cibule-on-TYN-falsely-critical report. Existence of a `Stock` row is now
  the source of truth for *branch carries product*. `low_stock_rows`
  iterates Stock rows instead of `Product × Branch`; catalogue chips +
  product detail use the same Stock-driven iteration. Two new
  vlastník-only POST views (`product_branch_add`,
  `product_branch_remove`) wired under
  `katalog/<id>/pobocky/<branch>/{pridat,odebrat}/`. Product edit gets a
  *Pobočky držící tento produkt* fieldset with **Drží / Nedrží**
  badges (read-only for obsluha) + Přidat / Odebrat buttons
  (vlastník-only, native `confirm()` warns on non-zero on-hand or
  reservations). `product_create` calls a new
  `seed_branch_carriage_for_product` helper that seeds a 0-kg `Stock`
  row for every active branch. Data migration
  `0013_seed_stock_for_existing_products` backfills the same rows for
  every existing (active product × active branch) pair on prod (no-op
  reverse). New domain headwords *drží / nedrží* in
  `context/domain-glossary.md`; mention added to screens 04 + 05.
  Tests: one rewrite (`test_low_stock_rows_sorted_by_deficit` — SEZ no
  longer appears without a Stock row) + seven new tests. 346 tests
  green, ruff clean, `manage.py check` clean.

- **2026-06-28** — **Public-site pass 2: O nás long-form, homepage
  enrichment, footer cleanup, public-branded login** (on
  `ft_web_public_pass2`). A content + cosmetic refinement within decisions
  [`0050`](./decisions/0050-public-site-and-sklad-split.md) +
  [`0051`](./decisions/0051-public-site-ia-and-content.md) +
  [`0052`](./decisions/0052-kontakt-info-only-drop-contactinquiry.md) — **no
  new decision file** (docs updated instead; see `context/public-site.md`).
  - **Header login link removed** — `Přihlášení` is now **footer-only** (a
    "Přihlášení do skladu" link in the new *Odkazy* column), since a header
    login link misleads customers who have no app access. `.login-link` CSS
    dropped.
  - **Footer** reorganised into three tidy columns (firma + IČO/datová
    schránka / Kontakt / Odkazy) + a short legal strip; privacy note
    shortened (dropped the long IP-clause sentence and the duplicate
    "Sklad / Přihlášení" span).
  - **O nás** rewritten as a real long-form article from kasia.cz/about
    (Matej: include export/reach, omit RC Rugby sponsorship): lead →
    sortiment → vlastní výroba (1995 česneková pasta Týniště, 1998 míchárna
    Strančice, 2011 výrobna Sezimovo Ústí, gastro směsi z Toužimi pod VERA
    GURMET) → dovoz a export (PL/UA/SK/IL/BY/NL) → dostupnost a dosah → CTA.
  - **Homepage** enriched for B2B: Co děláme (capabilities), Komu dodáváme
    (segments + one-line sortiment mention), Proč Kasia (why-us). **Products
    kept minimal** — no product list, no new Produkty/Encyklopedie page
    (deferred per 0051).
  - **Public-branded login** (`registration/login.html` extends
    `web/base.html`): two panels — Zaměstnanci (sign-in + "Zapomenuté
    heslo?") / Zákazníci (staff-warehouse note + links back to web/Kontakt).
    `login` route gains `redirect_authenticated_user=True` (logged-in visitor
    → `/sklad/`) + `extra_context` for the public chrome. `web/base.html` CSS
    fix: `input[type=password]` added to the form-input selector; login
    errors use `{{ form.non_field_errors }}` (the existing `.errorlist` rule).
  - `web/content.py`: added `COMPANY["export_markets"]`.
  - **Verification:** 19 web tests green (incl. login redirect-authenticated),
    ruff clean, `manage.py check` clean, `makemigrations --check` clean (no
    migrations). Local `make up` + prod deploy pending.

- **2026-06-29** — **UI directions ported into the real app (intermediate live
  state)** per [`0054`](./decisions/0054-adopt-ui-directions.md). Branch
  `ft_ui_port_intermediate` off synced main.
  - **Sklad** (`kasia/templates/base.html`): chrome rewritten to a left
    **sidebar** app shell — jpg logo + `KASIA / sklad`, vertical nav
    (vlastník-only items split under a "Správa" label), user e-mail +
    Odhlásit pinned bottom; collapses to a top bar + scroll-nav under 720px.
    Sharp/0-radius, brand-green accent, **Inter** + **IBM Plex Mono**. Shared
    component CSS rewritten under the **same class names** (`.card`,
    `.primary`/`.secondary`, `table.lines`, `.tab-chip`, `.row-delete-btn`,
    `.messages`, …) so every child template inherits; **all JS/HTMX hooks
    preserved verbatim** (row-delete, whole-row nav, `stockWarnVals`,
    `#lines-table`/`#lines-body`, `.stock-warn-cell`). `:root` gains
    `--ok-soft` (the 0053 carry-chip referenced it). `.row-delete-btn`
    box-model fixed (the oversized `Smazat`). Added `.kpis` KPI strip +
    utilities (`.row`/`.stack`/`.actions`/`.muted`/`.num`/`.grid-2`).
  - **KPI overview:** `inventory/views.py home()` adds 4 aggregates (K
    vyřešení / Produktů skladem / Celková zásoba kg / Dochází zboží) → strip
    in `inventory/home.html`; `branch_dashboard()` + `branch_dashboard.html`
    get an equivalent per-branch KPI header (obsluha redirect target).
  - **Public** (`kasia/templates/web/base.html`): restyled in place to
    centered/curvy/green — radius 18/999, soft shadows, **Sora** + **Inter**,
    eyebrow pills, hero helpers — keeping every page class name. `web/home.html`
    rebuilt: centered hero (eyebrow, big Sora headline, stat block 369+/236,
    pill CTAs) over hand-authored **`web/art-hero.svg`** (commented real-photo
    slot), centered section heads, green SVG line-icons on all cards; every
    section preserved (Co děláme ×6, Komu dodáváme ×3, Proč Kasia ×6, teasers).
    o_nas / provozovny / kontakt / login inherit the system (kontakt still
    form-free).
  - **Docs/rules:** `0054`, new `.claude/rules/design-system.md`, amended
    `no-premature-tech-choices.md` (design direction now gated), updated
    `screens/02` + `public-site.md`.
  - **Verification:** `manage.py check` clean, ruff clean, **349 pytest green**
    (unchanged from baseline), `collectstatic --noinput` clean (SVG hashed into
    manifest, `navrhy` gallery still collects). Local walkthrough + prod deploy
    next.

- **2026-06-29** — **UI-port bugfix + public restyle finish** (branch
  `hf_web_ui_port_fix`; **refines `0054`, does not supersede it** — directions +
  shared-class contract unchanged). The 2026-06-29 `0054` deploy was shipped
  *without* a visual check or sign-off and two problems surfaced (Matej's
  feedback): (1) **sklad was unusable** — `.mob-nav` had no default
  `display:none`, so on desktop it rendered as the first item of the `.app`
  grid, shoved the sidebar into the `1fr` column and left a stray unstyled link
  column; (2) the **public restyle stopped at `.stat`** — footer / login /
  branch cards / map / forms below it were still pre-`0054` flat CSS. Fixes on
  this branch:
  - **Fix A (critical):** added `.mob-nav { display:none }` to the desktop block
    in `kasia/templates/base.html` (the `@media(max-width:720px)` block still
    turns it on for mobile). Sidebar 244px + `.content` 1fr restored; JS/HTMX
    hooks + shared classes untouched.
  - **Fix B:** brought the leftover `web/base.html` CSS into the curvy-green
    system (radius/shadow tokens, Sora headings) — forms, login card/panels/
    aside, contact panel, people, badge, branch cards (rounded top photo,
    inherited card shadow/hover), map-embed, and a redesigned footer (brand
    wordmark block + hairline accent); every class name kept, footer login link
    kept class-free (test-locked).
  - **Fix C:** de-boxed `web/home.html` — dropped the hero eyebrow, added a prose
    `.about-band` (Říčany photo), a light `.feature-list` (Komu dodáváme), a
    borderless `.checklist` (Proč Kasia), and a dark-green `.cta-band`; dropped
    the 3 trailing teaser cards. Kept "Co děláme / Komu dodáváme / Proč Kasia" +
    369/236 (test-locked).
  - **Verification:** `manage.py check` clean, ruff clean, **349 pytest green**,
    `collectstatic --noinput` clean; rendered locally via `make up` (real pages,
    not just pytest strings — the step missing last time). **No deploy** — by
    Matej's instruction after the unsanctioned first deploy, this is verified
    locally and waits for explicit go-ahead before touching `main`/prod.
  - **Round 2 (same session, on local-eyeball feedback):**
    - **Sklad content centered** — `.content` got `margin: 0 auto` so a wide
      desktop centers the 1180px column instead of hugging the sidebar with a
      big empty right gutter.
    - **Themed edit-form fields** (`base.html`) — inputs/selects/textareas get a
      faint fill, hover border, accent inset focus ring, and a custom SVG caret
      on `<select>` (still radius-0 per 0054) so the *upravit* forms don't read
      as raw browser widgets.
    - **Historie tab-chips fixed** — the active chip was double-classed
      `primary tab-chip` (button padding/line-height fighting the chip styles,
      causing the shifted text + stray gap); now plain `.tab-chip` /
      `.tab-chip.active`, container `align-items:center`. (Only `movement_history`
      had this pattern.)
    - **Public polish** — O nás wrapped in `.article` (readable measure, rounded
      shadowed lead photo, green-accented section heads); provozovny phone/hours
      moved to a tidy `.meta` definition list; map link styled.
    - Note: the Nastavení **500 was a stale local DB**, not code — the running
      dev Postgres was missing migrations `0012_settings_recipients_table` +
      `0013_seed_stock_for_existing_products`; `manage.py migrate` fixed it
      (those migrations already ship in the repo). Now 200.
    - Re-verified: check / ruff clean, **349 pytest green**, collectstatic clean,
      and all pages re-rendered via the rebuilt docker stack. Still **no deploy**.

- **2026-06-29** — **Recipe PDF + mixing notes + custom error pages** (same branch;
  [`0055`](./decisions/0055-recipe-pdf-and-mixing-notes.md)). On Matej's walkthrough
  of a *směs* product detail:
  - The free-form **mixing notes** (packing size / mixing time, captured from the
    recipe XLS into `Product.notes` per `0048`) are now surfaced as "Poznámky
    k míchání" inside the Receptura card (and no longer double-shown in the stock
    card for mixtures). Added a "Zahájit míchání →" link to the real mixing-job
    flow so the recipe view has an actionable next step.
  - **Recipe PDF** — `render_recipe_pdf()` (WeasyPrint, reuses dodák infra) →
    `inventory/recipe_pdf.html` (ingredient table podíl / % / per-100 kg + notes),
    `recipe_pdf` view at `/sklad/katalog/<pk>/receptura/pdf/` (404 for non-mixtures).
    "Stáhnout recepturu (PDF)" button on the detail page. No model/migration/dep.
  - **Themed "Spočítat dávku" box** — the scaler inputs weren't in a `<form>`, so
    they missed the themed field CSS; wrapped the scaler card in a non-submitting
    `<form>`. Cosmetic, JS hooks unchanged.
  - **Custom branded error pages** — `kasia/templates/404.html` (green/Sora, logo,
    links to úvod + sklad login) and a dependency-free `500.html`, replacing
    Django's plain defaults (DEBUG=False only).
  - Verified: check / ruff clean, **353 pytest green** (+4: recipe PDF download,
    404-for-raw-spice, notes+PDF-link on detail, branded-404), collectstatic clean,
    recipe PDF + detail re-rendered via the docker stack. PR opened (#9).
  - **Round 2 on the same screen (Matej's feedback):**
    - **"Spočítat dávku" is now the interactive tool** — the PDF button moved
      here from the Receptura card; kg input accepts `12,5` / `12.5`; quick
      presets 5/10/25/50/100 kg; the "Potřeba (kg)" column recomputes live; the
      PDF link carries the chosen qty (`?qty=`), so the PDF matches what's on
      screen.
    - **Exact-sum rounding** (`_amounts_summing_to`) — Knedlík's % summed to
      100.01; now the rounding difference lands on the largest line so the %
      column sums to exactly 100.00 and the kg column to the target.
    - **"Zahájit míchání →" pre-selects the směs** (`?mixture=<pk>` →
      `mixing_job_create` marks the option selected).
    - **356 pytest green** (+3: qty PDF, exact-sum unit test, mixture preselect);
      re-rendered + Knedlík 100.00 % confirmed via the docker stack.
- **2026-06-29** — **Homepage hero now shows the real Kasia logo + real slogan**
  (branch `ft_wa_hero_logo`, PR #11, squash-merged + deployed to prod). Captured
  the live company logo from `kasia.cz` (being taken down) → `kasia/static/web/
  hero-logo.png` (259×157 PNG) and swapped it for the hand-authored `art-hero.svg`
  in the homepage hero (`web/home.html`); dropped `aria-hidden`, real `alt`
  (`company.legal_name`) — an explicit owner override of the green-SVG preference
  in [`0054`](./decisions/0054-adopt-ui-directions.md). Added `.hero-art img`
  sizing + tightened `.hero-art` `max-width` to 360px so the small raster isn't
  upscaled (`web/base.html`). H1 changed to Kasia's real slogan **"Koření, které
  gurmán ocení"**. `art-hero.svg` left unreferenced (harmless). **Map idea
  shelved**: a hand-drawn themed SVG can only be country-level, so the functional
  OpenStreetMap embeds stay as-is (no decision, no code change). check / ruff
  clean, **356 pytest green** (no new tests — pure template/asset swap), no
  migrations; verified live on prod `http://91.98.47.1/` (logo serves 200, H1 +
  slogan correct).

- **2026-06-29** — Phase A of the HTTPS / `kasia.cz` cutover landed
  (decision [`0056`](./decisions/0056-domain-cutover-https.md)). Goal:
  front-load every *safe* change to prod before the A record is pointed, so
  the actual cutover is the smallest possible flip. Canonical host is the
  apex `kasia.cz`; `www.kasia.cz` → 301 → `kasia.cz`.
  - `kasia/settings/base.py`: added **env-gated** `SECURE_PROXY_SSL_HEADER`
    (`HTTP_X_FORWARDED_PROTO`/https), `CSRF_TRUSTED_ORIGINS` (from
    `DJANGO_CSRF_TRUSTED_ORIGINS`), and `SESSION_COOKIE_SECURE` /
    `CSRF_COOKIE_SECURE` (from `DJANGO_SECURE_COOKIES`, default off). All
    default to today's HTTP-only behaviour until the on-box `.env` opts in —
    so the change is **inert on deploy**. No `SECURE_SSL_REDIRECT` (Caddy
    redirects), no `USE_X_FORWARDED_HOST` (Caddy preserves Host).
  - `.env.example`: documented `DJANGO_ALLOWED_HOSTS` (keep
    `127.0.0.1,localhost` for the `/healthz` healthcheck under DEBUG=False),
    `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_COOKIES` (flip to 1 only
    once HTTPS is live).
  - `infra/RUNBOOK.md` § 5 rewritten: 443 already open on the live firewall
    (no Terraform change); the DNS-must-resolve-before-Caddyfile ordering +
    LE rate-limit caveat; Phase A `.env` pre-set vs Phase B flip.
  - `.claude/rules/infra-as-code.md`: note that the site-specific `.env`
    vars are per-deployment, never committed.
  - **No Terraform change** — firewall id 11145413 already opens 443.
  - Verified: `manage.py check` clean; **356 pytest green** (all new flags
    default OFF, suite runs under DEBUG=True so behaviour is unchanged).
  - **Phase B held in a separate, unmerged draft PR (#14)** (Caddyfile
    hostname block + `compose.yaml` 443) so it can't auto-deploy before DNS
    resolves. Phase A is PR #13.
  - **On-box `.env` pre-set (done 2026-06-29):** SSH'd to the box (app@),
    backed up `.env` → `.env.bak.https-cutover`, set
    `DJANGO_ALLOWED_HOSTS=kasia.cz,www.kasia.cz,91.98.47.1,127.0.0.1,localhost`
    and added `DJANGO_CSRF_TRUSTED_ORIGINS=https://kasia.cz,https://www.kasia.cz`;
    left `DJANGO_SECURE_COOKIES` unset (cookies still flow over HTTP).
    `docker compose up -d --force-recreate web` to load the new env (plain
    `restart` does **not** re-read env_file). Side effect: the `/healthz`
    healthcheck — which had been returning 400 (DisallowedHost) because the
    old `ALLOWED_HOSTS` lacked `127.0.0.1` — now passes; container reports
    **healthy**. Verified `http://91.98.47.1/` still serves (302). HTTPS on
    the box is **not** reachable (443 unpublished until Phase B; and LE never
    certs a bare IP — HTTPS waits for DNS + Phase B).
  - **Remaining for cutover:** point DNS (`A kasia.cz` / `A www.kasia.cz`
    → 91.98.47.1), confirm via `dig`, merge PR #14, then set
    `DJANGO_SECURE_COOKIES=1` on the box + recreate web.

- **2026-06-29** — **Polish round: sidebar IA, mixing-job recipe PDF,
  Czech-locale decimal fixes, Podpora sort, per-product stock inventura,
  custom confirm dialog + dirty-state guard** (branch `ft_wa_polish_round`).
  Bundle of follow-ups from Matej's walkthrough after PR #7:
  - **Sidebar IA** — `base.html`: Dodavatelé + Odběratelé moved out of the
    daily-workflow "Provoz" group into a new always-visible "Číselníky" section
    placed **above** the vlastník-only "Správa" block (obsluha keeps access;
    just reordered). Mobile nav: same two anchors moved to the end of the flat
    list before the vlastník items. No view / permissions / URL change.
  - **Mixing-job recipe PDF link** — `mixing_job_detail.html`: added
    "Stáhnout recepturu (PDF)" next to the consumption / production movement
    links, pointing at the existing `recipe_pdf` endpoint with
    `?qty=job.target_qty|unlocalize`. Widens the surface of
    [`0055`](./decisions/0055-recipe-pdf-and-mixing-notes.md) — no new view,
    route, or test for PDF rendering.
  - **Podpora history sort** — `inventory/views.py`: support list now orders by
    `F("resolved_at").asc(nulls_first=True), "-created_at"`, so open items sit
    above resolved ones; within each group, newest first. Same 50-row limit.
  - **Recipe scaler "Potřeba (kg)" zeroed bug** — `product_detail.html`:
    `LANGUAGE_CODE = "cs"` + Django 5 L10N was rendering
    `data-ratio="{{ rc.ratio }}"` as `0,500000`, so `parseFloat` returned 0 and
    the live scaler printed 0 in every row. Added `{% load l10n %}` + piped
    through `|unlocalize`. Same root cause + fix on
    `inventura_edit.html:data-current` (the "Rozdíl" column miscomputed for
    fractional stock).
  - **Per-product stock inventura** — `/sklad/katalog/<pk>/upravit-stav/`
    converted from "pick one branch via dropdown + edit one row" to a full
    table editor: one row per active branch with editable "Nový stav (kg)"
    input, current qty + reserved + Drží/Nedrží chip, per-row Odebrat /
    Přidat na pobočku (both keep you on the same page via a `?next=` round
    trip honored by `product_branch_remove` / `product_branch_add`),
    shared "Důvod úpravy" field, one submit writes a `[STAV]` Movement
    per changed row. `StockAdjustmentForm` removed; view parses
    `qty_<branch_pk>` posts directly. Entry points: existing
    "Upravit stav skladu" links on `product_form.html` (carry table card)
    + new link on `product_detail.html` (Stav skladu card, vlastník-only).
  - **Branded confirm dialog + dirty-state guard** — `stock_adjust_form.html`:
    inline `<dialog>` styled in the project's green/cream palette replaces
    the browser-default `confirm()` for Odebrat. The Zrušit link and per-row
    Odebrat / Přidat buttons trigger the same modal when there are unsaved
    `qty_*` edits ("Opustit beze změn?"). Browser-level navigation (back,
    tab close) falls back to native `beforeunload` since browsers ignore
    custom messages there.
  - **361 pytest green** (+5: scaler dot-decimal, inventura data-current,
    support open-before-resolved, per-product bulk inventura,
    all-active-branches rendered as rows; existing stock_adjust tests
    rewritten to post the new `qty_<branch.pk>` fields); ruff +
    `manage.py check` clean. No new decision file — this is polish + UX
    refinement of existing surfaces, not architecture.
- **2026-06-29** — **Polish round 2: row-click, auto-append line, catalog
  stock-state filter, Míchání icon** (branch `ft_wa_polish_round_2`).
  Four-item bundle from the walkthrough following PR #15:
  - **Mixing index whole-row click** — `mixing_job_index.html`: rows
    converted from single-anchor "Zahájeno" cell to `tr.row-link
    data-href` so anywhere on a row navigates to the job detail. Reuses
    the existing JS handler + hover CSS in `base.html` (same pattern as
    `catalogue_index.html` / `dodaci_list_index.html` /
    `planned_transfer_index.html` / `movement_history.html`). Supplier /
    customer / branch index pages intentionally kept button-driven —
    they have no "detail" view.
  - **Auto-append blank line on Příjem/Výdej** —
    `_movement_form_lines.html`: the existing "Přidat řádek" button now
    carries `id="add-line-btn"`; an inline delegated `input` listener on
    `#lines-body` programmatically clicks that button when the operator
    types into the last non-deleted row, so there's always one trailing
    empty line. Guard via `data-autopopulated="1"` on the row to avoid
    spamming the partial endpoint on rapid keystrokes. Both screens
    share the partial.
  - **Catalog stock-state filter** — `catalogue_index.html` +
    `inventory/views.py:catalogue_index`: new `?state=low|empty` query
    param + matching `<select name="state">` in the filter strip
    ("Dochází" / "Prázdné"). Filter runs in Python after `rows` are
    built (because `is_low` / `effective` are per-request, not stored
    on `Product`) and before `count` is read, so the "Nalezeno: N"
    line reflects the filtered length. Companion edits to the
    "Vymazat filtry" condition and the "Zobrazit všechny pobočky"
    link so neither loses the state filter on navigation.
  - **Míchání sidebar icon** — `base.html:371`: SVG paths swapped
    from the cup-on-stand glyph to a two-opposing-curved-arrows
    rotate/cycle glyph, in the same Feather/Lucide 1.8 stroke style
    as the rest of the sidebar.
  - **371 pytest green** (+5: mixing index row-link, add-line-btn
    marker present on both Příjem/Výdej, line_row_partial sanity,
    catalog state=low filter, catalog state=empty filter); ruff +
    `manage.py check` clean. No new decision file — pure UI polish,
    nothing schema-shaped.

## Hand-off for the next session (post-compact)

**Origin/main head: `16b9081` (2026-06-13 Pass 5g).** Local main
and origin/main are in sync.

**Operating posture (Matej 2026-06-12, still active):**
- Keep building locally; **no Hetzner deploy yet**. Hetzner
  provisioning + the shadow run come *after* the full surface
  is built and Matej has tested it locally.
- All local testing happens in the **full docker compose
  stack** (`make up` → http://localhost/), not
  `manage.py runserver`. Same image we ship to Hetzner. See
  the `Makefile` targets and [[feedback-docker-full-stack]].
- The `deploy.yml` workflow on `origin/main` keeps failing on
  the SSH step ("missing server host"). That is the **expected
  pre-Hetzner state**, not a regression. Don't try to fix it.
- Matej drives feedback. He'll open the local stack, walk
  through screens, and feed back fixes / ideology changes;
  do **not** start a new feature pass without his go-ahead.

**Code surface — operator-facing MVP is COMPLETE:**

14 design screens, all built. Plus the full Pass 5 operator
CRUD on top so nothing operationally important is admin-only
anymore.

- **Original 14 screens:** 01 login (Django built-in),
  02 owner dashboard, 03 branch dashboard, 04 catalogue,
  05 product detail, 06 příjem, 07 výdej, 08 dodáky list,
  09 dodák detail, 10 movement history, 11 movement edit,
  13 správa uživatelů, 14 nastavení, 15 míchání.
- **Pass 5 operator CRUD** (per
  [`0040`](./decisions/0040-operator-crud-tiering.md) +
  [`0041`](./decisions/0041-manual-stock-adjustment.md) +
  [`0042`](./decisions/0042-overdraw-guided-correction.md)):
  - 5a — Supplier + Customer CRUD (`/dodavatele/`,
    `/odberatele/`) for all users.
  - 5b — Product + Recipe CRUD (`/katalog/novy/`,
    `/katalog/<pk>/upravit/`). Fields = all; recipe + archive
    = vlastník-only.
  - 5c — Branch CRUD (`/pobocky/`), vlastník-only, code locks
    after first dodák per 0008.
  - 5d — Per-product stock direct edit
    (`/katalog/<pk>/upravit-stav/`) via synthetic Movement
    with `[STAV] ` note prefix (internal
    "Inventura / ruční úprava" counterparty pair seeded by
    migration 0008). Vlastník-only.
  - 5e — Bulk inventura editor
    (`/katalog/inventura/<code>/`) — vlastník walks every
    product at one branch, types new quantities, saves all
    at once. Each non-zero delta = one synthetic Movement.
  - 5f — Guided overdraw correction on výdej: pre-checks all
    lines against stock, renders structured "Nedostatek na
    skladě" card with per-row "Upravit stav skladu ↗" button
    (vlastník) so the operator fixes the count and retries.
  - 5g — Historie redesign: tab chips
    (Vše / Příjmy / Výdeje / Inventura / Editováno) with
    live count badges above the existing filter card;
    `[STAV]` movements get an "inventura" badge in the Druh
    column.

**Verification of where each screen lives:**
- URL conf: `inventory/urls.py` (and `kasia/urls.py` for
  /login/ /logout/ /admin/ + password-reset chain).
- Views: `inventory/views.py` — function-based, grouped by
  screen with `# --- ###` section headers.
- Templates: `kasia/templates/inventory/*.html` extending
  `base.html`; dodák PDF is `inventory/dodaci_list.html`
  with embedded CSS Paged Media; registration in
  `registration/login.html` + password-reset chain.
- Services (single write path): `inventory/services.py` —
  `apply_movement` / `edit_movement` /
  `apply_stock_adjustment` (5d/0041) /
  `start_mixing_job` / `finish_mixing_job` /
  `cancel_mixing_job` / `record_completed_mixing_job` /
  `render_dodaci_list_pdf` / `send_dodaci_list_email`.

**Decisions landed this session (2026-06-12 → 2026-06-13):**
- [`0040`](./decisions/0040-operator-crud-tiering.md) —
  two-tier-per-entity operator CRUD gating.
- [`0041`](./decisions/0041-manual-stock-adjustment.md) —
  stock direct edits go through a synthetic Movement with
  `[STAV] ` note prefix; internal Inventura counterparty
  pair seeded by `inventory/0008_seed_adjustment_counterparty.py`.
- [`0042`](./decisions/0042-overdraw-guided-correction.md) —
  overdraw doesn't refuse silently; it prompts with the
  insufficient items + an inline correction path for
  vlastník.

**Quality bar (do not weaken on later passes):**
- `make test` (= `uv run pytest`) → all green (currently 252).
- `uv run ruff check` → clean.
- `uv run python manage.py check` → clean.
- `uv run python manage.py makemigrations --check --dry-run`
  → "No changes detected" unless the pass adds models.
- Every pass smoke-tested against the **full docker compose
  stack** (`make up` → http://localhost/), not
  `manage.py runserver`. Same image we ship to Hetzner.

**Test accounts (seeded via `make seed`):**
- `admin@kasia.local` / `heslo1234` — superuser
- `karolina@kasia.local` / `heslo1234` — vlastník
- `tyn@kasia.local` / `heslo1234` — obsluha TYN
- `sez@kasia.local` / `heslo1234` — obsluha SEZ

**Walkthrough docs:** `WALKTHROUGH.md` (Czech, per-page
purpose + test cases) at repo root.

**No open blocking decisions.** Both pre-compact opens
(overdraw policy, Historie redesign) merged as 0042 + 5g.
Matej's local walkthrough is the next signal; until he
feeds back, hold position and respond to direct asks.

## Next

1. **Local walkthrough by Matej** against the running docker
   stack — public site at `make up` → http://localhost/ and the
   warehouse app at http://localhost/sklad/. All 14 screens +
   Pass 5 CRUD (5a–5g) are in, both blocking decisions
   (0040, 0041, 0042) merged. Matej feeds back fixes /
   ideology changes screen by screen.

2. **UI-direction polish pass** (follows the intermediate live state from
   [`0054`](./decisions/0054-adopt-ui-directions.md), 2026-06-29). The two
   base templates + dashboards are ported; remaining work is a per-page
   alignment/inline-style sweep across the sklad forms, index tables, and
   detail/confirmation screens (replace fighting inline styles with the new
   `.row`/`.stack`/`.actions`/`.muted`/`.num`/`.grid-2` utilities), plus
   swapping the commented hero photo slot once Petr supplies a real photo.
   Keep the class names + JS/HTMX hooks stable (see `design-system.md`).
   Then add the deferred public pages (Sortiment, Encyklopedie koření, CSR,
   segmenty) as later passes.

3. **Quality-of-life backlog** — three items landed 2026-06-15;
   nothing currently queued. Reopen as walkthrough surfaces
   more.

4. **(Deferred until Matej says go.)** Provision the Hetzner
   box per
   [`infra/RUNBOOK.md`](../infra/RUNBOOK.md) → 14-day shadow
   run per
   [`0034`](./decisions/0034-shadow-run-before-go-live.md) →
   branch-staff cutover.
