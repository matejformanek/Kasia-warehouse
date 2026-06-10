# 0027 — Hosting + backups: Hetzner Cloud CPX22 + Storage Box BX11

## Context

The deploy target — one VPS in the EU, cheap, well-supported, with
a workable off-box backup target. The data residency story is
straightforward: Kasia is a Czech company; a German Hetzner region
(Falkenstein or Nuremberg) is the obvious low-latency, in-EU,
GDPR-comfortable pick.

**Note on timing:** the box is **not provisioned in this pass.**
Until Matej decides to migrate from local Compose to a live VPS,
production hosting is not active. This decision *names* the
target so [`0025`](./0025-iac-terraform-hcloud.md) and
[`0026`](./0026-ci-cd-github-actions.md) can be concrete; the
provisioning step happens when Matej runs `terraform apply` per
[`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md).

Workload sizing: ~6 active users, ~hundreds of products, tens of
movements per day, peak concurrency under 10. A modest VPS (3 vCPU,
8 GB RAM) has comfortable headroom and lots of room for the
WeasyPrint + gunicorn working set.

Backups must be **off-box** — a server-only backup is useless if
the server itself is gone. Hetzner sells Storage Box (SFTP/Borg
target) cheaply; restic encrypts client-side before upload, so
even if Hetzner is compromised the dumps stay private.

## Options considered

- **Hetzner Cloud CPX22 (Falkenstein) + Storage Box BX11.**
  €7.99/mo + €3.49/mo ≈ €11.50/mo. AMD EPYC 3 vCPU, 8 GB RAM,
  80 GB NVMe. Storage Box gives 1 TB SFTP + Borg-compatible
  endpoint. Hetzner Terraform provider is gold-standard.
- **OVHcloud VPS-1 Strasbourg.** Similar price tier, EU
  region. Second choice if Hetzner is unavailable for some reason.
  Terraform support is via `ovh/ovh` provider — workable, less
  polished than hcloud.
- **Scaleway DEV1-M / S Frankfurt.** Comparable price; smaller
  ecosystem footprint.
- **Contabo VPS.** Cheaper, but reputation for overcommit and
  variable I/O performance argues against it for a DB-on-same-box
  setup.
- **AWS Lightsail / DigitalOcean Droplet.** Higher cost for
  equivalent specs; no win for a small Czech business.

## Choice

**Production:** Hetzner Cloud **CPX22** in **Falkenstein** (`fsn1`).
3 vCPU AMD EPYC, 8 GB RAM, 80 GB NVMe, €7.99/mo at 2026-06-08
pricing.

**Backups:** Hetzner **Storage Box BX11** (~€3.49/mo, 1 TB) at the
same datacentre. Restic-encrypted daily backups, written by the
`backup` container in
[`compose.yaml`](../../compose.yaml):

- Daily Postgres logical dump (`pg_dump`).
- Daily snapshot of the `pgdata` named volume.
- Retention policy (how many daily / weekly / monthly snapshots) is
  **TBD** — tracked as an open item in
  [`../open-questions.md`](../open-questions.md) § Decide later
  and to be written into
  [`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md) once operating
  history accumulates.

**Total monthly cost:** ~€11.50.

**Second choice if Hetzner is unavailable:** OVHcloud VPS-1 in
Strasbourg. Equivalent specs, EU residency, `ovh/ovh` Terraform
provider.

## Rationale

- Hetzner Cloud is the price/performance leader in the EU for this
  size class; AMD EPYC at €7.99/mo for the CPX22 spec is
  unrivalled at 2026 prices.
- Falkenstein is ~600 km from Kasia in Říčany u Prahy — sub-30 ms
  round-trip; effectively LAN-class for ~6 users on a typical
  Czech home/office uplink.
- Storage Box at the same DC keeps backup transfer free
  (Hetzner-internal traffic) and cheap.
- Restic gives client-side encryption: the Storage Box is treated
  as untrusted bytes-at-rest, which is the right posture even with
  a reputable provider.
- The Hetzner Terraform provider is the most polished of the
  candidates; [`0025`](./0025-iac-terraform-hcloud.md) leverages it.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- [`0025`](./0025-iac-terraform-hcloud.md) — Terraform can be
  concrete about provider + region + server type.
- [`0023`](./0023-runtime-orchestration-compose.md) — the `backup`
  service can name a concrete restic target.
- Operational handover — the bill of materials is ~€11.50/mo;
  documented for Petr.

**Forecloses (without follow-on decision):**

- Other VPS providers as the primary target.
- Server-only (no off-box) backups.
- US-region hosting.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Single-VPS-deploy preference.

**Outstanding sub-questions** (added in this pass to
[`../open-questions.md`](../open-questions.md) § Decide later):

- Backup retention SOP (number of daily / weekly / monthly
  snapshots, restore-drill cadence).
- Domain name (TLS cutover trigger per
  [`0024`](./0024-tls-caddy.md)).
