# Kasia-warehouse

Warehouse-management tool for **Kasia vera s.r.o.**, a Czech B2B spice
distributor. One Django 5.2 project, two surfaces on one domain: a public
marketing site at `/` (the `web` app) and a login-gated warehouse app under
`/sklad/…` (the `inventory` + `accounts` apps). ~6 active operators.

## Run it locally

Full Docker stack (web + Postgres 18 + Caddy) — the same image shipped to prod:

```sh
make up          # http://localhost/ (public) and http://localhost/sklad/ (app)
make superuser   # first run only — create a local admin
make seed        # optional: walkthrough data (users, catalogue, movements)
make down        # stop the stack
```

## Test it

Tests run on the host via `uv` (not in the container):

```sh
make test        # uv run pytest
```

Python is `uv`-managed (Python 3.14); never `pip`/`poetry`. See
`.claude/rules/python-uses-uv.md`.

## Where to read next

- **`context/state.md`** — current status (Done / In progress / Next). Read first.
- **`context/architecture.md`** — code layout + the recipe for adding a
  screen / číselník / movement type.
- **`context/README.md`** — index of all foundational context + decisions.
- **`context/decisions/`** — numbered decision log (append-only).
- **`.claude/rules/`** — load-bearing rules governing how work happens here.
- **`infra/RUNBOOK.md`** — operating the live Hetzner box; deploys ship on
  push to `main`.
