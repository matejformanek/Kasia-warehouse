# Hetzner provisioning — session handoff

> Single-shot handoff doc so this conversation can compact / restart
> without losing the in-progress Hetzner provisioning state. Next
> agent: read this first (after `state.md`), then resume at § Next.

**Date:** 2026-06-16
**Current state of code:** `main @ 871d062` pushed to
`origin/main` (Pass 6 + polish). 273 pytest tests green, ruff clean,
system check clean, makemigrations --check clean.
**Current state of infra:** nothing on Hetzner yet. Local docker
stack is live at http://localhost/ for walkthrough.

---

## 0. Pre-flight (Matej, in progress)

Decisions + rules that gate this work:
- [`context/decisions/0025-iac-terraform-hcloud.md`](decisions/0025-iac-terraform-hcloud.md)
  — `terraform apply` is run manually from Matej's workstation with
  `HCLOUD_TOKEN` in env. **One-off override granted to the agent for
  this session** — agent runs `init / plan / apply` on Matej's say-so
  and shows plan output for approval before applying.
- [`context/decisions/0027-hosting-hetzner.md`](decisions/0027-hosting-hetzner.md)
  — Hetzner CPX22 in Falkenstein + Storage Box BX11. EUR billing is
  fine for a CZ B2B (reverse-charge VAT once IČO+DIČ given).
- [`.claude/rules/infra-as-code.md`](../.claude/rules/infra-as-code.md)
  — no console clicks for app/infra state; everything through
  `infra/terraform/` + `compose.yaml` + `deploy.yml`.

### Status checklist (tick what's done)

- [x] Hetzner account created
- [x] `kasia-prod` project created in Hetzner Cloud Console
- [x] Old leaked API token (`oRYZ5asCq5RD…`) **REVOKED**
- [x] New API token generated (Read & Write) — name
  `terraform-matej-workstation`
- [ ] New token added to `~/.zprofile` via:
  ```bash
  echo 'export HCLOUD_TOKEN="…"' >> ~/.zprofile
  source ~/.zprofile
  ```
  Verify: `grep -c '^export HCLOUD_TOKEN=' ~/.zprofile` returns `1`.
  ⚠️ **NEVER** put the token in the project `/Users/matej/Work/Kasia-warehouse/.env`
  — that file ships into the running Django container.
- [ ] SSH keypair generated:
  `ssh-keygen -t ed25519 -f ~/.ssh/kasia_prod -C kasia-prod`
- [ ] Terraform OR OpenTofu installed locally
  — `brew install opentofu` (recommended, BSL-free fork) **or**
  `brew tap hashicorp/tap && brew install hashicorp/tap/terraform`
- [ ] `hcloud` CLI installed locally — `brew install hcloud`

### One pre-flight fix already landed on `main`

`infra/terraform/cloud-init.yaml` had `REPLACE_ME` in the repo clone
URL. Fixed on 2026-06-16 to `matejformanek/Kasia-warehouse.git`
(part of commit `<TBD>` after this handoff merges).

---

## 1. What the agent runs when Matej says "go"

Once the four boxes above are ticked, Matej says `go` and the agent
runs (from `/Users/matej/Work/Kasia-warehouse/infra/terraform`):

```bash
# Confirm token is reachable from the agent's Bash environment
# (sourced from ~/.zprofile per the harness's shell init).
source ~/.zprofile
[ -n "$HCLOUD_TOKEN" ] && echo "token ok" || echo "missing"

# These three env vars are what main.tf reads.
export TF_VAR_hcloud_token="$HCLOUD_TOKEN"
export TF_VAR_ssh_pub_key="$(cat ~/.ssh/kasia_prod.pub)"
export TF_VAR_admin_ip="$(curl -s https://ifconfig.me)/32"

cd /Users/matej/Work/Kasia-warehouse/infra/terraform

terraform init      # or tofu init
terraform plan      # PASTE OUTPUT BACK TO MATEJ FOR REVIEW
                    # Expected: 4 resources to be created
                    #   - hcloud_ssh_key.admin
                    #   - hcloud_firewall.kasia
                    #   - hcloud_server.web
                    #   - hcloud_firewall_attachment.web
                    # No "destroy" / "update" actions.

# WAIT for explicit "apply" from Matej before this:
terraform apply -auto-approve

terraform output server_ipv4   # capture the box IP
```

Then wait for cloud-init to finish on the box:

```bash
SERVER_IPV4="$(cd /Users/matej/Work/Kasia-warehouse/infra/terraform && terraform output -raw server_ipv4)"
ssh -o StrictHostKeyChecking=accept-new \
    -i ~/.ssh/kasia_prod \
    root@"$SERVER_IPV4" \
    'cloud-init status --wait'   # ~2–3 min on first boot
```

Expected output: `status: done`. If it says `error`, run
`journalctl -u cloud-final` on the box and diagnose.

After this, control passes back to Matej for steps 2–5.

---

## 2. Matej-only steps after first-boot is `done`

### 2.1 Populate `/srv/kasia/.env` on the box

```bash
ssh -i ~/.ssh/kasia_prod root@<server_ipv4>
cd /srv/kasia
cp .env.example .env
nano .env
chmod 600 .env
chown app:app .env
```

Required values (Matej fills these, agent never sees them):

| Variable | What to put |
|----------|-------------|
| `DJANGO_SECRET_KEY` | `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'` on Mac |
| `DJANGO_ALLOWED_HOSTS` | `<server_ipv4>` for now |
| `DJANGO_DEBUG` | `0` |
| `POSTGRES_PASSWORD` | Another long random string |
| `EMAIL_HOST` | Decided SMTP provider (Seznam.cz Mail Pro recommended) |
| `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `1` |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP credentials |
| `DEFAULT_FROM_EMAIL` | `Kasia vera <no-reply@kasia.cz>` |
| `RESTIC_REPOSITORY` / `RESTIC_PASSWORD` | leave blank until step 2.4 |

### 2.2 Set 3 GitHub Actions secrets

https://github.com/matejformanek/Kasia-warehouse/settings/secrets/actions

| Secret | Value |
|--------|-------|
| `SSH_HOST` | `<server_ipv4>` |
| `SSH_USER` | `app` |
| `SSH_KEY` | Contents of `~/.ssh/kasia_prod` (private key, full PEM block) |

### 2.3 Trigger first deploy

Either: `git commit --allow-empty -m "infra: first Hetzner deploy" && git push`
or click "Run workflow" on the `deploy` workflow at
https://github.com/matejformanek/Kasia-warehouse/actions.

Watch build (~3 min) → deploy (~1 min). Verify
`curl http://<server_ipv4>/healthz` → `ok`.

### 2.4 Create the superuser

```bash
ssh -i ~/.ssh/kasia_prod app@<server_ipv4>
cd /srv/kasia
docker compose run --rm \
  -e DJANGO_SUPERUSER_EMAIL=admin@kasia.cz \
  -e DJANGO_SUPERUSER_PASSWORD='<strong-password>' \
  web python manage.py createsuperuser --noinput
```

Then in the browser at `http://<server_ipv4>/uzivatele/`:
- Create Karolína as vlastník
- Create one obsluha account per branch (TYN + SEZ)

### 2.5 Storage Box + backups

1. Hetzner console → project switcher → **Storage Boxes** → order BX11
   (1 TB, ~€4/mo, same region — Falkenstein).
2. Enable SSH support; copy `kasia_prod.pub` into authorized_keys via
   the box's web UI.
3. On the prod box, init restic and fill `.env`:

   ```bash
   ssh -i ~/.ssh/kasia_prod app@<server_ipv4>
   cd /srv/kasia
   RESTIC_PASS='<long-random>'
   docker compose run --rm \
     -e RESTIC_REPOSITORY="sftp:u123456@u123456.your-storagebox.de:/kasia" \
     -e RESTIC_PASSWORD="$RESTIC_PASS" \
     --entrypoint restic backup init
   sudo nano .env   # add RESTIC_REPOSITORY + RESTIC_PASSWORD
   docker compose --profile prod up -d backup
   ```

4. **Save the restic password independently of the box** — losing it
   means losing every backup.
5. Schedule a restore drill ~30 days after go-live per
   `.claude/rules/right-sized-for-small-business.md`.

---

## 3. Deferred (after the box is live, separate session)

- **Domain + HTTPS cutover**: `infra/RUNBOOK.md` § 5. Caddyfile +
  compose port unpub + `DJANGO_ALLOWED_HOSTS`. Decision: domain name
  open (`context/open-questions.md` § Decide later). No code change.
- **Cron entry for daily low-stock e-mail**: per decision 0045 the
  command is `python manage.py mail_low_stock_summary`. Add a
  crontab entry on the box once a few days of real data exist:

  ```bash
  sudo crontab -e
  0 7 * * *  cd /srv/kasia && /usr/bin/docker compose run --rm web python manage.py mail_low_stock_summary >> /var/log/kasia-low-stock.log 2>&1
  ```

- **14-day shadow run** per decision 0034 — Petr + Karolína use the
  live system alongside the old method before branch staff cut over.

---

## 4. Quick reference

| Thing | Value |
|-------|-------|
| Hetzner project | `kasia-prod` |
| Server name | `kasia-prod` |
| Server type | CPX22 (3 vCPU AMD EPYC, 8 GB RAM, 80 GB NVMe) |
| Location | `fsn1` (Falkenstein, DE) |
| OS image | `ubuntu-24.04` |
| SSH key file (local) | `~/.ssh/kasia_prod` + `~/.ssh/kasia_prod.pub` |
| SSH key name on Hetzner | `kasia-prod-admin` |
| Firewall name | `kasia-prod-fw` |
| Firewall rules | 22 from `<admin_ip>/32`; 80, 443, ICMP from world |
| User on box | `root` (initial) → `app` (after deploy SSH) |
| Repo path on box | `/srv/kasia` |
| Image tag pattern | `ghcr.io/matejformanek/kasia-warehouse:sha-<12char>` + `:latest` |
| Healthcheck URL | `http://<server_ipv4>/healthz` → `ok` |
| GHCR auth | built-in `GITHUB_TOKEN` (no PAT) |
| Monthly cost | ~€11.50 (CPX22 ~€7.55 + Storage Box ~€4 + traffic free ≤20 TB) |

---

## 5. Files the agent may need to read next session

- `infra/RUNBOOK.md` — operational playbook (this doc is the *delta*
  for the in-progress provisioning; RUNBOOK is the steady-state ref)
- `infra/terraform/main.tf`, `variables.tf`, `cloud-init.yaml`
- `context/decisions/0025-iac-terraform-hcloud.md` (rationale)
- `context/decisions/0027-hosting-hetzner.md` (rationale)
- `.github/workflows/deploy.yml` (the build + deploy pipeline)
- `.env.example` (template for what `/srv/kasia/.env` on the box needs)
- `compose.yaml` (the prod profile; backup service is gated to it)

---

## 6. How to resume

Next agent: read `context/state.md` § Done (most recent first) → read
this doc → check § Pre-flight checklist → ask Matej which boxes are
ticked. The action you're empowered to take is § 1 (terraform
`init / plan / apply`) on Matej's explicit `go` — and only that.
Anything in § 2 requires Matej to be at the keyboard with the
credentials.
