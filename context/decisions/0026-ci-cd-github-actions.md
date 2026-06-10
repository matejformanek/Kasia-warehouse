# 0026 — CI/CD: GitHub Actions, push-to-main → prod

## Context

With the image
([`0022`](./0022-container-image.md)), the orchestration
([`0023`](./0023-runtime-orchestration-compose.md)), and the IaC
([`0025`](./0025-iac-terraform-hcloud.md)) committed, deployment
needs an automation path. Constraints:

- One environment: **prod only**, no staging. ~6 users; a staging
  box doubles cost for no operating win.
- One developer day-to-day (Matej). The pipeline must work
  end-to-end without manual artefact shuffling.
- The repo is on GitHub. The image registry is **GitHub Container
  Registry (GHCR)** so authentication is via the workflow's
  `GITHUB_TOKEN` (no long-lived PATs).

**Important nuance:** the production VPS does not exist yet in this
pass. The `deploy.yml` workflow is **scaffolded but not active**
until Matej provisions the box and sets the `SSH_*` secrets; the
push-to-`main`→deploy path is dormant by design. Until then,
`docker compose up` against the local stack is the only deploy
target.

Watchtower (auto-pull-and-restart from the registry) was rejected:
it masks deploy failures (no surfaced error when migration fails;
no rollback trigger).

## Options considered

- **GH Actions: CI on every push/PR; deploy on push-to-main.**
  Same repo, same secrets surface; no third-party CI service.
- **GH Actions for CI + Watchtower on the VPS for deploy.**
  Simpler in shape but Watchtower's failure-handling story is
  weak — a failed migration would leave the cluster in an
  inconsistent state with no audit trail.
- **GH Actions + ArgoCD / Flux.** Pull-based GitOps; nice for
  multi-cluster, overkill for one VPS.
- **GitLab CI / Drone / CircleCI.** No reason to leave GitHub.
- **Manual `docker compose pull && up -d` via SSH.** Day-one only;
  the discipline rots within a month.

## Choice

**GitHub Actions.** Three workflows under
[`../../.github/workflows/`](../../.github/workflows/):

1. **`ci.yml`** — on every push and PR:
   `uv sync` → `uv run ruff check` → `uv run python manage.py
   check` → `uv run pytest`. Uses `actions/checkout@v4` and
   `astral-sh/setup-uv@v3`.
2. **`deploy.yml`** — on push to `main`:
   - Build job: `docker buildx build` against the multi-stage
     Dockerfile; push to GHCR tagged `sha-<commit>` + `latest`.
     Auth via `${{ secrets.GITHUB_TOKEN }}`.
   - Deploy job: SSH to the VPS via `appleboy/ssh-action`. Runs:
     ```
     docker compose pull
     docker compose run --rm web python manage.py migrate --noinput
     docker compose up -d --remove-orphans
     docker image prune -f
     ```
     Migrations run **before** the container swap. If migrations
     fail, the old container keeps serving.
3. **`terraform.yml`** — on PR touching `infra/`:
   `terraform fmt -check`, `terraform validate`, `terraform plan`
   posted as a PR comment. **No `terraform apply`** — apply
   happens manually from Matej's workstation
   ([`0025`](./0025-iac-terraform-hcloud.md)).

Required GH Actions secrets (set once by Matej; documented in
[`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md)):
`SSH_HOST`, `SSH_USER`, `SSH_KEY` (private key). GHCR push uses
the built-in `GITHUB_TOKEN` — no PAT.

**Rollback:** re-tag the previous `sha-<commit>` image as `latest`
in GHCR and re-trigger the deploy job (or do it locally and `docker
compose pull && up -d` over SSH). One-liner; documented in
[`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md). No auto-rollback
in MVP — ~6 users tolerate a manual revert.

## Rationale

- Push-to-main is the minimum-friction deploy story for a solo
  developer; review happens on PR before merge, not after.
- Migrations-before-swap means a broken migration aborts the
  deploy and leaves the previous container running.
- GHCR + `GITHUB_TOKEN` removes the long-lived PAT class of risk.
- No staging is a deliberate cost choice; the CI test suite is the
  pre-prod gate.
- Watchtower's rejection follows the
  [`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
  "backups matter more than uptime" line — visible deploy failures
  are more valuable than seamless silent failures.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The first deploy is one button: push to main once the box is
  provisioned and secrets are set.
- PR-level confidence: every change runs `ruff` + `manage.py
  check` + `pytest` before merge.
- Rollback is a one-liner.

**Forecloses (without follow-on decision):**

- Watchtower / auto-pull on the box.
- Staging environment.
- Multi-environment CD (prod is the only target).

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Single-VPS-deploy preference, automated.

**Makes implementable (0001–0013):**

- N/A directly — pipeline plumbing.

**Operational dependency:** the `deploy.yml` job will not succeed
until [`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md) one-time
setup is complete (box provisioned, `.env` on box, GH secrets set).
The workflow is scaffolded but dormant until then.
