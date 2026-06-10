# 0023 — Runtime orchestration: Docker Compose v2

## Context

The deployment shape called out in
[`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
is a single VPS, one app, one DB. We need a way to run the app
container ([`0022`](./0022-container-image.md)) alongside Postgres
([`0016`](./0016-database-postgres.md)) and a reverse proxy
([`0024`](./0024-tls-caddy.md)) and a backup sidecar — locally for
dev and on the production VPS for prod.

Kubernetes / Nomad / Swarm are conference-talk-shaped for a 6-user
system. The two real candidates are systemd-managed `podman` /
`docker run` and Docker Compose v2.

**Development workflow:** the same `compose.yaml` is the developer
loop. `docker compose up` brings up `web` + `db` + `proxy` on the
laptop. The production box runs the same file with a `.env` that
points at production secrets. No separate `compose.dev.yaml` —
configuration differences live in `.env`. The Hetzner box is
**provisioned at migration time** (see
[`0027`](./0027-hosting-hetzner.md)); until then, all work happens
against local Compose.

## Options considered

- **Docker Compose v2.** Declarative YAML for the service set,
  named volumes, networks, healthchecks. Docker Engine includes
  Compose v2 as a first-party CLI subcommand. Same artefact local +
  prod.
- **Coolify / Dokploy / CapRover.** Self-hosted PaaS layers above
  Docker. Add a web UI for deploys + a bunch of plumbing we don't
  need.
- **Plain systemd + podman.** Works, but loses the declarative
  service graph (depends_on, healthchecks) without writing more
  unit files.
- **`docker run` from a script.** Loses the YAML manifest;
  imperative; harder to reason about.

## Choice

**Docker Compose v2** running on the VPS via the Docker Engine's
Compose plugin. One `compose.yaml` at the repo root, used by both
local dev and prod (env-driven differences). Services:

- **`web`** — built from [`../../Dockerfile`](../../Dockerfile)
  per [`0022`](./0022-container-image.md). Runs gunicorn +
  WhiteNoise. Depends on `db`. Healthcheck hits `/healthz` (200).
  Listens on the internal Compose network only; not published to
  the host. **In production** the image is pulled from GHCR by
  tag (`sha-<commit>` or `latest`); locally it is built from
  source.
- **`db`** — `postgres:18-trixie`. Named volume `pgdata`.
  **Localhost-bound only** (`127.0.0.1:5432:5432`) for emergency
  psql access; not exposed externally. Env-driven password from
  `POSTGRES_PASSWORD`. Healthcheck: `pg_isready`.
- **`proxy`** — `caddy:2-alpine`. Mounts the
  [`../../Caddyfile`](../../Caddyfile) read-only. Publishes
  `:80` (and `:443` when a domain lands — see
  [`0024`](./0024-tls-caddy.md)). Healthcheck: HTTP 200 against
  itself.
- **`backup`** — `offen/docker-volume-backup` running on a cron
  schedule. Dumps Postgres (`pg_dump` against `db`) and snapshots
  the `pgdata` volume, then ships restic-encrypted archives to the
  Storage Box per [`0027`](./0027-hosting-hetzner.md). Restic repo
  password from `.env`. **Disabled by default in local dev** (the
  service has a `profiles: [prod]` declaration so `docker compose
  up` locally skips it).

Named volumes: `pgdata` (the Postgres data dir),
`caddy_data` + `caddy_config` (TLS state when a domain lands).

## Rationale

- One declarative file is the smallest viable orchestration unit
  for this scale.
- Same artefact local + prod means dev/prod parity without
  duplicate config.
- Localhost-binding the DB removes the most common Postgres-on-VPS
  attack surface (open 5432 to the internet).
- The backup service runs as an ordinary container next to the app;
  no separate orchestrator.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Local dev loop — `docker compose up` brings the full stack up on
  a laptop. This is the *only* dev path until the Hetzner box is
  provisioned.
- [`0026`](./0026-ci-cd-github-actions.md) — the deploy step is a
  thin SSH wrapper around `docker compose pull && docker compose
  up -d`.
- [`0027`](./0027-hosting-hetzner.md) — the VPS only needs Docker
  Engine + Compose plugin; nothing else app-specific lives at the
  OS level.

**Forecloses (without follow-on decision):**

- Kubernetes / Nomad / Swarm.
- Self-hosted PaaS layers (Coolify, Dokploy, CapRover).
- Running the DB on a separate machine (until a future decision
  says otherwise).

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Single-VPS-deploy + two-tier preference.

**Makes implementable (0001–0013):**

- The full app stack is reproducible from `compose.yaml` —
  developers / contractors get the same DB version, same Pango
  version, same Caddy version as production.
