# Kasia-warehouse — agent instructions

This repository is the warehouse management tool for **Kasia vera s.r.o.**,
a Czech B2B spice distributor. The stack is locked, the operator-facing
MVP is built (14 screens + Pass 5 operator CRUD + Pass 6 reorder
threshold / reservations / low-stock summary), and the system runs
locally via `make up` against the same Docker image we'll ship to the
Hetzner box. Hetzner provisioning + the 14-day shadow run come last.

## Read in this order

1. **`context/state.md`** — current project status (Done / In progress / Next).
   This is the cold-start anchor. Always read first.
2. **`context/README.md`** — index of all foundational context, with the
   recommended reading order.
3. **`.claude/rules/`** — load-bearing rules that govern how you work in this
   repo. Pay particular attention to `decision-log-discipline.md`,
   `state-file-discipline.md`, and `right-sized-for-small-business.md`.
4. **`context/decisions/`** — read in numeric order. 0028–0034 supersede
   parts of 0001–0013 (Petr's 2026-06-09 brief); 0044 supersedes part
   of 0039 (reservations). The tech-stack layer is 0014–0027.

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

- Django 5.2 LTS app at `inventory/` + `accounts/` + `kasia/`.
- Models, services, views, forms, templates, admin, tests — all
  shipped per the screen-by-screen design in `context/screens/`.
- Local dev runs via `make up` → `http://localhost/` against the
  full docker stack (web + Postgres 18 + Caddy). Same image we'll
  ship to Hetzner; differences live in `.env`. Tests run on the
  host via `make test` (`uv run pytest`).
- Hetzner box is **not yet provisioned**. The `deploy.yml` workflow
  on `origin/main` keeps failing on the SSH step ("missing server
  host") — that's the expected pre-Hetzner state, not a regression.
  Provisioning + the 14-day shadow run come after Matej finishes
  local walkthrough.

## What this repo is not (yet)

- Not a production system. No real Kasia users on it.
- Not multi-tenant. Single-org, single-database, two branches
  (TYN + SEZ) per `context/warehouses.md`.
- Not connected to the účetní's software. Per
  [`screens/future-export-uctarne.md`](./context/screens/future-export-uctarne.md)
  CSV + PDF download is MVP; specific Pohoda XML / Money S3 lands
  after the first real month.
