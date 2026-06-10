# 0024 — Reverse proxy + TLS: Caddy 2 (HTTP-only initially)

## Context

The `web` container in
[`0023`](./0023-runtime-orchestration-compose.md) is not exposed
directly — a reverse proxy fronts it for TLS termination, sensible
defaults (HSTS, security headers), and decoupling of the public
listener from the gunicorn process.

A domain is **not registered yet** as of 2026-06-08. The first
deploy will be **IP-only over plain HTTP**, with TLS added the day
a domain lands and an A-record points at the box. Matej confirmed
this scope (2026-06-08).

The TLS shape is the one piece of the deployment most likely to
change in MVP shakedown (domain registration delays, hostname
swaps), so it gets its own decision file separate from
[`0023`](./0023-runtime-orchestration-compose.md).

## Options considered

- **Caddy 2 (`caddy:2-alpine`).** Auto-TLS via Let's Encrypt
  zero-config when a hostname is configured. Single Caddyfile
  syntax. ~25 MB image. Single binary, no plugins for the basic
  reverse-proxy case.
- **nginx + certbot.** Mature; more knobs; requires a renew cron +
  ACME client + handler reloads. More moving parts for a solo
  operator.
- **Traefik.** Auto-TLS too, but config is heavier (labels on
  services + a static config file); aimed at multi-service
  dynamic environments.
- **HAProxy.** Out of shape for an HTTPS-with-auto-TLS workflow.

## Choice

**Caddy 2 (`caddy:2-alpine`)** as the `proxy` service in
[`compose.yaml`](../../compose.yaml). One
[`Caddyfile`](../../Caddyfile) at the repo root.

**MVP cut (this pass):**

```caddyfile
:80 {
    reverse_proxy web:8000
    encode zstd gzip
    log {
        output stdout
        format console
    }
}
```

A commented block sits **directly above** the active `:80` block in
the same Caddyfile documenting the cutover:

```caddyfile
# When a domain lands, replace the :80 block below with:
#
#   kasia.example.cz {
#       reverse_proxy web:8000
#       encode zstd gzip
#   }
#
# Caddy auto-provisions Let's Encrypt certs and renews them.
# Also publish :443 in compose.yaml proxy service.
```

The proxy service in [`compose.yaml`](../../compose.yaml) publishes
`:80` only at first; `:443` is added at cutover time. The `caddy`
named volumes (`caddy_data`, `caddy_config`) are present from day
one so cert state persists across container restarts.

## Rationale

- Caddy auto-TLS is zero-config when a hostname is set. For a solo
  operator (Matej) this is the lowest-friction TLS story.
- HTTP-only MVP is a deliberate scope choice — TLS without a
  hostname is a self-signed dance that adds nothing real for ~6
  users on a known LAN reaching the system by IP.
- One file (`Caddyfile`) carries the cutover-comment so the
  next developer knows exactly what to change.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- First deploy can proceed with IP-only access.
- Cutover to a domain is a one-line Caddyfile edit + a compose
  publish-port edit + a `docker compose up -d` reload — no other
  app-level changes.

**Forecloses (without follow-on decision):**

- nginx or Traefik as the production proxy.
- A separate certbot timer / cron — unnecessary with Caddy.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- Single-VPS deploy preference. Reverse proxy + auto-TLS is the
  mainstream small-business shape.

**Makes implementable (0001–0013):**

- N/A directly — infrastructure plumbing.

**Open follow-on:** the **domain name** itself is now a *Decide
later* item (added in this pass to
[`../open-questions.md`](../open-questions.md) § Decide later); no
decision file is needed when it lands — only the Caddyfile edit.
