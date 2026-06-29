**Infra changes go through code in this repo. The cloud console, the box's shell, and a developer's laptop are not deployment surfaces.**

This rule lands with decisions [`0022`](../../context/decisions/0022-container-image.md)–[`0027`](../../context/decisions/0027-hosting-hetzner.md). It is the operational counterpart to `no-premature-tech-choices.md`: once a layer is chosen, *how* it changes is also fixed.

## Hard constraints

- **All infra changes go through `infra/terraform/`.** No manual `hcloud` console changes. If drift is found, codify it before doing anything else.
- **Container changes go through `Dockerfile` + `compose.yaml`.** No `docker run` ad-hoc on the box for app processes. `docker exec` for inspection is fine; `docker exec` to write app state is not.
- **Secrets are out of the repo.** GitHub Actions secrets for build/deploy time (`SSH_HOST`, `SSH_USER`, `SSH_KEY`, plus the built-in `GITHUB_TOKEN` for GHCR). On-server `.env` (chmod 600, never in git) for runtime. **Never commit `.env`, never paste secrets into the repo, PRs, or commit messages.**
- **Deploys: push to `main` is the only path to prod.** No `docker compose up` from a developer laptop against the production box. The `deploy.yml` workflow is the entry point.
- **Rollback is image re-tag, not git revert.** Re-tag the previous `sha-*` image as `latest` in GHCR and re-deploy, per [`infra/RUNBOOK.md`](../../infra/RUNBOOK.md) § Rollback. Don't bypass the image registry by `git revert + redeploy`; that risks shipping a fresh build with subtle differences.
- **Terraform apply is manual.** CI runs `fmt -check`, `validate`, `plan`; only Matej runs `terraform apply` from a workstation with `HCLOUD_TOKEN` in env. See [`decisions/0025`](../../context/decisions/0025-iac-terraform-hcloud.md) for the reasoning.
- **Local development is the same compose stack.** `docker compose up` runs the same `Dockerfile` and `compose.yaml` that ship to prod; differences live in `.env`. No `compose.dev.yaml`. If a dev-only knob is needed, drive it from `.env`.
- **Site-specific knobs are per-deployment `.env`, never committed.** The HTTPS/domain settings (`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_COOKIES`, per [`decisions/0056`](../../context/decisions/0056-domain-cutover-https.md)) live only in the on-box `.env` and are *documented* (not set) in `.env.example`. Their reader code in `kasia/settings/base.py` defaults to today's HTTP-only behaviour, so the same image runs both locally and on prod.

## Why this rule exists

The system is operated by one person (Matej) supporting ~6 users in a Czech B2B distributor. The failure mode to avoid is not a bad deploy — it's an *invisible* config change that nobody can reproduce a year later. IaC + image-tag deploys + on-box `.env` is the smallest discipline that keeps the box reproducible without paying for a real ops team.

## Cross-references

- [`no-premature-tech-choices.md`](./no-premature-tech-choices.md) — gates *what* the stack is.
- [`right-sized-for-small-business.md`](./right-sized-for-small-business.md) — gates the *shape* of the deployment. This rule is the *how*.
- [`infra/RUNBOOK.md`](../../infra/RUNBOOK.md) — the operational playbook.
