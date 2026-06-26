# 0050 — Public-site information architecture, content, and the `ContactInquiry` model

## Context

[`0049`](./0049-public-site-and-sklad-split.md) establishes *that* a
public marketing site lives at `/` (warehouse app under `/sklad/`). This
decision fixes *what* the public site is: its information architecture,
its content sourcing, the durable contact-form store, and the modern-web
essentials — all designed from the business
([`../company-profile.md`](../company-profile.md),
[`../warehouses.md`](../warehouses.md)), **not** by mirroring the old
kasia.cz.

The old site (captured 2026-06-26) had: Naše produkty · Encyklopedie
koření · O nás · Provozovny · Kontakt; a "přes 369 druhů koření / 236
kulinářských produktů" proof stat; founding *leden 1993*; the VERA GURMET
gastro brand; an e-shop via PROFIpotraviny.cz; a chráněná dílna and an RC
Rugby Říčany sponsorship. **The owner's decision is not to mirror it** —
design a relevant IA for a 2026 B2B spice distributor and decide what
genuinely belongs now.

## Options considered

- **A — Four curated, template-rendered pages, Czech-only, i18n-ready
  (chosen).** Domů, O nás, Provozovny, Kontakt. Content lives in Django
  templates (no CMS). The kontakt form persists to the DB and then
  attempts e-mail.
- **B — Mirror the old site's five-section IA** (incl. Naše produkty +
  Encyklopedie koření). Rejected by the owner — the product catalogue and
  spice encyclopedia are large content surfaces that need real sourcing
  and upkeep; they are deferred, not first-build.
- **C — A CMS-backed site.** Rejected per
  [`0049`](./0049-public-site-and-sklad-split.md) option D — four mostly
  static pages don't justify CMS complexity.
- **D — An email-only kontakt form (no DB store).** Rejected — see the
  `ContactInquiry` rationale below; without persistence, inquiries are
  silently lost whenever SMTP is unconfigured.

## Choice

**Option A — four pages, Czech-only (templates i18n-ready so EN/RU can
layer on later), content curated in templates and decoupled from the
warehouse DB. The kontakt form persists a `ContactInquiry` row, then
attempts e-mail.**

### Information architecture (first build — locked by Matej 2026-06-26)

- **Domů (`/`)** — hero (heritage since *leden 1993* + the "přes 369 druhů
  koření / 236 kulinářských produktů" proof stat), a short
  who-we-are / who-we-serve line, brand promise, primary CTAs to
  Provozovny + Kontakt, and teaser blocks linking O nás / Provozovny /
  Kontakt.
- **O nás (`/o-nas/`)** — příběh od ledna 1993, rodinná firma, dovoz +
  zpracování koření v Říčanech. Concise. (CSR / sponzoring / kvalita may
  become short *sections* here later; they are **not** separate pages
  now.)
- **Provozovny (`/provozovny/`)** — the physical locations from
  [`../warehouses.md`](../warehouses.md): **Říčany u Prahy (sídlo,
  Nádražní 1202/5)**, **Týniště nad Orlicí**, **Sezimovo Ústí**. Per-card:
  adresa, otevírací doba, telefon, static map link. ⚠ TYN/SEZ street
  addresses + per-branch phones are **not in the repo** — placeholders +
  an explicit "doplnit od Petra" note; do not invent addresses.
- **Kontakt (`/kontakt/`)** — adresa sídla, telefon(y)
  (+420 323 601 422 / 424), e-mail (info@kasia.cz), IČO 25756729 (+ DIČ
  when supplied), datová schránka emye9prc, otevírací doba
  (Po–Pá 7:00–15:00), static map, and the poptávkový / kontaktní formulář.

**Explicitly deferred (not in first build):** Sortiment / Naše produkty,
Encyklopedie koření, Sponzorství / CSR as its own page, and a
"Pro koho / segmenty" page. The IA + nav leave clean room to add these
later without restructuring.

### `ContactInquiry` model — justified, not a default

The kontakt form **persists to the DB first, then attempts e-mail.**
Rationale:

- Production SMTP is still deferred (state.md § Hetzner; SMTP block in the
  box `.env` is blank). An **email-only** form would **silently lose every
  inquiry** until SMTP lands — that violates
  `right-sized-for-small-business.md` ("backups / durability over
  uptime").
- Precedent: the `Feedback` model ([`0046`](./0046-support-page.md)) is the
  same shape — durable capture + admin review.

Fields: `name`, `email`, `phone` (optional), `message`, `created_at`,
optional `handled` flag. **Email is a plain string, never linked to
`User`** — public submitters are not accounts. The e-mail send wraps in
try/except and **never re-raises** (mirrors
`inventory/services.py:send_dodaci_list_email`, per
[`0019`](./0019-email-smtp-sync.md)); a failed send must not lose the
saved row. A read-only `ContactInquiryAdmin` surfaces inquiries for
review.

### Modern-web essentials (every page)

Responsive layout; SEO `<title>` + meta description + Open Graph;
JSON-LD `Organization` / `LocalBusiness` structured data; hand-rolled
`sitemap.xml` + `robots.txt` (no `django.contrib.sitemaps` — right-sized
for 4 pages); a Czech GDPR cookie / contact-consent note; accessible
markup; favicon (reuse `kasia/static/brand/`); and a discreet
"Sklad / Přihlášení" link (footer) into `/sklad/`.

### Content decoupled from the warehouse DB

Public content is curated in templates. Internal SKUs (raw_spice /
mixture, branch stock) are operational, not marketing — the public site
does **not** read the warehouse DB. (When a Sortiment page lands later, it
will be curated content too, not a live stock dump.)

## Rationale

- **Designed from the business, deferring large content surfaces.** The
  four pages are the ones a B2B buyer or partner actually needs to find
  Kasia and get in touch; the product catalogue and encyclopedia are real
  projects deferred until there's content + upkeep capacity.
- **Durability over uptime for inquiries** — the one model on the public
  site exists specifically because SMTP isn't guaranteed.
- **Czech-only but i18n-ready** keeps the first build small while leaving
  the EN/RU door open without a later restructure.

## Date & by-whom

2026-06-26 — Matej (owner-side; four-page scope locked).

## Consequences — things this now blocks or unblocks

**Unblocks:**

- The `web` app's templates, views, the `ContactInquiry` model +
  migration + read-only admin, and the robots/sitemap views.
- The design-review track: standalone public mockups under
  `design-options/public/` → Petr picks a direction → log a decision →
  port the winner into the real `web/` templates.

**Defers (clean room left in the IA + nav):**

- Sortiment / Naše produkty, Encyklopedie koření, Sponzorství / CSR page,
  Pro koho / segmenty. Each becomes a later pass.

**Open data to source from Petr (placeholders until supplied):**

- TYN + SEZ street addresses and per-branch phone numbers.
- DIČ (if VAT-registered) for the Kontakt page.
- Real product/spice photography (no text-to-image tool available;
  mockups use CSS/gradient placeholders + existing brand art).

**New non-trivial-decision trigger:** persisting user-submitted data
(`ContactInquiry`, like `Feedback`) is now noted in
`.claude/rules/decision-log-discipline.md` as a case that warrants a
decision entry.
