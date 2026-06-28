# Public marketing site (`web` app)

The public counterpart to [`screens/`](./screens/). It is kept separate
because the public site is a **marketing / communication** surface for the
outside world, not an operator screen for warehouse staff.

- **Decisions:** [`decisions/0050-public-site-and-sklad-split.md`](./decisions/0050-public-site-and-sklad-split.md)
  (the split), [`decisions/0051-public-site-ia-and-content.md`](./decisions/0051-public-site-ia-and-content.md)
  (the IA + content), and
  [`decisions/0052-kontakt-info-only-drop-contactinquiry.md`](./decisions/0052-kontakt-info-only-drop-contactinquiry.md)
  (Kontakt is now **info-only** — the poptávkový formulář + `ContactInquiry`
  model were removed; `web` is a clean leaf app with **no models**).
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
| `/kontakt/` | `web:kontakt` | Kontakt (info-only, GET) |
| `/robots.txt` | `web:robots_txt` | robots (hand-rolled) |
| `/sitemap.xml` | `web:sitemap_xml` | sitemap (hand-rolled) |

Every public view is `@login_not_required` (the global
`LoginRequiredMiddleware` has no include-level opt-out). Staff reach the app
via a discreet, muted **"Přihlášení"** link in the header (→ `{% url 'login' %}`,
`/sklad/prihlaseni/`) and the **"Sklad / Přihlášení"** link in the footer.
"Sklad" is deliberately **not** in the marketing nav (decision 0052) so casual
public visitors aren't led into the app.

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
Card per location (building photo, role badge, adresa, telefon, otevírací
doba, **embedded OSM map** + "Otevřít v mapách" link) — real public data
from kasia.cz. **Four** locations (the public site is curated and decoupled
from the warehouse DB, which still tracks stock only at TYN + SEZ — see
[`warehouses.md`](./warehouses.md)):
- **Říčany u Prahy** — *Sídlo společnosti*, Nádražní 1202/5, 251 01 ·
  +420 323 601 422.
- **Sezimovo Ústí** — provozovna, Pod Kovosvitem 1096, 391 02 ·
  +420 607 190 150.
- **Toužim** — provozovna, Malé náměstí 608, 364 01 · +420 775 353 637.
- **Týniště nad Orlicí** — provozovna, Turkova 77, 517 21 · +420 604 640 950.

### Kontakt (`/kontakt/`) — info-only (decision 0052)
No form. The page is a contact directory:
- **Contact panel**: adresa sídla, telefony (+420 323 601 422 / 424),
  e-mail (info@kasia.cz), **fax +420 323 602 077**, IČO 25756729 (+ DIČ až
  bude dodáno), datová schránka emye9prc, otevírací doba Po–Pá 7:00–15:00.
- **Kontaktní osoby** (z kasia.cz): Ing. Jaroslav Šulc (Prodej),
  Věra Kovačková (Administrativa), Petr Formánek (Nákup) — foto + jméno +
  role; per-person e-mail/telefon se zobrazí, až je Matej dodá (placeholder
  "" → odkaz se nevykreslí).
- **Embedded OSM map** of the sídlo + "Otevřít v mapách" link.

Map coords are geocoded once during development (Nominatim) and hardcoded in
`web/content.py`; the OSM export iframe is cookie-free, the site's only
external runtime dependency, and degrades gracefully (the "Otevřít v mapách"
link still works if OSM is down).

## Modern essentials (every page)
Responsive layout; SEO `<title>` + meta description + Open Graph; JSON-LD
`Organization` structured data; hand-rolled `robots.txt` + `sitemap.xml`
(no `django.contrib.sitemaps` — right-sized for four pages); Czech privacy
note in the footer (no tracking cookies; OSM map embeds may expose the
visitor IP to the map host — kept honest per 0052); accessible markup
(skip-link, `lang="cs"`, `aria-current`); favicon reused from
`kasia/static/brand/`. Exec portraits + branch photos live in
`kasia/static/web/` (`exec-*.jpg`, `branch-*.jpg`).

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

## Open data to source from Petr / Matej
- Per-person exec **e-mails + phones** (Šulc / Kovačková / Formánek) —
  placeholders until supplied (the link is hidden when empty).
- DIČ (if VAT-registered).
- Branch/exec photos are the scraped kasia.cz images — can be swapped or
  dropped later (templates render gracefully without a photo).

## Visual design
Light/minimalist green-brand base, built directly into the `web/` templates
(Kontakt + Provozovny rebuilt from real kasia.cz data per 0052, no
mockup-gallery round). The broader `design-options/public/` gallery (linked
from `/navrhy/`) remains a style-exploration artifact for the homepage
direction; its `05-kontakt.html` still shows a form and is **not** the live
page.
