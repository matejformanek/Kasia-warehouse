# 0106 — Public-site SEO hardening pass (canonical, per-page OG, LocalBusiness, sitemap lastmod)

> Drafted 2026-07-14 as "0076" on the unshipped `ft_wa_seo` branch; that
> number went to [`0076-public-site-analytics.md`](./0076-public-site-analytics.md)
> (Umami) in the meantime, so the SEO pass lands as **0106**.

## Context

The public site shipped with a solid SEO baseline per
[`0051`](./0051-public-site-ia-and-content.md) (per-page titles + meta
descriptions, Open Graph, `Organization` JSON-LD, hand-rolled `robots.txt` +
`sitemap.xml`) and the 0058 five-page IA. The HTTPS cutover
([`0056`](./0056-domain-cutover-https.md)) executed 2026-07-14: prod is live
at `https://kasia.cz`, Caddy 301s the IP and `www.kasia.cz` to the apex,
`web:8000` is not published — so Caddy is the **only** external path to
Django and every request arrives as `Host: kasia.cz` over proxied HTTPS
(`SECURE_PROXY_SSL_HEADER` active). Request-derived absolute URLs are
therefore already canonical in prod.

Gaps (re-verified against `main` @ `391dd60`, 2026-10-06):

- No `<link rel="canonical">` and no `og:url` on any page.
- No per-page OG title/description — the `og_title` / `og_description`
  blocks exist in `web/base.html` but no page overrides them; all 5 pages
  share one generic OG title.
- `LocalBusiness` JSON-LD was promised in 0051's modern-web essentials but
  never shipped — only `Organization` exists, while `web/content.py` holds
  exact NAP + geo + hours for all 4 provozovny. This is the markup that ties
  the site to the Google Maps listing (Matej owns the Google Business
  Profile as of 2026-07-14 — website URL + opening hours set there).
- `sitemap.xml` lacks `<lastmod>`.
- `og:image` has no dimensions/alt; `twitter:card summary` crops the wide
  1600×619 logo badly.

## Options considered

- **A — Env-configured base URL (`DJANGO_PUBLIC_BASE_URL`)** for canonical /
  og:url / sitemap. Rejected: host canonicalization is already solved at the
  Caddy edge (0056 apex-canonical + the www→apex 301); an env knob would be
  a second source of truth that can drift.
- **B — Request-derived base URL via a small context processor (chosen).**
  `f"{request.scheme}://{request.get_host()}"` — correct in prod because
  Caddy pins the host, correct locally (`http://localhost`), correct under
  tests (`http://testserver`). No new setting.
- **C — `django.contrib.sitemaps` + `sites` framework.** Rejected again
  (0051): right-sized — 5 static pages don't justify the framework.

## Choice

**Option B — a `web/context_processors.py::seo` context processor supplies
`site_url` + `canonical_url` to every template render** (it sits next to the
existing `umami` processor from 0076), and this pass ships:

- `<link rel="canonical">`, `og:url`, a `{% block robots %}` override hook
  (default `index, follow`), and `<meta name="theme-color" content="#006634">`
  in `web/base.html`.
- Per-page `og_title` / `og_description` overrides on all 5 pages, mirroring
  each page's `title` / `meta_description` copy.
- `og:image` width/height/alt/type + `twitter:card summary_large_image` +
  `twitter:image` (the 1600×619 logo is a wide image; `summary` crops it).
- `Organization` JSON-LD enriched: `@id` (`{site_url}/#organization`),
  `description`, `brand` (VERA GURMET), `areaServed: "CZ"`, `contactPoint`,
  and `sameAs` → the Google Business Profile share link Matej supplied
  2026-07-14 (recorded in `context/research-sources.md`).
- **`LocalBusiness` JSON-LD ×4** on `/provozovny/` — an `@graph` looping
  `PROVOZOVNY`, one node per branch with stable `@id`
  (`{site_url}/provozovny/#<slug>`; new `slug` key per branch in
  `web/content.py`), NAP, `GeoCoordinates`, `openingHoursSpecification`
  Mon–Fri 07:00–15:00, and `parentOrganization` → the Organization `@id`.
- `sitemap.xml` gains `<lastmod>` (a manually-bumped
  `CONTENT_LASTMOD` in `web/content.py`). **No changefreq/priority** —
  Google ignores both.
- `robots.txt` Sitemap line reuses `{{ site_url }}` (same helper as the
  head — the three surfaces can never diverge).

## Rationale

- **No env var**: the Caddy edge guarantees the host (0056); request-derived
  URLs are the value already proven correct by the live sitemap. This relies
  on the www→apex 301 staying in the Caddyfile.
- **JSON-LD is hand-built in templates** (no serializer), so the
  `web/content.py` values feeding it must stay free of `& " ' < >` —
  Django's HTML auto-escaping would otherwise emit `&amp;`-style entities
  inside the JSON. Current values are clean; keep them so. The tests parse
  every JSON-LD block with `json.loads`, so a broken value fails CI.
- `LocalBusiness` fulfils the one unshipped 0051 essential and ties the site
  to the (now owner-verified) Google Business Profile.
- Alt-text audit ran with this pass: every `<img>` on the 5 pages + base
  already carries meaningful Czech `alt` — no fixes needed.

**Out of scope:** HSTS (0056's follow-up), BreadcrumbList/FAQ markup,
hreflang (single-language site), `WebSite` + `SearchAction` (no site
search). User-side follow-ups (not code): Google Search Console
registration (DNS TXT preferred — else a one-line meta-tag commit once the
token exists) + sitemap submission; pasting `context/gbp-description.txt`
into the Business Profile.

## Date & by-whom

2026-07-14 — Matej (full recommended pass confirmed in-session); ported to
current `main` and renumbered 2026-10-06.

## Consequences

- **Amends [`0051`](./0051-public-site-ia-and-content.md)** (fulfils the
  LocalBusiness essential; adds canonical/og:url, robots-meta hook,
  theme-color, sitemap lastmod). Aligns with 0056's apex-canonical stance.
- The `seo` context processor (`site_url` / `canonical_url`) and the
  `{% block robots %}` hook become part of the stable public-template
  contract — renaming them is a new decision (recorded in
  `.claude/rules/design-system.md`).
- `CONTENT_LASTMOD` in `web/content.py` must be bumped manually whenever
  public copy changes (date-only ISO is valid W3C datetime).
- Commits us to keeping `web/content.py` public-facing string values free
  of `& " ' < >` while JSON-LD stays hand-built.
