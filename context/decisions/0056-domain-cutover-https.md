# 0056 — Domain cutover to HTTPS at `kasia.cz`

## Context

[`0024`](./0024-tls-caddy.md) committed Caddy 2 as the reverse proxy and
shipped the first deploy **IP-only over plain HTTP** (`91.98.47.1`), with
the domain left as a *Decide later* item — "no decision file is needed when
it lands, only the Caddyfile edit." That last part turns out to be too
narrow: pointing a real hostname at the box also forces a small set of
Django security settings (proxy header, trusted origins, secure cookies) and
a strict ordering constraint around Let's Encrypt. That shape is a decision,
so it gets its own file.

The domain `kasia.cz` is now available. The goal is to **front-load every
safe change to prod before the A record is pointed**, so the actual cutover
is the smallest possible flip.

The hard constraint that shapes the whole plan:

> **Caddy cannot obtain a TLS cert until DNS resolves to the box.**
> Activating the hostname Caddyfile before the A record points here would
> (a) take the IP site offline — the `:80` catch-all is gone — and (b) make
> Caddy hammer Let's Encrypt's ACME endpoint and fail, risking the LE rate
> limit. `deploy.yml` auto-deploys on push to `main` and runs
> `git reset --hard origin/main`, so the Caddyfile change cannot be a manual
> on-box edit (it would be overwritten on the next deploy) and must be held
> on an unmerged branch until `dig` confirms DNS.

## Options considered

- **Canonical apex `kasia.cz`, `www` → 301 → apex.** Apex is the brand;
  `www` redirects to it. One cert per host, both auto-provisioned by Caddy.
- **Canonical `www.kasia.cz`, apex → www.** Common for CDN/cookie reasons;
  neither applies here (single box, no CDN, no cookie-scope concern at this
  scale).
- **Cloudflare / external TLS in front of the box.** Adds a moving part and
  a second TLS hop for ~6 users; Caddy auto-TLS already covers it.

For the Django settings:

- **Set the proxy header + secure cookies unconditionally in code.** Would
  break the IP-over-HTTP site the moment it deployed (secure cookies stop
  logins on HTTP). Rejected.
- **Env-gate everything; default to today's behaviour.** Lets the code ship
  to prod inertly and the on-box `.env` opt in at cutover. Chosen.

## Choice

**Canonical apex `kasia.cz`; `www.kasia.cz` → 301 → `https://kasia.cz`.**
Caddy auto-provisions Let's Encrypt certs for both hosts once DNS resolves.

Django gains these settings in
[`kasia/settings/base.py`](../../kasia/settings/base.py), all env-gated so
they default to current (HTTP-only) behaviour until the on-box `.env` opts
in:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [...]          # from DJANGO_CSRF_TRUSTED_ORIGINS
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", default=False)
CSRF_COOKIE_SECURE   = _env_bool("DJANGO_SECURE_COOKIES", default=False)
```

- `SECURE_PROXY_SSL_HEADER` is the real win beyond cosmetics: without it,
  password-reset e-mails (`accounts/views.py`, `use_https=request.is_secure()`)
  and the sitemap (`web/views.py`, `request.build_absolute_uri`) emit
  `http://91.98.47.1/...` links. With it they become `https://kasia.cz/...`.
- `CSRF_TRUSTED_ORIGINS` is required for cross-origin POSTs behind a
  TLS-terminating proxy — most visibly the public **kontakt** form and any
  warehouse form.
- Secure cookies are gated behind `DJANGO_SECURE_COOKIES` and flipped to `1`
  only **after** HTTPS is live — on HTTP they would stop logins working.

Explicitly **not** set: `USE_X_FORWARDED_HOST` (Caddy preserves the original
`Host` header by default), `SECURE_SSL_REDIRECT` (Caddy already redirects
http→https; doubling it risks a loop), and `SECURE_PROXY_HEADER_X_FORWARDED_HOST`
(not a real Django setting). `DJANGO_ALLOWED_HOSTS` keeps `127.0.0.1,localhost`
(the container healthcheck hits `http://127.0.0.1:8000/healthz` and
`CommonMiddleware` validates Host under `DEBUG=False`) and keeps `91.98.47.1`
through the transition.

**No Terraform change:** the firewall already opens 443
(`infra/terraform/main.tf`, applied to live firewall id 11145413).

**Ordering — the one change that must wait for DNS:**

1. Phase A (this decision): merge the env-gated Django settings + docs to
   `main` and pre-set the safe `.env` values on the box. Site stays HTTP on
   the IP; everything is inert until `.env` opts in.
2. Domain manager **adds** `A kasia.cz → 91.98.47.1` and
   `A www.kasia.cz → 91.98.47.1`. **MX / mail records untouched.**
3. Confirm `dig +short kasia.cz` / `www.kasia.cz` → `91.98.47.1`.
4. **Only then** merge the held Caddyfile + `compose.yaml` (443) PR → deploy
   activates the hostname block; Caddy provisions the cert on first hit.
5. On the box, set `DJANGO_SECURE_COOKIES=1` and restart web.

## Rationale

- Front-loading the inert settings shrinks the risky window to a single
  DNS-gated merge.
- Apex-canonical matches the brand and the company's e-mail domain; the
  `www` 301 keeps the other spelling working.
- Env-gating keeps the IP-over-HTTP site fully functional right up to the
  flip and makes rollback a `.env` revert, not a code revert.
- Caddy auto-TLS keeps the solo-operator TLS story zero-config, consistent
  with 0024.

## Date & by-whom

2026-06-29 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- Phase A can ship to prod immediately without changing current behaviour.
- The cutover becomes one DNS-gated PR merge + one `.env` line flip.

**Commits us to:**

- `kasia.cz` apex as the canonical host; `www` as a permanent 301 alias.
- Keeping `127.0.0.1,localhost` in `DJANGO_ALLOWED_HOSTS` for the healthcheck.

**Forecloses (without a follow-on decision):**

- An external TLS terminator (Cloudflare etc.) in front of the box.
- `www`-canonical addressing.

**Resolves:** the **Domain name** *Decide later* item from
[`../open-questions.md`](../open-questions.md) (opened alongside 0024).

**Out of scope (noted, not done here):**

- HSTS (`SECURE_HSTS_SECONDS`) — optional hardening, add only after HTTPS is
  proven stable (premature HSTS locks browsers to HTTPS).
- `DEFAULT_FROM_EMAIL` still defaults to `example.cz` in code / `.env.example`;
  the real from-address lives in the on-box `.env`. Tangential to HTTPS.
</content>
</invoke>
