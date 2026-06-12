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

## Hand-off for the next session (post-compact)

**Posture (Matej 2026-06-12):**
- Keep building all screens locally; **no Hetzner deploy yet**.
  Hetzner provisioning + the shadow run come *after* the full
  surface is built and Matej has tested it locally.
- Test only against the local dev server (`uv run python
  manage.py runserver`) + the local compose stack. The deploy
  workflow on `origin/main` will keep failing on the SSH step
  ("missing server host") — that is the expected pre-Hetzner
  state.
- Matej will open the local app and feed back fixes /
  ideology changes screen by screen once everything is built.

**MVP code surface — all 14 screens now in:**
- Built: 01 login (Django built-in), 02 owner dashboard,
  03 branch dashboard, 04 catalogue, 05 product detail,
  06 příjem, 07 výdej, 08 dodáky list, 09 dodák detail,
  10 movement history, 11 movement edit, 13 správa uživatelů,
  **14 nastavení**, 15 míchání.
- **Operator-facing MVP surface is complete.** Next step is
  Matej's local walkthrough → feedback iteration → Hetzner
  provisioning + shadow run.

**Verification of where each screen lives:**
- URL conf: `inventory/urls.py` (and `kasia/urls.py` for
  /login/ /logout/ /admin/).
- Views: `inventory/views.py` — function-based, grouped by
  screen with `# --- ###` headers.
- Templates: `kasia/templates/inventory/*.html` extending
  `base.html`; the dodák PDF is `inventory/dodaci_list.html`
  with embedded CSS Paged Media; the registration template is
  `registration/login.html`.
- Services (single write path): `inventory/services.py` —
  `apply_movement` / `edit_movement` /
  `start_mixing_job` / `finish_mixing_job` /
  `cancel_mixing_job` / `record_completed_mixing_job` /
  `render_dodaci_list_pdf` / `send_dodaci_list_email`.

**Quality bar (do not weaken on later passes):**
- `make test` (= `uv run pytest`) → all green (currently 184).
- `uv run ruff check` → clean.
- `uv run python manage.py check` → clean.
- `uv run python manage.py makemigrations --check --dry-run`
  → "No changes detected" unless this pass adds models.
- Every pass smoke-tested against the **full docker compose
  stack** (`make up` → http://localhost/) — not
  `manage.py runserver`. Same image we ship to Hetzner. See
  the `Makefile` targets and
  [[feedback-docker-full-stack]] memory.

## Next

1. **Local walkthrough by Matej.** All 14 screens land in
   docker (`make up` → http://localhost/). Matej steps
   through every screen with realistic data and feeds back
   fixes / ideology changes.
2. **Quality-of-life:** branch-code rename guard (lock after
   first dodák per
   [`0008`](./decisions/0008-dodaci-list-numbering.md)),
   admin `is_internal` filter on Customer/Supplier so
   Míchárna doesn't clutter the picker.
4. **Local-only validation.** Once 13 + 14 land, run the full
   compose stack locally (db service with the ICU locale
   landed in 0038) and walk through every screen by hand
   before Matej takes over for feedback iteration.
5. **(Deferred until Matej says go.)** Provision the Hetzner
   box per
   [`infra/RUNBOOK.md`](../infra/RUNBOOK.md) → 14-day shadow
   run per
   [`0034`](./decisions/0034-shadow-run-before-go-live.md) →
   branch-staff cutover.
