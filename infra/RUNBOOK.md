# Kasia infra RUNBOOK

Operational playbook for the production VPS. Pairs with decisions
[`0014`](../context/decisions/0014-language-python-uv.md)–[`0027`](../context/decisions/0027-hosting-hetzner.md)
and [`.claude/rules/infra-as-code.md`](../.claude/rules/infra-as-code.md).

**Status:** the production box is **not provisioned yet** (as of
2026-06-08). Everything below is the one-time migration path
between local Docker Compose development and a live Hetzner box.

## 0. Local development (until migration)

Day-to-day development runs entirely off `docker compose up` against
a local stack:

```
cp .env.example .env
docker compose build
docker compose up
```

That brings up `web` + `db` + `proxy`. The `backup` service is
profiled to `prod` only and stays out of the local loop. Visit
http://localhost/healthz; expect `200 OK`.

## 1. First-time provisioning (Hetzner box)

Run from Matej's workstation, **not from CI**.

### 1.1 Generate or pick an SSH key

```
ssh-keygen -t ed25519 -f ~/.ssh/kasia_prod -C kasia-prod
```

### 1.2 Run Terraform

```
cd infra/terraform
export HCLOUD_TOKEN=...                       # from Hetzner console → Security
export TF_VAR_hcloud_token="$HCLOUD_TOKEN"
export TF_VAR_ssh_pub_key="$(cat ~/.ssh/kasia_prod.pub)"
export TF_VAR_admin_ip="$(curl -s https://ifconfig.me)/32"

terraform init
terraform plan
terraform apply
```

Note the `server_ipv4` output — that's the box's IP.

### 1.3 Populate the on-box `.env`

```
ssh -i ~/.ssh/kasia_prod root@<server_ipv4>
# (or `app@<server_ipv4>` once SSH key sync completes)
cd /srv/kasia
cp .env.example .env
$EDITOR .env                                  # fill in real secrets
chmod 600 .env
```

`.env` is **never** committed. Restic secrets
(`RESTIC_REPOSITORY`, `RESTIC_PASSWORD`) need a separate decision
on the Storage Box endpoint before backups run.

### 1.4 Set GitHub Actions secrets

In the GitHub repo settings → Secrets and variables → Actions:

| Secret      | Value                                                  |
|-------------|--------------------------------------------------------|
| `SSH_KEY`   | contents of `~/.ssh/kasia_prod` (the private key)      |

Host and user are hardcoded literals in `.github/workflows/deploy.yml`
(`host: 91.98.47.1`, `username: app`) — non-secret. If the box is
re-IP'd, edit the workflow rather than rotating a secret. GHCR push
is authenticated by the built-in `GITHUB_TOKEN`; no PAT.

### 1.5 Trigger the first deploy

Push any commit to `main`, or run the `deploy` workflow manually
from the Actions tab. Watch:

- Build job pushes `ghcr.io/<org>/<repo>:sha-<commit>` + `:latest`.
- Deploy job SSHes in, pulls, runs migrations, swaps the container.

Verify: `curl http://<server_ipv4>/healthz` returns `200`.

### 1.6 Set up backups

Create the Storage Box via the Hetzner console (BX11 in the same
region). On the box:

```
restic -r sftp:u123456@u123456.your-storagebox.de:/kasia init
```

Record the repo path + password in the on-box `.env`
(`RESTIC_REPOSITORY`, `RESTIC_PASSWORD`). Then:

```
docker compose --profile prod up -d backup
```

Restore drill: see § 4.

## 2. Routine deploy

Push to `main`. The `deploy.yml` workflow:

1. Builds and pushes the image to GHCR.
2. SSHes to the box.
3. Runs `docker compose run --rm web python manage.py migrate
   --noinput` **before** swapping the container.
4. `docker compose up -d --remove-orphans` swaps.
5. `docker image prune -f` reclaims disk.

If migrations fail, the old container keeps serving and the
workflow shows a red X — no auto-rollback, just no swap.

## 3. Rollback

When a deploy turns out broken:

```
# On the box.
cd /srv/kasia
export WEB_IMAGE=ghcr.io/<org>/<repo>:sha-<previous-good-commit>
docker compose pull web
docker compose up -d --remove-orphans
```

Or — easier — re-tag the previous good `sha-*` as `latest` in GHCR
and re-run the `deploy.yml` workflow on the *previous* commit via
`workflow_dispatch`. No auto-rollback path; ~6 users can tolerate
a manual revert.

## 4. Backup restore drill

A backup that hasn't been restored doesn't exist
([`.claude/rules/right-sized-for-small-business.md`](../.claude/rules/right-sized-for-small-business.md)).
Cadence: TBD once we have operating history; aim quarterly.

```
docker compose stop web
restic -r $RESTIC_REPOSITORY snapshots
restic -r $RESTIC_REPOSITORY restore <id> --target /tmp/restore
# Drop into a fresh pgdata volume, point the db service at it.
docker compose up -d
```

Retention policy SOP — number of daily / weekly / monthly snapshots
to keep — is currently open
([`../context/open-questions.md`](../context/open-questions.md)
§ Decide later). Write the SOP into this file once a month of real
operation gives us shape.

## 5. Domain cutover to HTTPS at `kasia.cz`

Full plan and rationale: [`../context/decisions/0056-domain-cutover-https.md`](../context/decisions/0056-domain-cutover-https.md).
Canonical host is the apex `kasia.cz`; `www.kasia.cz` → 301 → `kasia.cz`.

**443 is already open** on the live firewall
(`infra/terraform/main.tf`, firewall id 11145413) — **no Terraform
change** at cutover.

**The hard constraint:** Caddy cannot get a Let's Encrypt cert until DNS
resolves to the box. Activating the hostname Caddyfile *before* the A
record points here takes the IP site offline (the `:80` catch-all is gone)
and makes Caddy fail against ACME, risking the LE rate limit. Since
`deploy.yml` does `git reset --hard origin/main`, a manual on-box Caddyfile
edit would be overwritten on the next deploy — so the Caddyfile change is
**held on an unmerged branch and merged only after `dig` confirms DNS.**

### 5a. Phase A — prime prod now (safe; IP site stays up on HTTP)

The Django HTTPS settings already live (env-gated) in
[`../kasia/settings/base.py`](../kasia/settings/base.py) and default to
today's behaviour until the on-box `.env` opts in:

- `SECURE_PROXY_SSL_HEADER` — so password-reset e-mails
  (`accounts/views.py`) and the sitemap (`web/views.py`) emit
  `https://kasia.cz/...` instead of `http://91.98.47.1/...`.
- `CSRF_TRUSTED_ORIGINS` (from `DJANGO_CSRF_TRUSTED_ORIGINS`) — required
  for cross-origin POSTs behind the TLS-terminating proxy, most visibly
  the public **kontakt** form (per
  [`../context/decisions/0051-public-site-ia-and-content.md`](../context/decisions/0051-public-site-ia-and-content.md))
  and any warehouse form.
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` (from
  `DJANGO_SECURE_COOKIES`, default off).

On the box, pre-set the **safe** values in `.env` and restart web:

```
DJANGO_ALLOWED_HOSTS=kasia.cz,www.kasia.cz,91.98.47.1,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://kasia.cz,https://www.kasia.cz
# leave DJANGO_SECURE_COOKIES unset/0 — cookies must still flow over HTTP
```

⚠️ Keep `127.0.0.1,localhost` in `DJANGO_ALLOWED_HOSTS` — the web
container healthcheck hits `http://127.0.0.1:8000/healthz` and
`CommonMiddleware` validates Host under `DEBUG=False`; drop them and the
deploy goes unhealthy. Keep `91.98.47.1` so the IP keeps working through
the transition.

After this, the site is unchanged (HTTP on the IP) but the box is primed.

### 5b. Phase B — the flip (only when DNS is pointed at the box)

The Caddyfile + compose change is held in a **separate, unmerged PR**:

- [`../Caddyfile`](../Caddyfile): replace the `:80 { ... }` block with the
  `kasia.cz { ... }` reverse-proxy block + a `www.kasia.cz` block that
  `redir https://kasia.cz{uri} permanent`.
- [`../compose.yaml`](../compose.yaml): uncomment the `"443:443"` port
  publish under the `proxy` service.

Then, in order:

1. Tell the domain manager: **add** `A kasia.cz → 91.98.47.1` and
   `A www.kasia.cz → 91.98.47.1`. **Do not touch MX / mail records.**
2. Confirm `dig +short kasia.cz` and `dig +short www.kasia.cz` →
   `91.98.47.1`.
3. **Only then** merge the held PR to `main` → auto-deploy activates the
   Caddyfile + 443. Caddy provisions the cert on first hit.
4. On the box, set `DJANGO_SECURE_COOKIES=1` in `.env` and restart web.
5. (Optional, cosmetic) update the `host:` literal in
   `.github/workflows/deploy.yml` to the hostname — the IP still works
   since DNS just resolves to it.

Verify: `curl -I http://kasia.cz` → 301/308 → `https://kasia.cz`;
`curl -Iv https://kasia.cz` → valid LE cert + 200;
`curl -I https://www.kasia.cz` → 301 → `https://kasia.cz`;
`docker compose logs proxy` → cert obtained, no ACME errors.

## 6. Things that are not in this RUNBOOK on purpose

- **Observability / log shipping / metrics / alerting.** ~6 users;
  per [`../.claude/rules/right-sized-for-small-business.md`](../.claude/rules/right-sized-for-small-business.md),
  add when there's operating pain to justify it. Caddy + gunicorn
  logs to stdout; `journalctl -u docker` covers the rest.
- **A staging environment.** Prod-only by
  [`../context/decisions/0026-ci-cd-github-actions.md`](../context/decisions/0026-ci-cd-github-actions.md).
- **Auto-rollback.** Manual per § 3.
