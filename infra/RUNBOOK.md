# Kasia infra RUNBOOK

Operational playbook for the production VPS. Pairs with decisions
[`0014`](../context/decisions/0014-language-python-uv.md)–[`0027`](../context/decisions/0027-hosting-hetzner.md)
and [`.claude/rules/infra-as-code.md`](../.claude/rules/infra-as-code.md).

**Status:** the production box is **provisioned and live** — `91.98.47.1`
(CPX22, Falkenstein fsn1), serving `https://kasia.cz` since 2026-07-14. A push to
`main` deploys via `deploy.yml`. § 1 below is the one-time provisioning path
(kept for reference / rebuild); §§ 2–8 are the live operational playbook.

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
4. On the box, set `DJANGO_SECURE_COOKIES=1` in `.env` and recreate web
   (`docker compose --profile prod up -d --force-recreate web` — a plain
   `restart` does **not** re-read `env_file`).
5. (Optional, cosmetic) update the `host:` literal in
   `.github/workflows/deploy.yml` to the hostname — the IP still works
   since DNS just resolves to it.

⚠️ **Caddyfile changes need a proxy recreate, not just a deploy.** The
Caddyfile is a **single-file bind mount** (`./Caddyfile:/etc/caddy/...`),
and `git reset --hard` replaces the file with a new inode — the running
container keeps seeing the **old** file, so neither the deploy nor a
`caddy reload` picks the change up. After any Caddyfile-touching merge,
run `docker compose --profile prod up -d --force-recreate proxy` on the
box (a few seconds of downtime; certs persist in the `caddy_data`
volume). Deploys that change the `proxy` service itself (ports, image)
recreate it automatically — that's why the Phase B cutover worked without
this step.

⚠️ **`WEB_IMAGE` trap on manual recreates.** `deploy.yml` exports
`WEB_IMAGE=ghcr.io/…:sha-*` only inside its own SSH session — it is not
persisted anywhere on the box. A manual `docker compose up` without
`WEB_IMAGE` in the environment falls back to compose's default
(`kasia-web:local`), silently swapping prod onto whatever stale local
image the box still has (this caused a brief outage at the 2026-07-14
cutover). The on-box `.env` therefore **pins `WEB_IMAGE` to the currently
deployed `sha-*` tag**; each deploy still overrides it via the exported
env var (shell env beats `.env` in compose precedence), but keep the pin
roughly current when doing manual work, and never remove it.

Verify: `curl -I http://kasia.cz` → 301/308 → `https://kasia.cz`;
`curl -Iv https://kasia.cz` → valid LE cert + 200;
`curl -I https://www.kasia.cz` → 301 → `https://kasia.cz`;
`docker compose logs proxy` → cert obtained, no ACME errors.

## 6. Analytics (Umami)

Self-hosted Umami v3 per
[`../context/decisions/0076-public-site-analytics.md`](../context/decisions/0076-public-site-analytics.md).
Two prod-profile services in [`../compose.yaml`](../compose.yaml): `umami`
(app, pinned release tag) + `umami-db` (own Postgres cluster on the
`umami_pgdata` volume — fully separate from the warehouse DB). Caddy serves
it at **`https://analytics.kasia.cz/`** (wildcard `*.kasia.cz` A record;
cert auto-provisioned like the apex).

- **Log in:** `https://analytics.kasia.cz/`, user `admin`. A fresh install
  boots with password `umami` — **rotate it immediately** (first boot
  2026-07-14 did this; the rotated password was left one-time-fetchable at
  `/home/app/umami-admin-pw.txt`, mode 600 — fetch and `rm`).
- **Website entries:** Nastavení → Websites in the Umami UI. The `kasia.cz`
  entry exists; its ID is wired as `UMAMI_WEBSITE_ID` in `/srv/kasia/.env`.
  To add another site, create the entry, copy its ID — a second site needs
  its own template wiring, so that's a code change, not just config.
- **Back-fill / rotate `UMAMI_WEBSITE_ID`:** edit `/srv/kasia/.env`, then
  `docker compose --profile prod up -d --force-recreate web` (a plain
  `restart` does **not** re-read `env_file`). The tracker tag is
  conditional on the var, so an empty value simply disables tracking.
- **Caddyfile changes** (including the `analytics.kasia.cz` block) need the
  **proxy force-recreate** after the merge deploys — see the single-file
  bind-mount trap in § 5b.
- **Backups:** `umami_pgdata` is mounted read-only into the `backup`
  service; the nightly 03:00 restic run to the Storage Box covers it
  alongside `pgdata`. Restore works the same as § 4, targeting
  `umami_pgdata`.
- **Upgrades:** bump the pinned `umamisoftware/umami:<version>` tag in
  `compose.yaml` via PR (record the image digest in the PR description);
  the container runs its own DB migrations on boot.
- **Rollback / kill switch:** `docker compose rm -fs umami umami-db` on the
  box stops analytics without touching the site — the tracker tag is
  env-gated and the public pages render regardless of whether the script
  loads. Full removal is a compose revert PR.

## 7. Production data reset (go-live, one-time)

Wipes prod back to a clean baseline at go-live, keeping only the owner/admin
users, both branches, Settings + recipients, and the seeded counterparties.
Per [`../context/decisions/0087-production-data-wipe-for-go-live.md`](../context/decisions/0087-production-data-wipe-for-go-live.md).
**Backup first — this is a hard delete.**

### 7.1 Back up prod off-repo (never commit; `backups/` is gitignored)

```
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose exec -T db pg_dump -U kasia -d kasia --clean --if-exists --no-owner" \
  | gzip > backups/prod-pre-golive-wipe-$(date +%F).sql.gz
gunzip -t backups/prod-pre-golive-wipe-$(date +%F).sql.gz   # verify integrity
chmod 600 backups/prod-pre-golive-wipe-*.sql.gz
```

The dump holds SMTP creds, password hashes, and customer PII — `chmod 600`,
never `git add -f`, never paste into PRs/commits.

### 7.2 Run the wipe (via the deploy.yml one-off-container path)

The command must already be on the box (merged to `main` → deployed). Dry-run
first, review the before→after table, then commit:

```
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose run --rm web python manage.py reset_production_data"
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose run --rm web python manage.py reset_production_data --commit"
```

Use `docker compose run --rm web` (a fresh one-off container, like the `migrate`
step in `deploy.yml`) — **not** a `make` target (forbidden on the box). The wipe
is one `transaction.atomic()`; a failed/aborted run leaves prod untouched.

### 7.3 Verify

Re-query counts (expect 4 users / 2 branches / 2 recipients / 4 customers /
5 suppliers / 0 movements-products-stock-dodáky), then a live smoke test: log in
as a kept user; open dashboard, míchání, inventura, příjem — no 500s.

### 7.4 Rollback (only if you changed your mind after a clean run)

Restore into the **existing** DB (never drop/recreate — that loses the 0038 ICU
`cs-CZ` locale):

```
gunzip -c backups/prod-pre-golive-wipe-<DATE>.sql.gz | \
  ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose exec -T db psql -U kasia -d kasia"
```

## 8. Things that are not in this RUNBOOK on purpose

- **Observability / log shipping / metrics / alerting.** ~6 users;
  per [`../.claude/rules/right-sized-for-small-business.md`](../.claude/rules/right-sized-for-small-business.md),
  add when there's operating pain to justify it. Caddy + gunicorn
  logs to stdout; `journalctl -u docker` covers the rest. (Public-site
  *visitor* analytics is the deliberate 0076 exception — § 6.)
- **A staging environment.** Prod-only by
  [`../context/decisions/0026-ci-cd-github-actions.md`](../context/decisions/0026-ci-cd-github-actions.md).
- **Auto-rollback.** Manual per § 3.
