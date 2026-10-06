# 0105 — Infra security hardening: Hetzner backups + on-box pg_dump, SSH hardening, Caddy headers, pinned images and actions (supersedes 0027's backup half)

**Date:** 2026-10-06
**Decider:** Matej
**Status:** Active

## Context

The repo is public and `https://kasia.cz` has been live on the Hetzner CPX22
(`91.98.47.1`) since 2026-07-14. A read-only infra audit on 2026-10-06 found:

- **No working backup.** The `backup` service (`offen/docker-volume-backup`)
  was never configured — `RESTIC_*` were never set, the 0027 Storage Box was
  never bought — and it mounted `/var/run/docker.sock`, which is
  root-equivalent. The only DB copies were manual laptop dumps.
- **`terraform apply` on main would have destroyed prod.** `user_data`,
  `ssh_keys` and `image` are ForceNew in the hcloud provider, and the live
  box's `user_data` already differs from `cloud-init.yaml`. A local plan
  against the real state on 2026-10-06 printed `hcloud_server.web must be
  replaced` (`1 to add, 1 to change, 1 to destroy`) — and the Postgres volume
  lives on that server's disk.
- **SSH.** Port 22 is world-open (by choice, 0025 / hetzner-admin skill);
  sshd had no drop-in (password auth on by Ubuntu default, root login
  allowed), no fail2ban. The GitHub deploy secret `SSH_KEY` is Matej's own
  `kasia_prod` key, which is also authorised for **root**.
- **Supply chain.** Floating image tags (`caddy:2-alpine`,
  `postgres:18-trixie`, `uv:0.5`); third-party actions referenced by mutable
  tags; no top-level `permissions:`; the deploy SSH step accepted any host key.
- **Headers.** No HSTS; `Server: gunicorn` / `Server: Caddy` advertised.

## Options considered

**Backups**

1. **Hetzner server backups only** (+20 % of the server price, 7 rolling
   daily images) **+ an on-box nightly `pg_dump` sidecar** so each image
   holds a consistent logical dump. Cheapest, zero new credentials.
2. Option 1 + an off-provider copy (Storage Box BX11 per 0027, or a scheduled
   pull to the laptop). Survives loss of the server / the Hetzner project.
3. Keep 0027 (restic → Storage Box). Never configured; needs a new secret,
   a new account and an always-on container with more privilege.

**Root SSH:** `PermitRootLogin no` vs `prohibit-password`.

**CSP:** a strict policy vs none this pass.

## Choice

**Backups — option 1, accepted with its known gap.**

- `infra/terraform/main.tf`: `backups = true`, `delete_protection = true`,
  `rebuild_protection = true` on `hcloud_server.web`, **plus**
  `lifecycle { ignore_changes = [user_data, ssh_keys, image] }` so those
  ForceNew attributes can never again turn an apply into a replace. With the
  lifecycle block the plan is `0 to add, 1 to change, 0 to destroy`
  (verified locally 2026-10-06). Deliberately rebuilding the box now means
  removing that block (and the protection flags) in a reviewed PR first.
- `compose.yaml`: the `backup` service is **removed** (and with it the
  docker-socket mount and `RESTIC_*`); a `db-dump` sidecar on the **same
  `postgres:18.6-trixie` image as `db`** runs `pg_dump -Fc` every 12 h into
  `/home/app/kasia-dumps` (outside the `/srv/kasia` checkout that deploy
  hard-resets; pre-created mode 700 by `deploy.yml` as `app`), keeps the
  newest 14 (≈ 7 days), and reports unhealthy when no dump is younger than
  26 h. Runs as `app`'s uid:gid (1000:1001, measured on the box). Umami's DB
  (`umami_pgdata`) is not dumped — analytics only; Hetzner's image covers it
  crash-consistently.
- **Known and accepted gap: Hetzner deletes a server's backups together
  with the server.** Deleting the server (API-token misuse, console mistake,
  a forced replace) loses the live DB *and* every Hetzner backup. Matej
  accepted this on 2026-10-06 instead of paying for an off-provider copy.
  Mitigations: `delete_protection` / `rebuild_protection`, the lifecycle
  block, and the **manual laptop dump** (`infra/RUNBOOK.md` § 4.1) as the
  only off-box path — take one before any risky infra change and
  periodically. This **partially supersedes 0027**: the hosting choice
  stands; the Storage Box / restic backup design does not.

**SSH — hardened, root stays key-only.**

- `cloud-init.yaml` (new boxes): `/etc/ssh/sshd_config.d/10-hardening.conf`
  with `PasswordAuthentication no`, `KbdInteractiveAuthentication no`,
  `PermitRootLogin prohibit-password`; `fail2ban` (sshd jail) and
  `unattended-upgrades` installed.
- `prohibit-password`, **not** `no`: `app` has `sudo: null`, so key-only root
  is the only clean admin path (`app`'s `docker` group is root-equivalent
  anyway, so a separate deploy key buys **revocability, not isolation**).
- Port 22 stays world-open (0025's operational choice — Matej moves networks).
- A **dedicated deploy key** replaces `kasia_prod` in the `SSH_KEY` secret,
  authorised on `app` only. `kasia_prod` stays on root **and** app as Matej's
  admin key (removing it from `app` would break the RUNBOOK and ops-skill
  `app@` paths).
- **The running box is changed by hand, once**, per the ordered procedure in
  `infra/RUNBOOK.md` § 10 — cloud-init only runs at first boot and is now
  ignored by Terraform. This is the documented one-off exception to
  `.claude/rules/infra-as-code.md`; the repo (cloud-init) stays the source of
  truth for the next rebuild.

**Caddy (prod `Caddyfile`, `kasia.cz` block only):**
`Strict-Transport-Security "max-age=31536000"` (no `includeSubDomains`, no
preload) and `-Server` / `-X-Powered-By` / `-Via`. HSTS is **not** set in
Django: `SECURE_HSTS_SECONDS` would also pin `https://localhost` through
`Caddyfile.dev`'s `tls internal`. `manage.py check --deploy` W004 is
therefore expected and accepted. **No CSP** this pass — sklad depends on
inline scripts/handlers and the public site on Umami + Google Maps embeds; no
XSS was found and `X-Frame-Options: DENY` already ships.

**Pins:** `caddy:2.11.4-alpine` (= the digest running on prod),
`postgres:18.6-trixie` (= the running server version; also CI's service
image), `ghcr.io/astral-sh/uv:0.5.31` (= what the floating `0.5` resolved to,
same digest — a uv bump is its own PR). `.dockerignore` gains `backups/`,
`scratchpad/`, `*.dump`, `*.sql.gz`; `.gitignore` gains `scratchpad/`.

**GitHub Actions:** top-level `permissions: {}` in every workflow, each job
lists only what it uses (`contents: read`; build adds `packages: write`;
deploy has none). Every action is pinned by commit SHA (tag in a trailing
comment). `checkout` runs with `persist-credentials: false`. The deploy step
pins the box's host key: `fingerprint:` = the **ECDSA** SHA256 fingerprint,
because drone-ssh 1.8.2 (golang.org/x/crypto v0.45.0, no `HostKeyAlgorithms`
override) negotiates ECDSA first — verified 2026-10-06 by a Go probe on that
x/crypto version and `ssh-keyscan -t ecdsa`. A mismatch aborts before any
remote command runs.

## Rationale

- The real risk was data loss, not intrusion: a misconfigured backup plus a
  latent destroy-on-apply. Fixing both costs one Terraform block, one flag
  and a ~40-line sidecar.
- Hetzner backups + an in-image logical dump is the smallest thing that
  actually runs. The off-provider gap is real but was explicitly accepted;
  the laptop dump covers it manually.
- Pins and SHA-pinned actions make every deploy reproducible and remove the
  "someone moved a tag" path, at the price of manual bumps.
- `right-sized-for-small-business.md`: no Vault, no bastion, no VPN, no
  WAF; boring defaults on the one box.

## Consequences

- **Matej, before/after merge** (full order in RUNBOOK § 10): run the local
  `terraform plan` (must say `0 to destroy`) and `apply`; perform the live-box
  SSH steps; after the merge deploy, confirm a dump in `~/kasia-dumps` and the
  headers with `curl -sI https://kasia.cz/`.
- The first deploy after merge recreates `db`, `umami-db` (image string
  change → a few seconds of DB restart) and `proxy` (picks up the new
  Caddyfile without the manual force-recreate), and removes the orphaned
  `backup` container.
- A rebuilt box gets **new host keys** → update `fingerprint:` in
  `deploy.yml`, and re-add the deploy public key to `app` (cloud-init seeds
  `app` from root's keys only).
- Image / action bumps are now explicit PRs.
- Restore procedure + drill record: RUNBOOK § 4 (first drill 2026-10-06:
  all 31 public tables matched prod row-for-row).

## Relates to

- [`0022`](./0022-container-image.md) — Dockerfile (uv pin).
- [`0023`](./0023-runtime-orchestration-compose.md) — compose services.
- [`0024`](./0024-tls-caddy.md) — Caddy headers.
- [`0025`](./0025-iac-terraform-hcloud.md) — Terraform + cloud-init; lifecycle block.
- [`0026`](./0026-ci-cd-github-actions.md) — workflow permissions / pins / host key.
- [`0027`](./0027-hosting-hetzner.md) — backup half superseded here.
- [`0040`](./0040-operator-crud-tiering.md) — role tiering; app-level
  hardening (IDOR, roles, lockout) is the separate app decision 0104, not
  this one.
