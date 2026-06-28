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
via a single **"Přihlášení do skladu"** link in the footer's *Odkazy* column
(→ `{% url 'login' %}`, `/sklad/prihlaseni/`). The pass-1 header login link was
**removed** (pass 2, 2026-06-28) — it was misleading for customers, who have no
app access. Login is **footer-only**, and "Sklad" is deliberately **not** in the
marketing nav so casual public visitors aren't led into the app.

The login page (`registration/login.html`) is **public-branded**: it extends
`web/base.html` (green chrome + cleaned footer) and shows two panels —
**Zaměstnanci** (the sign-in form + "Zapomenuté heslo?") and **Zákazníci** (a
note that this is the staff warehouse, with links back to the site + Kontakt).
The `login` route sets `redirect_authenticated_user=True`, so an
already-logged-in visitor hitting `/sklad/prihlaseni/` is bounced straight to
`LOGIN_REDIRECT_URL` (`inventory:home`, `/sklad/`); `extra_context` feeds
`company` / `nav` into the public chrome on both GET and invalid POST.

## Page content map (first build — four pages, locked by Matej 2026-06-26)

### Domů (`/`) — enriched for B2B, de-boxed (pass 2, 2026-06-28; section flow
revised 2026-06-29 on Matej's feedback — refines 0054, not a new direction)
- Hero: brand promise headline **"Koření, které dělá kuchyni"** (the *Rodinná
  firma od roku 1993* eyebrow was dropped from the hero — it now framing the
  prose band below).
- Proof stat in the hero: **"Přes 369 druhů koření a 236 kulinářských produktů."**
- **Co děláme** (capabilities): the six icon cards — dovoz a kvalita, zpracování,
  míchání směsí, balení, mokrá výroba, vlajkové produkty. The one section where
  cards earn their place.
- **Prose "O nás" band** (`.about-band`, white bg, *not* boxes): heading +
  short rodinná-firma / dovozce-i-zpracovatel copy + *Více o nás →*, paired with
  the Říčany photo. This carries the *od roku 1993* framing.
- **Komu dodáváme** (segments): light inline icon rows (`.feature-list`, no card
  chrome) — velkoobchody, gastro provozy, výrobci uzenin + potravin — plus a
  one-line sortiment mention (no product list, no catalog — Produkty/Encyklopedie
  stay deferred per 0051).
- **Proč Kasia** (why-us): borderless 2-column **checklist** (`.checklist`, the
  main de-boxing move) — 30+ let, dovozce i zpracovatel, stálá kvalita +
  dohledatelnost, rychlé dodávky, síť obchodních zástupců, dovoz i export.
- **Dark-green CTA band** (`.cta-band`): *Pojďme spolupracovat* + CTAs, closes the
  page on colour. The three trailing teaser cards (O nás / Provozovny / Kontakt)
  were dropped — that nav lives in the header, footer, and this CTA.

### O nás (`/o-nas/`) — long-form article (pass 2, 2026-06-28)
Real long-form article rebuilt from kasia.cz/about (Matej: include export/reach,
omit RC Rugby sponsorship). Sections: Lead (rodinná firma od *ledna 1993*,
přímý dovozce + zpracovatel) → Od koření k celému sortimentu (sušená zelenina,
byliny; silná pozice v sušeném česneku/cibuli/majoránce) → Vlastní výroba
(1995 česneková pasta v Týništi, mokrá výroba, 1998 míchárna Strančice, 2011
výrobna Sezimovo Ústí, gastro směsi z Toužimi pod značkou VERA GURMET, VEGA +
Zlaté kuře) → Dovoz a export (re-export do PL/UA/SK/IL/BY/NL; kmín, černý pepř,
koriandr) → Dostupnost a dosah (sídlo Říčany ~15 km u dálnice na Brno, síť
obchodních zástupců po ČR) → CTA. Export markets live in
`COMPANY["export_markets"]`.

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
(no `django.contrib.sitemaps` — right-sized for four pages); short Czech
privacy note in the footer (no tracking cookies; mapy vkládány z
OpenStreetMap — pass 2 shortened it, dropping the long IP-clause sentence);
the footer is three tidy columns (firma / Kontakt / Odkazy) + a legal strip;
accessible markup
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

As of [`0054`](./decisions/0054-adopt-ui-directions.md) the live look ports the
`design-options/public/11-centered-modern.html` direction onto this content:
centered/curvy/green.

### Visual assets & styling (decision 0054)
- **Logo:** `kasia/static/brand/kasia-logo.jpg`, top-left wordmark
  ("Kasia vera"); referenced via `{% static %}`.
- **SVG art:** hand-authored green vector, no raster generation.
  `kasia/static/web/art-hero.svg` is the homepage hero motif (mortar +
  herbs); homepage cards use inline green SVG line-icons. A commented
  `web/hero-photo.jpg` slot in `web/home.html` is left for Petr's real photo.
  New SVG assets are committed to git so build-time `collectstatic` finds them.
- **Fonts:** **Sora** (headings) + **Inter** (body), loaded from Google Fonts
  via a `<link>` placed before the `<style>` block in `web/base.html`.
- **Palette:** company green — `--green:#235c33`, `--green-dark:#18421f`,
  `--green-soft:#eef4ee`, accent `--spice:#c2581c`. Defined in the
  `web/base.html` `:root`; reference the vars, not raw hex.
- **Radius / shadow:** 18px (cards) / 999px (pills); soft layered shadows.
- **Maps:** functional OpenStreetMap embeds stay on Provozovny/Kontakt
  (`.map-embed` frame restyled only); the footer keeps the cookie-free note.
- **Class contract + sklad counterpart:** see
  [`.claude/rules/design-system.md`](../.claude/rules/design-system.md).
