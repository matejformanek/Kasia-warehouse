# 0022 — Container image: multi-stage Dockerfile on `python:3.14-slim-trixie`

## Context

The deployment shape committed in
[`0023`](./0023-runtime-orchestration-compose.md) is Docker Compose
v2 on a single VPS. The container image is the unit of deployment.

The app's runtime needs:

- Python 3.14 ([`0014`](./0014-language-python-uv.md)).
- The Pango stack for WeasyPrint
  ([`0017`](./0017-pdf-weasyprint.md)).
- `psycopg[binary]` ([`0016`](./0016-database-postgres.md)) — no
  PostgreSQL client libs needed at runtime (psycopg-binary bundles
  its own libpq).
- gunicorn + WhiteNoise for serving HTTP + static files.
- A non-root user — defence in depth for the runtime.
- Reproducible installs — `uv sync --frozen` against
  `pyproject.toml` + `uv.lock`.

Multi-stage build keeps the runtime image small: the builder stage
has uv + dev headers, the runtime stage has only what's needed to
serve requests.

**Development uses the same image locally** via
[`compose.yaml`](../../compose.yaml) — `docker compose up` is the
developer's primary loop until the production box is provisioned.
The Dockerfile is therefore both the dev and prod artefact; there
is no separate `Dockerfile.dev`.

## Options considered

- **`python:3.14-slim-trixie` base, multi-stage with uv copied from
  `ghcr.io/astral-sh/uv` (pinned).** Smallest viable footprint
  for a Django + WeasyPrint app; trixie is the current Debian
  stable.
- **`python:3.14-alpine`.** Smaller still, but Alpine's musl libc
  + Pango have historically been wobbly; not worth the saved MB.
- **`python:3.14` (full Debian).** ~900 MB; carries dev tooling we
  don't need at runtime.
- **Single-stage build.** Smaller Dockerfile but the image carries
  uv, build deps, and intermediate artefacts. Multi-stage costs
  nothing readable-wise and halves the image size.
- **Distroless base.** Tempting for minimal attack surface, but
  WeasyPrint wants the Pango runtime which is awkward on
  distroless. Not worth the engineering for ~6 users.

## Choice

**Multi-stage Dockerfile based on `python:3.14-slim-trixie`.**

Stages:

1. **`builder`** — `python:3.14-slim-trixie`. Copies `uv` from
   `ghcr.io/astral-sh/uv:latest` (pinned to a specific tag at build
   time via the deploy job). Runs `uv sync --frozen --no-dev` into
   a project-local `.venv`.
2. **`runtime`** — `python:3.14-slim-trixie`. Installs Pango runtime
   deps (`libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
   fonts-dejavu-core`) + `tini`. Adds non-root `app` user. Copies
   the `.venv` from the builder stage. Copies app source. Runs
   `python manage.py collectstatic --noinput` so WhiteNoise has
   the compressed-manifest output ready at start.

Image size target: **~180–220 MB compressed**. Verified locally
with `docker image ls`.

Entrypoint is `tini -- gunicorn kasia.wsgi:application --bind
0.0.0.0:8000`. Migrations are *not* run on container start —
they're run by the CI/CD deploy job before container swap
([`0026`](./0026-ci-cd-github-actions.md)).

## Rationale

- Slim-trixie is the official Python image's "small but
  Debian-shaped" line — Pango deps install cleanly via apt; no
  Alpine surprises.
- Multi-stage halves the image; the builder layer can be cached
  separately from the runtime layer for fast incremental builds.
- Non-root `app` user is a cheap defence-in-depth win.
- `tini` as PID 1 handles signal forwarding so `docker compose
  stop` exits cleanly.
- Pinning `uv` from `ghcr.io/astral-sh/uv` (vs apt-installing or
  curl-pipe) means reproducible toolchain bytes on every build.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- [`0023`](./0023-runtime-orchestration-compose.md) — the `web`
  service references this image.
- [`0026`](./0026-ci-cd-github-actions.md) — the CI build job
  produces this image, tags it `sha-<commit>` + `latest`, pushes
  to GHCR.
- Local development — `docker compose build` builds the same
  image that ships to prod.

**Forecloses (without follow-on decision):**

- Alpine base images.
- Distroless / scratch bases.
- Migrations-on-container-start patterns.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Single-VPS-deploy preference; the container is the deploy unit.

**Makes implementable (0001–0013):**

- N/A directly — this is infrastructure plumbing. It carries the
  app, doesn't shape its data model.
