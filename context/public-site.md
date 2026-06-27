# Public marketing site (`web` app)

The public counterpart to [`screens/`](./screens/). It is kept separate
because the public site is a **marketing / communication** surface for the
outside world, not an operator screen for warehouse staff.

- **Decisions:** [`decisions/0050-public-site-and-sklad-split.md`](./decisions/0050-public-site-and-sklad-split.md)
  (the split) and [`decisions/0051-public-site-ia-and-content.md`](./decisions/0051-public-site-ia-and-content.md)
  (this IA + content).
- **Code:** the `web` Django app + templates under
  `kasia/templates/web/`. Curated content lives in `web/content.py`
  (single source for company facts + locations) — **decoupled from the
  warehouse DB** (no SKU / stock data on the public site).

## URL map

Public surface lives at the domain root; the warehouse app is under
`/sklad/` (per 0050).

| Path | View | Page |
|------|------|------|
| `/` | `web:home` | Domů |
| `/o-nas/` | `web:o_nas` | O nás |
| `/provozovny/` | `web:provozovny` | Provozovny |
| `/kontakt/` | `web:kontakt` | Kontakt (form GET/POST) |
| `/kontakt/odeslano/` | `web:kontakt_ok` | Poptávka odeslána |
| `/robots.txt` | `web:robots_txt` | robots (hand-rolled) |
| `/sitemap.xml` | `web:sitemap_xml` | sitemap (hand-rolled) |

Every public view is `@login_not_required` (the global
`LoginRequiredMiddleware` has no include-level opt-out). The footer
carries a discreet **"Sklad / Přihlášení"** link into `/sklad/`.

## Page content map (first build — four pages, locked by Matej 2026-06-26)

### Domů (`/`)
- Hero: heritage since *leden 1993* + brand promise.
- Proof stat: **"Přes 369 druhů koření a 236 kulinářských produktů."**
- Short who-we-are / who-we-serve line (B2B: velkoobchod + gastro,
  značka VERA GURMET).
- Primary CTAs → Provozovny + Kontakt.
- Teaser blocks → O nás / Provozovny / Kontakt.

### O nás (`/o-nas/`)
- Příběh od *ledna 1993*, rodinná firma, sídlo Říčany u Prahy.
- Co děláme: dovoz → čištění/třídění/mletí → míchání směsí → balení →
  dodávky pod značkou VERA GURMET.
- Concise (nice-to-have per Matej). CSR / sponzoring / kvalita may become
  short *sections* here later — **not** separate pages now.

### Provozovny (`/provozovny/`)
Per-location card (adresa, otevírací doba, telefon, odkaz na mapu), from
[`warehouses.md`](./warehouses.md):
- **Říčany u Prahy** — sídlo, Nádražní 1202/5, 251 01.
- **Týniště nad Orlicí** — provozní sklad. ⚠ ulice + telefon **nejsou v
  repu** → placeholder + "doplnit od Petra" (neimprovizovat adresy).
- **Sezimovo Ústí** — provozní sklad. ⚠ stejné placeholdery.

### Kontakt (`/kontakt/`)
- Adresa sídla, telefony (+420 323 601 422 / 424), e-mail (info@kasia.cz),
  IČO 25756729 (+ DIČ až bude dodáno), datová schránka emye9prc,
  otevírací doba Po–Pá 7:00–15:00, odkaz na mapu.
- **Poptávkový / kontaktní formulář** → `ContactInquiry`.
  - Persisted to DB first, **then** best-effort e-mail (try/except, never
    re-raises — durability over uptime, per 0051 + 0019). Recipients via
    `settings.CONTACT_INQUIRY_RECIPIENTS` (default info@kasia.cz).
  - GDPR consent checkbox (required, not stored as a column).
  - Plain `<form method="post">` + `{% csrf_token %}` — the public base
    ships **no htmx** (app-only).
  - Read-only `ContactInquiryAdmin` for review (+ "vyřízeno" toggle).

## Modern essentials (every page)
Responsive layout; SEO `<title>` + meta description + Open Graph; JSON-LD
`Organization` structured data; hand-rolled `robots.txt` + `sitemap.xml`
(no `django.contrib.sitemaps` — right-sized for four pages); Czech
cookie/contact-consent note in the footer; accessible markup
(skip-link, `lang="cs"`, `aria-current`); favicon reused from
`kasia/static/brand/`.

## Czech copy notes
- Czech only for the first build; templates are **i18n-ready** (clean
  structure, `lang="cs"`, all copy in templates not images) so EN/RU can
  layer on later. Full `{% trans %}` wrapping is deferred until a second
  language is actually requested.
- Diacritics intact everywhere; domain spellings per
  [`domain-glossary.md`](./domain-glossary.md).

## Explicitly deferred (clean room left in the IA + nav)
Sortiment / Naše produkty, Encyklopedie koření, Sponzorství / CSR as its
own page, "Pro koho / segmenty". Each becomes a later pass; the nav adds
them without restructuring.

## Open data to source from Petr
- TYN + SEZ street addresses and per-branch phone numbers.
- DIČ (if VAT-registered).
- Real product/spice photography (no text-to-image tool; mockups use
  CSS/gradient placeholders + existing brand art).

## Visual design
The first real templates are clean and functional placeholders. Final
visual direction goes through the `design-options/public/` mockup gallery
(linked from `/navrhy/`) → Petr picks → log a decision → port the winner
into these `web/` templates. Fresh SVG logo concepts ride along in the
gallery.
