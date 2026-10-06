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

That brings up `web` + `db` + `proxy`. The `db-dump` backup sidecar
and Umami are profiled to `prod` only and stay out of the local loop. Visit
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

⚠️ **On the live box, every `apply` is gated on the plan** (per
[`0105`](../context/decisions/0105-infra-security-hardening.md)). State is
**local-only** (`infra/terraform/terraform.tfstate`, gitignored — keep a copy
in `backups/`); `terraform state list` must show the 4 existing resources
first. Use `terraform plan -out=tfplan.bin` and read it: it must say
`0 to destroy` and never `must be replaced`. `hcloud_server.web` carries
`lifecycle { ignore_changes = [user_data, ssh_keys, image] }` and
`delete_protection` / `rebuild_protection` — a deliberate rebuild means
removing those in a reviewed PR first. Never change `TF_VAR_ssh_pub_key`
away from `kasia_prod.pub`. The CI terraform job plans against a dummy token
and no state, so it cannot catch a replace.

### 1.3 Populate the on-box `.env`

```
ssh -i ~/.ssh/kasia_prod root@<server_ipv4>
# (or `app@<server_ipv4>` once SSH key sync completes)
cd /srv/kasia
cp .env.example .env
$EDITOR .env                                  # fill in real secrets
chmod 600 .env
```

`.env` is **never** committed. Backups need no secrets (§ 1.6).

### 1.4 Set GitHub Actions secrets

In the GitHub repo settings → Secrets and variables → Actions:

| Secret      | Value                                                  |
|-------------|--------------------------------------------------------|
| `SSH_KEY`   | contents of `~/.ssh/kasia_deploy` — the dedicated deploy private key, authorised on `app` only (§ 10). Until § 10 is done it is still `~/.ssh/kasia_prod`. |

`SSH_KEY` is a **repository** secret (checked 2026-10-06; the `production`
environment has no secrets of its own). Host and user are hardcoded literals
in `.github/workflows/deploy.yml` (`host: 91.98.47.1`, `username: app`) —
non-secret, as is the host-key `fingerprint:` (ECDSA — update it after a
rebuild: `ssh-keyscan -t ecdsa <ip> | ssh-keygen -lf -`). If the box is
re-IP'd, edit the workflow rather than rotating a secret. GHCR push
is authenticated by the built-in `GITHUB_TOKEN`; no PAT. A rebuilt box seeds
`app`'s `authorized_keys` from root's (`kasia_prod` only) — re-append the
deploy public key (§ 10 step 4) before the first deploy.

### 1.5 Trigger the first deploy

Push any commit to `main`, or run the `deploy` workflow manually
from the Actions tab. Watch:

- Build job pushes `ghcr.io/<org>/<repo>:sha-<commit>` + `:latest`.
- Deploy job SSHes in, pulls, runs migrations, swaps the container.

Verify: `curl http://<server_ipv4>/healthz` returns `200`.

### 1.6 Backups (per [`0105`](../context/decisions/0105-infra-security-hardening.md))

Nothing to set up by hand beyond the Terraform apply:

- **Hetzner server backups** — `backups = true` in `main.tf`; 7 rolling
  daily images of the whole disk. ⚠️ **They are deleted together with the
  server** — accepted gap; the off-box path is the manual laptop dump (§ 4.1).
- **`db-dump` sidecar** (`compose.yaml`, prod profile) — `pg_dump -Fc` of the
  warehouse DB every 12 h into `/home/app/kasia-dumps` (mode 700, created by
  `deploy.yml`), newest 14 kept. Each Hetzner image therefore holds
  consistent logical dumps. Check it:

```
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  'ls -lt ~/kasia-dumps | head -3; cd /srv/kasia && docker compose --profile prod ps db-dump'
```

Expect a `kasia-<UTC timestamp>.dump` younger than 12 h and `(healthy)`
(unhealthy = no dump younger than 26 h → `docker compose logs db-dump`).

Restore: § 4.

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
Cadence: quarterly, and after any Postgres major bump. Retention today:
14 on-box dumps (≈ 7 days at 12 h) inside each of 7 daily Hetzner images.

All dumps are `pg_dump -Fc` (custom format) and hold **SMTP creds, password
hashes and customer PII** — `chmod 600`, keep under `backups/` (gitignored +
dockerignored), never paste into PRs/commits.

### 4.1 Take an off-box (laptop) dump

The only copy that survives losing the server (§ 1.6). Take one before any
risky infra change, and periodically:

```
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose exec -T db pg_dump -U kasia -d kasia -Fc" \
  > backups/prod-$(date +%F).dump
chmod 600 backups/prod-$(date +%F).dump
pg_restore -l backups/prod-$(date +%F).dump | grep -c 'TABLE DATA'   # sanity (31 on 2026-10-06)
```

Or copy the newest sidecar dump:
`scp -i ~/.ssh/kasia_prod "app@91.98.47.1:kasia-dumps/$(ssh -i ~/.ssh/kasia_prod app@91.98.47.1 'ls -1t ~/kasia-dumps | head -1')" backups/`.

### 4.2 Restore drill (local, scratch DB — never touches prod or your dev data)

Uses a **separate compose project** (`-p kasia-drill`) so its volume is
fresh and the everyday `kasia` dev DB is untouched. The `.env` forces the
console e-mail backend so nothing restored can mail real people.

```
cd <a checkout of main>
cat > .env <<'ENV'
POSTGRES_PASSWORD=drill-only
DJANGO_SECRET_KEY=drill-only
DJANGO_DEBUG=1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
CADDYFILE=./Caddyfile.dev
ENV
docker compose -p kasia-drill up -d --wait db           # fresh initdb, ICU cs-CZ (0038)
docker compose -p kasia-drill exec -T db \
  pg_restore -U kasia -d kasia --no-owner --clean --if-exists --exit-on-error \
  < backups/<dump>.dump
```

Compare per-table row counts with prod (read-only on prod) — `counts.sql`:

```
select table_name,
  (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I',
     table_schema, table_name), false, true, '')))[1]::text::int
from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE' order by 1;
```

```
docker compose -p kasia-drill exec -T db psql -U kasia -d kasia -tA < counts.sql > drill.txt
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  'cd /srv/kasia && docker compose exec -T db psql -U kasia -d kasia -tA' < counts.sql > prod.txt
diff prod.txt drill.txt && echo IDENTICAL
DATABASE_URL=postgres://kasia:drill-only@127.0.0.1:5432/kasia DJANGO_SECRET_KEY=x \
  DJANGO_DEBUG=1 EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend \
  uv run python manage.py migrate --check                 # schema == code
docker compose -p kasia-drill down -v && rm .env          # throw it away
```

(The drill publishes `127.0.0.1:5432`, so stop the dev stack first.) Counts
only match exactly when prod hasn't changed since the dump; otherwise expect
small deltas in `inventory_screenvisit` / `django_session`.

**Drill log**

| Date | Dump | Result |
|---|---|---|
| 2026-10-06 | `backups/prod-2026-10-06-pre-hardening.dump` (laptop `pg_dump -Fc`) | Restored clean (`--exit-on-error`, rc 0); DB locale `icu / cs-CZ`; all **31** public tables **identical** to prod (e.g. users 8, products 157, movements 255, movement lines 579, dodáky 49, stock 120, míchání 44); `migrate --check` clean. The `db-dump` sidecar was also run against the restored DB as uid 1000:1001: wrote a valid archive (31 TABLE DATA entries), healthcheck passed, retention kept the newest 14. |

### 4.3 Restore into production (disaster)

1. **Take a laptop dump of whatever is there now** (§ 4.1), even if broken.
2. Get the dump onto the box: newest `~/kasia-dumps/*.dump`, or `scp` a
   laptop dump to `app@91.98.47.1:`. If the disk itself is gone, first
   restore the server from a Hetzner backup image (console → server →
   Backups → Restore — `rebuild_protection` must be lifted via Terraform
   for a rebuild-from-image) and take its newest `~/kasia-dumps` file.
3. Stop writers, restore **into the existing DB** (never drop/recreate it —
   that loses the 0038 ICU `cs-CZ` locale), start again:

```
ssh -i ~/.ssh/kasia_prod app@91.98.47.1
cd /srv/kasia
docker compose --profile prod stop web db-dump
docker compose exec -T db pg_restore -U kasia -d kasia --no-owner \
  --clean --if-exists --exit-on-error < ~/kasia-dumps/<dump>.dump
docker compose --profile prod up -d --no-deps web db-dump   # WEB_IMAGE trap: § 5b
```

4. Verify: `/healthz` 200, log in, open Přehled + Historie; compare counts
   with the drill query above.

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
run `docker compose --profile prod up -d --no-deps --force-recreate proxy`
on the box (a few seconds of downtime; certs persist in the `caddy_data`
volume). **`--no-deps` is mandatory**: without it compose re-evaluates `web`
against the `.env` `WEB_IMAGE` pin and can roll prod back (trap below).
Verify with `curl -sI https://kasia.cz/` (e.g. the 0105 HSTS header present,
no `Server:`). Deploys that change the `proxy` service itself (ports, image)
recreate it automatically — that's why the Phase B cutover and the 0105
image pin worked without this step.

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
  `/home/app/umami-admin-pw.txt`, mode 600 — **still present on
  2026-10-06**; fetch it into a password manager and `rm` it, § 10 step 12).
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
- **Backups:** `umami_pgdata` is covered only by the Hetzner server backup
  image (crash-consistent; Postgres recovers via WAL). The `db-dump`
  sidecar dumps the warehouse DB only — analytics loss is tolerable (0105).
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

## 9. Login lockout (django-axes) — break-glass unlock

Per [`../context/decisions/0104-app-security-hardening.md`](../context/decisions/0104-app-security-hardening.md):
5 failed logins (on `/sklad/prihlaseni/` or `/admin/`) lock that
**(e-mail, client IP)** pair for **1 hour**; it unlocks by itself after the
cool-off, and a successful login resets the counter. The user sees the Czech
„Příliš mnoho pokusů" page (HTTP 429). To unlock someone immediately:

```
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose exec -T web python manage.py axes_reset_username <email>"
# or clear every lockout:
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose exec -T web python manage.py axes_reset"
```

`axes_list_attempts` shows the current failure records. The password-reset form
(`/sklad/reset-hesla/`) has its own per-IP limit (5 POSTs / hour, in-process
cache) — it clears on `docker compose restart web` or after the hour.

**Roles fail closed (0104):** a login refused with „Váš účet nemá přiřazenou
roli…" means the account is in neither the `vlastnik` nor the `obsluha` group
(or is obsluha without a pobočka). Fix it in `/sklad/uzivatele/` (pick the role)
or in `/admin/` (groups). Health check:
`docker compose exec -T web python manage.py shell -c "from accounts.models import User; print(User.objects.filter(is_superuser=False, groups__isnull=True).count())"`
→ must print `0`.

## 10. Live-box hardening (one-off, per 0105)

> **Documented one-off exception to
> [`.claude/rules/infra-as-code.md`](../.claude/rules/infra-as-code.md).**
> `cloud-init.yaml` carries the same hardening for any *future* box, but it
> only runs at first boot and Terraform now ignores it (lifecycle block), so
> the running box is changed by hand, exactly once, with these commands.
> Matej runs them; nothing here is automated. Afterwards record the date in
> `context/state.md`. Per
> [`0105`](../context/decisions/0105-infra-security-hardening.md).

Facts measured 2026-10-06: `app` = uid 1000 / gid 1001, in `docker`, no
sudo; `/etc/ssh/sshd_config.d/` empty (Ubuntu default → password auth on,
root login allowed); `unattended-upgrades` installed; `fail2ban` absent;
`SSH_KEY` is a **repository** secret (no environment secret) and the
`production` environment has **no** branch restriction or reviewers;
`/home/app/umami-admin-pw.txt` still exists.

Do the steps **in order**. Never close your first root session until the
step-9 checks pass.

**A — before anything**

1. Laptop dump (§ 4.1) and copy `infra/terraform/terraform.tfstate` into
   `backups/` (`chmod 600`).
2. Confirm break-glass works: Hetzner Console → server → **Console** (VNC)
   opens, and you know where **Rescue → Reset root password** is. This is the
   way back in if sshd ends up locked.

**B — merge + Terraform**

3. Merge the 0105 PR. The deploy already uses the pinned host-key
   `fingerprint:` (a mismatch fails before any remote command — safe) and
   recreates `db`, `umami-db`, `proxy`, starts `db-dump`, removes the old
   `backup` container. Then, from an up-to-date `main`:

```
cd infra/terraform
terraform state list            # expect the 4 resources
# TF_VAR_* exactly as in § 1.2 (ssh_pub_key = kasia_prod.pub)
terraform plan -no-color -out=tfplan.bin
# MUST read: "0 to add, 1 to change, 0 to destroy" —
#   backups / delete_protection / rebuild_protection false -> true.
# Anything "must be replaced" → STOP.
terraform apply tfplan.bin && rm tfplan.bin
```

**C — dedicated deploy key (rotates only the GitHub key)**

4. Generate and authorise it on `app` only:

```
ssh-keygen -t ed25519 -f ~/.ssh/kasia_deploy -N '' -C gha-deploy-kasia
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 'cat >> ~/.ssh/authorized_keys' < ~/.ssh/kasia_deploy.pub
ssh -i ~/.ssh/kasia_deploy -o IdentitiesOnly=yes app@91.98.47.1 'cd /srv/kasia && docker compose ps'
```

5. Swap the secret (repo-level — there is no environment secret to shadow
   it) and prove a deploy:

```
gh secret set SSH_KEY -R matejformanek/Kasia-warehouse < ~/.ssh/kasia_deploy
gh workflow run deploy.yml --ref main
gh run watch "$(gh run list --workflow=deploy --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```

6. **Keep `kasia_prod` on `app` and root.** It is Matej's admin key — the
   RUNBOOK and the ops skills use `app@` with it. *Optional, only if Matej
   explicitly agrees:* remove the `kasia-prod` line from
   `/home/app/.ssh/authorized_keys` — after that `app@` works only with the
   deploy key, every `ssh -i ~/.ssh/kasia_prod app@…` command in this file
   must become `root@` + `su - app`, and the deploy key becomes the only
   direct `app` credential.

**D — sshd hardening (session 1 stays open throughout)**

7. Session 1:

```
ssh -i ~/.ssh/kasia_prod root@91.98.47.1
cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
chmod 644 /etc/ssh/sshd_config.d/10-hardening.conf
sshd -t && sshd -T | grep -Ei '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication) '
# expect: permitrootlogin without-password (= prohibit-password),
#         passwordauthentication no, kbdinteractiveauthentication no
systemctl reload ssh
```

8. **New terminal** (session 1 still open) — all four must behave:

```
ssh -i ~/.ssh/kasia_prod   -o IdentitiesOnly=yes root@91.98.47.1 true && echo root-key-ok
ssh -i ~/.ssh/kasia_prod   -o IdentitiesOnly=yes app@91.98.47.1  true && echo app-admin-ok
ssh -i ~/.ssh/kasia_deploy -o IdentitiesOnly=yes app@91.98.47.1  true && echo deploy-key-ok
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive \
    root@91.98.47.1           # expect: Permission denied (publickey).
```

9. Any failure → in session 1: `rm /etc/ssh/sshd_config.d/10-hardening.conf
   && systemctl reload ssh`, re-test, investigate. Only when all four pass,
   close session 1.

**E — fail2ban + unattended-upgrades (root)**

10. ```
    apt-get update && apt-get install -y fail2ban
    printf '[sshd]\nenabled = true\nbackend = systemd\n' > /etc/fail2ban/jail.d/10-kasia.conf
    systemctl enable --now fail2ban && fail2ban-client status sshd
    ```
    Ubuntu defaults: 5 failures → 10 min ban. Locked yourself out? Hetzner
    Console → `fail2ban-client set sshd unbanip <your-ip>`.
11. unattended-upgrades is already installed — just confirm it is on:
    `systemctl is-enabled unattended-upgrades && cat /etc/apt/apt.conf.d/20auto-upgrades`
    (both `APT::Periodic` lines `"1"`).

**F — cleanup + verification**

12. Umami password file: as `app`, `cat ~/umami-admin-pw.txt` into a
    password manager, confirm it logs in at `https://analytics.kasia.cz/`
    (and that `admin` / `umami` does **not**), then `rm ~/umami-admin-pw.txt`.
13. Old backup image: `docker image rm offen/docker-volume-backup:latest`
    (as `app`; harmless if already gone).
14. Verify from the laptop:

```
curl -sI https://kasia.cz/ | grep -iE '^(strict-transport-security|server|via):'
#   → only "strict-transport-security: max-age=31536000"
nc -zv -w3 91.98.47.1 5432 ; nc -zv -w3 91.98.47.1 8000   # both must fail
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 'ls -lt ~/kasia-dumps | head -3'
```

Also check Hetzner Console → server shows **Backups: enabled** and the
delete/rebuild **protection** lock icons.
15. Add a dated line to `context/state.md` → Done.

**Not changed by this section (decide separately):** move `SSH_KEY` to a
`production`-environment secret and restrict that environment to `main`
(today any branch's workflow can read the repo secret; fork PRs cannot).
