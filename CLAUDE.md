# Kasia-warehouse — agent instructions

This repository is the warehouse management tool for **Kasia vera s.r.o.**,
a Czech B2B spice distributor. The stack is locked, the operator-facing
MVP is built (15 screens + Pass 5 operator CRUD + Pass 6 reorder
threshold / reservations / low-stock summary + Pass 7 Podpora +
Pass 8 XLS recipe importer + in-app password change), and the system
runs locally via `make up` against the same Docker image shipped
to the Hetzner box, which is **provisioned and live** — a push to
`main` deploys to production via `deploy.yml`. The 14-day shadow run
comes last.

The site is split into two surfaces on one domain (per
[`0050`](./context/decisions/0050-public-site-and-sklad-split.md)): a
**public marketing site at `/`** (no login, the `web` app — see
[`context/public-site.md`](./context/public-site.md)) and the
**login-gated warehouse app under `/sklad/…`** (auth at
`/sklad/prihlaseni/`, users at `/sklad/uzivatele/`). `/admin/` and
`/healthz` stay at root. (The `/navrhy/` design gallery was retired per
decision 0067 — the mockups stay in `design-options/` but are not served.)

## Read in this order

1. **`context/state.md`** — current project status (Done / In progress / Next).
   This is the cold-start anchor. Always read first.
2. **`context/README.md`** — index of all foundational context, with the
   recommended reading order.
3. **`.claude/rules/`** — load-bearing rules that govern how you work in this
   repo. Pay particular attention to `decision-log-discipline.md`,
   `state-file-discipline.md`, and `right-sized-for-small-business.md`.
   **Before editing any template or CSS, read `frontend-and-templates.md`** —
   it maps the post-0068 layout and lists the silently-wrong gotchas (e.g.
   multi-line `{# #}` comments render as page text), two of which are enforced
   by `inventory/tests/test_template_hygiene.py`.
4. **`context/decisions/`** — read in numeric order. 0028–0034 supersede
   parts of 0001–0013 (Petr's 2026-06-09 brief); 0044 supersedes part
   of 0039 (reservations); 0050 + 0051 add the public site and move the
   app under `/sklad/` (amend 0020 + 0047). The tech-stack layer is
   0014–0027.

## Hard rules (summary — full text in `.claude/rules/`)

- **Python toolchain is `uv`.** Per
  [`0014`](./context/decisions/0014-language-python-uv.md). No pip, no
  poetry, no pipenv, no rye, no conda. All commands run via `uv run …`.
- **Tech stack is settled for the layers in 0014–0027** (Python 3.14 /
  Django 5.2 LTS / Postgres 18 / WeasyPrint / htmx / Caddy / Docker
  Compose / Terraform-hcloud / GitHub Actions / Hetzner CPX22). For
  any **new** layer (caching, background queue, observability, search)
  the `no-premature-tech-choices.md` rule still applies — surface
  options in `context/tech-options.md` first, record a numbered
  decision before code lands.
- **User-facing text is Czech (`cs_CZ`).** Code, identifiers, comments,
  and commit messages are English. Domain terms use the spellings in
  `context/domain-glossary.md`.
- **Decisions are logged before they land.** Every non-trivial
  decision gets a dated file in `context/decisions/NNNN-slug.md`
  *before* it shows up in code. Append-only — to change a prior
  decision, write a new file and add a one-line `> Superseded by NNNN`
  banner at the top of the old one.
- **`context/state.md` is updated at the end of every working
  session.** It is the next agent's first read.
- **Infra changes go through `infra/terraform/` + the
  `compose.yaml` + `deploy.yml` workflow.** Not the cloud console,
  not the box's shell, not a developer's laptop. See
  `.claude/rules/infra-as-code.md` and `infra/RUNBOOK.md`.

## What this repo is

- Django 5.2 LTS project at `kasia/` with three apps: `inventory/`
  + `accounts/` (warehouse, under `/sklad/`) + `web/` (public
  marketing site at `/`).
- Models, services, views, forms, templates, admin, tests — all
  shipped per the screen-by-screen design in `context/screens/`
  (warehouse) and `context/public-site.md` (public site).
- Local dev runs via `make up` → `http://localhost/` (public
  homepage) and `http://localhost/sklad/` (warehouse app) against
  the full docker stack (web + Postgres 18 + Caddy). Same image
  we'll ship to Hetzner; differences live in `.env`. Tests run on
  the host via `make test` (`uv run pytest`).
- Hetzner box is **provisioned and live** (91.98.47.1, CPX22, fsn1).
  The `deploy.yml` workflow on `origin/main` **works**: a push to `main`
  builds the image, pushes to GHCR, SSHes to the box, migrates, and
  brings the stack up — i.e. **merging to `main` ships to production.**
  (The old "not yet provisioned / missing server host" note here was
  stale.)

## What this repo is not (yet)

- Not a production system. No real Kasia users on it.
- Not multi-tenant. Single-org, single-database, two branches
  (TYN + SEZ) per `context/warehouses.md`.
- Not connected to the účetní's software. Per
  [`screens/future-export-uctarne.md`](./context/screens/future-export-uctarne.md)
  CSV + PDF download is MVP; specific Pohoda XML / Money S3 lands
  after the first real month.
