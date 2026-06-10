# 0025 — Provisioning IaC: Terraform + hcloud + cloud-init

## Context

The production target is a single Hetzner Cloud VPS
([`0027`](./0027-hosting-hetzner.md)). The box needs:

- A server resource with the right size + image (Ubuntu LTS).
- A firewall: 22/tcp from the admin IP only, 80/tcp + 443/tcp from
  anywhere.
- An SSH key registered with Hetzner so first login works.
- (Optional but documented) a volume for `pgdata` so a rebuild of
  the server doesn't destroy DB state.
- Docker Engine installed and `/srv/kasia` cloned on first boot.

That's a ~80-line Terraform config + a ~20-line cloud-init file.
Ansible would be overkill for a single box that effectively never
configuration-drifts.

**Apply is not in CI.** Terraform plan runs on PRs touching
`infra/`; apply runs manually from Matej's workstation with the
`HCLOUD_TOKEN` in env. This avoids any accidental `apply` from a
broken automation path destroying the box.

## Options considered

- **Terraform + `hetznercloud/hcloud` provider + cloud-init.**
  Provider is gold-standard for Hetzner (maintained by Hetzner's
  cloud team). State file kept local to Matej's workstation
  (`terraform.tfstate` gitignored; backed up to the same Storage
  Box as the app DB).
- **OpenTofu** instead of Terraform. Drop-in fork; would work
  identically. Terraform is the better-known name and the choice
  follows the boring-beats-clever rule
  ([`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)).
- **Ansible.** Procedural; works fine but is overkill for one box
  whose config rarely changes. The bootstrap fits in cloud-init.
- **Pulumi.** Same shape as Terraform with Python/TS. No win for a
  one-box config; adds an SDK dependency.
- **Manual provisioning via the Hetzner console.** Fast on day one,
  expensive on day-180 when nobody remembers the firewall rules.
  Per [`../../.claude/rules/right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md):
  drift = pain. IaC pays for itself the first time the box is
  rebuilt.

## Choice

**Terraform with the `hetznercloud/hcloud` provider, pinned to the
latest 1.x.** cloud-init handles first-boot configuration. Files:

```
infra/terraform/versions.tf         # required_providers + versions
infra/terraform/variables.tf        # hcloud_token, ssh_pub_key, location, server_type
infra/terraform/main.tf             # hcloud_server, hcloud_firewall, hcloud_ssh_key, hcloud_volume
infra/terraform/outputs.tf          # public IPv4 + IPv6
infra/terraform/cloud-init.yaml     # Docker engine, swap, app user, /srv/kasia clone
```

**Apply is manual** from Matej's workstation. CI is plan-only
(`terraform.yml` GH Action runs `fmt -check`, `validate`, `plan`
on PRs touching `infra/` — see
[`0026`](./0026-ci-cd-github-actions.md)).

Defaults:

- `server_type = "cpx22"` (per
  [`0027`](./0027-hosting-hetzner.md)).
- `server_location = "fsn1"` (Falkenstein, DE — closest EU region
  for Kasia in Říčany).
- Image: latest Ubuntu LTS at apply time (24.04 as of 2026-06-08).
- Firewall: SSH from admin IP variable, 80/tcp + 443/tcp from
  `0.0.0.0/0` and `::/0`.

## Rationale

- The hcloud provider is mature and explicitly supported by
  Hetzner — drift between the Terraform model and the cloud
  console is rare.
- cloud-init for first-boot config keeps Ansible out of the loop;
  there's no second-day config management to do.
- Plan-in-CI / apply-from-workstation is a deliberate choice for a
  one-person ops surface: avoids the failure mode where a broken
  workflow accidentally destroys the box.
- The state file is committed nowhere; gitignored and backed up via
  the same restic flow as the DB.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The Hetzner box can be provisioned by running `terraform apply`
  from Matej's workstation when migration time comes — see
  [`../../infra/RUNBOOK.md`](../../infra/RUNBOOK.md).
- Adding a second box (e.g. a separate DB host) becomes a Terraform
  diff, not a console click-through.

**Forecloses (without follow-on decision):**

- Manual provisioning via the Hetzner console.
- Ansible / SaltStack / Chef for ongoing config management.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Single-VPS deploy preference, in a reproducible form.

**Makes implementable (0001–0013):**

- N/A directly. Infrastructure plumbing.
