# 0076 — Public-site analytics: self-hosted Umami at `analytics.kasia.cz`

> **Superseded in part by [`0077`](./0077-sklad-usage-tracking.md)** — the
> Forecloses item "Analytics on any `/sklad/` surface" is narrowed to
> third-party/browser trackers; a first-party server-side visit log is now in
> scope per 0077. Everything else — including the Umami context-processor
> path gate — stands.

**Date:** 2026-07-14
**Decider:** Matej
**Status:** Active
**Builds on:** [`0050`](./0050-public-site-and-sklad-split.md) +
[`0051`](./0051-public-site-ia-and-content.md) (the public marketing site whose
traffic this measures), [`0056`](./0056-domain-cutover-https.md) (the HTTPS /
`kasia.cz` cutover this was sequenced behind — live since 2026-07-14; the DNS
gate + post-merge proxy force-recreate patterns are reused verbatim),
[`0027`](./0027-hosting-hetzner.md) (the CPX22 box + nightly restic backups
the new volume joins), [`0023`](./0023-runtime-orchestration-compose.md)
(compose is the runtime the new services slot into).

## Context

The stack ships zero behavioural analytics. Caddy logs every request to
stdout (ephemeral — gone on container restart), the Hetzner console shows
only box-level CPU/RAM/bandwidth, and Django logs nothing on a 2xx path.
Since 2026-07-14 the public marketing site is taking unauthenticated traffic
on `https://kasia.cz`, and there is no answer to "how many visitors, from
where, on which pages, with which referrer?".

Analytics is a **new layer** not covered by decisions 0014–0027, so per
`no-premature-tech-choices.md` this decision (plus the
`context/tech-options.md` § 7 comparison) gates any code or compose change.

Two recent decisions are the observability precedents to distinguish from:
[`0074`](./0074-event-driven-low-stock-alert.md) (low-stock alert) and
[`0075`](./0075-email-outbox-log.md) (EmailLog outbox) both stayed **in-app**
— Django models, no new infra — because they observe *warehouse* events made
by known, logged-in operators. This decision is about **public behavioural
pageview tracking of anonymous visitors**, which the Django app cannot see
without either logging PII itself or embedding a tracker; that is what
justifies one new container pair where 0074/0075 needed none.

Timing note: the 14-day shadow run has not started and public traffic today
is minimal. The point of landing analytics now is to have the baseline
recording *before* real traffic arrives — the dashboard will be near-empty
for a while, and that is expected.

## Options considered

(Trade-off detail in [`../tech-options.md`](../tech-options.md) § 7.)

1. **Umami v2, self-hosted on the existing CPX22.** Apache-2.0, Node.js +
   its own Postgres container, ~150 MB RAM total. Cookie-less, daily-rotating
   pseudonymised visitor hash. **Chosen.**
2. **Plausible CE v2, self-hosted.** Same privacy posture, but requires
   Postgres *and* ClickHouse — a second analytical DB engine for a site with
   a handful of daily visitors. Rejected as oversized.
3. **Umami Cloud / Plausible Cloud** (~€9/mo). Rejected on cost — recurring
   spend that roughly doubles the entire hosting bill (~€11.50/mo per 0027)
   for a low-volume site.
4. **GoAccess over persisted Caddy logs.** No JS tag at all, but requires
   making Caddy logs durable first, and gives no referrer parsing on
   bot-filtered hits, no visit sessions, no country panel. Rejected.
5. **Do nothing.** Status quo. Rejected once `kasia.cz` takes real
   unauthenticated traffic — Petr's obvious first question ("kouká se na to
   někdo?") would have no answer.

## Choice

**Self-hosted Umami v2 on the existing Hetzner CPX22, at
`analytics.kasia.cz`, tracking the public site only.**

1. **Two new compose services**, both `profiles: [prod]` (matching `backup`;
   local `make up` never starts them): `umami` (pinned release image,
   `DISABLE_TELEMETRY=1`) + `umami-db` (own `postgres:18-trixie` container,
   own `umami_pgdata` volume — the warehouse DB stays untouched).
2. **Own hostname `analytics.kasia.cz`** — a sibling Caddy site block; Caddy
   auto-provisions the LE cert. Same DNS gate as 0056: the Caddyfile block
   stays on an unmerged branch until `dig +short analytics.kasia.cz` returns
   the box IP.
3. **Tracker tag on the public surface only.** A conditional
   `<script defer src=… data-website-id=…>` in `kasia/templates/web/base.html`,
   fed by a new `web/context_processors.py::umami` context processor reading
   `UMAMI_WEBSITE_ID` / `UMAMI_SCRIPT_URL` from the environment at request
   time. **Privacy boundary:** the processor returns empty values for any
   request path under `/sklad/` or `/admin/` — this matters because the
   operator login page (`/sklad/prihlaseni/`) extends `web/base.html` for its
   chrome. The warehouse base template gets nothing. Operators are known
   users; `auth_user.last_login` + the audit trail are their record.
4. **No consent banner.** Umami is cookie-less and pseudonymises visitors
   with a daily-rotating salt+IP+UA hash; no personal data is stored, so no
   GDPR / Czech ePrivacy consent is required. A future agent should not add
   a banner preemptively.
5. **Secrets in the on-box `.env` only** (`UMAMI_DB_PASSWORD`,
   `UMAMI_APP_SECRET`, `UMAMI_WEBSITE_ID`), documented-but-unset in
   `.env.example`. Seeded **before** the compose change merges, because
   Postgres bakes the password into the cluster at first initdb.
6. **Backups:** `umami_pgdata` is added read-only to the existing
   `offen/docker-volume-backup` service; the nightly restic run to the
   Storage Box (0027) covers it with no new tooling.
7. **Dashboard auth:** Umami's built-in login, single account for Matej;
   default `admin / umami` password rotated at first boot.

## Rationale

- **This is not the "analytics warehouse / event pipeline / data lake" that
  `right-sized-for-small-business.md` rejects.** It is a single-page
  visitor-session tracker: one container pair, default pageviews only, no
  event ingestion, no data lake, megabytes-scale storage. The rule gains a
  one-clause carve-out pointing here so the distinction is on record.
- **Self-hosted beats cloud on cost** (€0/mo vs ~€9/mo) and keeps visitor
  data on our box; the CPX22 has ~3.4 GB RAM headroom, so +150 MB is noise.
- **Umami beats Plausible CE on footprint** — one extra Postgres vs
  Postgres + ClickHouse — at identical privacy posture and sufficient
  features (pages, referrers, countries, realtime).
- **Separate Postgres container** keeps the warehouse DB's failure domain,
  upgrade cadence, and restore drill untouched; the two clusters never share
  a volume.
- **Cookie-less by default** means no consent-banner work and no legal
  surface on the marketing site.

## Date & by-whom

2026-07-14 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- `compose.yaml` + `Caddyfile` + `.env.example` changes for the two
  services and the `analytics.kasia.cz` site block (held until the A record
  resolves), then the tracker tag + context processor + tests.
- Custom Umami *events* (e.g. tracking the "Kontakt" click) later — the tag
  is the integration point; no new decision needed for default-feature use.

**Commits us to:**

- One more container pair + Postgres cluster to keep patched (image tag
  bumps go through `compose.yaml` per `infra-as-code.md`).
- The `/sklad/` + `/admin/` path gate in the context processor is a
  **load-bearing privacy boundary** — a test pins it; removing it is a new
  decision, not a refactor.
- If a future decision adds CSP headers, `script-src` and `connect-src`
  must include `analytics.kasia.cz`.

**Forecloses (without a follow-on decision):**

- Analytics on any `/sklad/` surface.
- A cookie-consent banner for the tracker (not needed; do not add one
  preemptively).
- Sentry-style error tracking — different problem (operational, not
  behavioural); needs its own numbered decision.

**Resolves:** public-site analytics — a previously-unlogged question opened
in effect alongside 0051 (now recorded and closed in
[`../open-questions.md`](../open-questions.md) § Decide later).
