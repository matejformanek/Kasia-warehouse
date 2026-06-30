# Public-site research — UX findings, visual POV & per-page blueprint

## 1. How to read this

This is an exploration document for the Kasia public-site overhaul — it gathers UX, conversion, accessibility and "anti-AI-template" research and translates each finding into an honest, Kasia-specific recommendation. It feeds **Checkpoint A** (direction-setting); it is not a build spec and locks nothing. The one guardrail under everything below: **we use only facts Kasia can actually stand behind** — 369 druhů koření, founded leden 1993, four real provozovny with photos, named export markets — and we never fabricate certifications, testimonials, customer logos, prices, capacity metrics, or product/process photography we don't have. Where a section would need a fact we lack, it becomes an honest "doplníme" slot or is omitted entirely.

---

## 2. UX findings (prioritized)

P1 = the eight highest-leverage improvements for the overhaul. The rest are supporting craft.

### Craft & hierarchy

- **(P1) Earned card use, not card-for-everything.** Cards impose equal visual weight; when every section is a card grid the page reads flat and "Notion-export." *For Kasia:* keep the 6-cell capability grid (genuinely scannable), but render "Proč Kasia" as a borderless checklist, "O nás" as a prose band, and audience segments as inline feature rows — vary the structure. [nngroup.com/articles/visual-hierarchy-ux-definition](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/)
- **(P1) Layout variation as editorial signal.** The AI statistical default is hero → 3-col card grid → 3-col card grid → testimonials → CTA. Each section earning its own structural shape is the clearest "a human laid this out" signal. *For Kasia:* before shipping any new section, confirm its shape differs from its neighbours. [shuffle.dev/blog/2026/01/why-do-most-ai-generated-websites-look-the-same](https://shuffle.dev/blog/2026/01/why-do-most-ai-generated-websites-look-the-same/)
- **Three type tiers max + clamp() fluid scale + eyebrow as a "free" label tier.** More than three named sizes creates ambiguity; the eyebrow pill labels sections through texture, not size. *For Kasia:* the existing scale is well-chosen — add explicit `line-height: 1.3` on h3 so wrapped card headings don't inherit tight leading; never introduce h4/h5. [smashingmagazine.com/2022/10/typographic-hierarchies](https://www.smashingmagazine.com/2022/10/typographic-hierarchies/)
- **Two complementary typefaces with distinct roles.** One font flat across everything is a primary AI tell; two faces with clear display-vs-reading roles read as deliberate. *For Kasia:* Sora (headings) + Inter (body) is the correct setup — use Sora boldly at large sizes; do not collapse to one or add a third. [impeccable.style/slop](https://impeccable.style/slop/)
- **8-pt spacing rhythm.** Uniform multiples of 8 read subconsciously as "craft"; 1–2px drifts accumulate into "cheap." *For Kasia:* define spacing tokens in `:root`; round the few odd values (e.g. hero-art margin 38.4px → 40px). [medium.com/built-to-adapt/intro-to-the-8-point-grid-system](https://medium.com/built-to-adapt/intro-to-the-8-point-grid-system-d2573cde8632)
- **Illustration over empty photo slots.** Hand-drawn commodity icons signal species-level expertise and cost zero bytes; gray placeholders signal "unfinished." *For Kasia:* extend the existing green SVG approach — kmín cross-section, peppercorn, coriander cluster, garlic clove at ~80px in brand green. [diasporaco.com/collections/all](https://www.diasporaco.com/collections/all)

### Trust & conversion

- **(P1) Specificity is the whole trust strategy.** Dated, named, countable facts can only be written about Kasia; vague equivalents ("velký sortiment", "roky zkušeností") cost credibility. *For Kasia:* "Přes 369 druhů koření", "od ledna 1993", "export do 6 zemí", "4 provozovny" — replace every abstract claim with a verifiable fact. [everything.design/blog/trust-signals-b2b-website](https://www.everything.design/blog/trust-signals-b2b-website)
- **(P1) Longevity as a datable milestone chain, not a superlative.** "30+ let zkušeností" is indistinguishable from a company that faked its founding date; the milestone chain is the proof. *For Kasia:* 1993 vznik → 1995 česneková pasta Týniště → 1998 míchárna Strančice → 2011 Sezimovo Ústí → gastro směsi Toužim. Four investments across 30 years = "they're not going anywhere." [fuchsgruppe.com/en/about-us](https://fuchsgruppe.com/en/about-us)
- **(P1) Process-chain narrative as the honest substitute for absent certifications.** Describing the steps you control beats a badge wall — and Kasia holds zero ISO/HACCP/BIO. *For Kasia:* přímý dovoz → vstupní kontrola → čištění/třídění/mletí → míchání na míru → mokrá výroba, summarised by the soft, defensible line "dohledatelnost od suroviny po balení." Never escalate to "certifikovaná kvalita." [avo.de/en/company/quality](https://www.avo.de/en/company/quality/)
- **(P1) Real building photos + addresses as primary trust imagery.** B2B buyers ask "does this company actually exist and operate at scale?"; a real provozovna exterior answers it better than any staged shot. *For Kasia:* surface the 4 building photos early (hero/sub-hero), not buried on Kontakt; 3 exec portraits on O nás/Kontakt. [frogspark.co.uk/blog/why-great-photography-is-key-in-b2b-website-design](https://frogspark.co.uk/blog/why-great-photography-is-key-in-b2b-website-design/)
- **(P1) Honest absence over fabricated proof or "coming soon" placeholders.** A gray cert-shield wall or "Přidáme brzy" testimonial does *more* damage than omission — B2B procurement runs due diligence. *For Kasia:* omit certs and testimonials entirely; hide-when-empty (as kontakt.html already does for exec emails). [nngroup.com/articles/empty-state-interface-design](https://www.nngroup.com/articles/empty-state-interface-design/)
- **Hero answers three buyer questions in the first viewport: what / for whom / what next.** ~57% of viewing time is above the fold; trust judged in 3–6s. *For Kasia:* category + buyer angle headline, capability subhead ("369 druhů · přímý dovoz · vlastní zpracování · od 1993"), one primary CTA, one real building photo. [mqlmagnet.com/post/landing-page-best-practices-that-actually-convert](https://www.mqlmagnet.com/post/landing-page-best-practices-that-actually-convert)
- **Subheadline as an ICP/segment filter.** Naming the buyer types reduces wrong-fit bounce and validates right-fit visitors. *For Kasia:* "Pro velkoobchody, gastro provozy, výrobce potravin a uzenin a obchodní řetězce." [lowcode.agency/blog/what-makes-a-high-converting-b2b-website](https://www.lowcode.agency/blog/what-makes-a-high-converting-b2b-website)
- **Proximity principle — proof next to the claim.** B2B buyers evaluate page-by-page; provenance locked on a single Kvalita page is effectively invisible. *For Kasia:* put one line of origin/process context inside each product category block, not only on a quality page. [valmax.agency/insights/best-manufacturing-websites-of-2026](https://valmax.agency/insights/best-manufacturing-websites-of-2026/)
- **No D2C urgency mechanics.** Countdown timers, "limited stock", discount pop-ups erode credibility in a months-long, multi-stakeholder B2B cycle. *For Kasia:* none — the lever is clarity and credibility, not pressure. [unbounce.com/conversion-rate-optimization/b2b-conversion-rates](https://unbounce.com/conversion-rate-optimization/b2b-conversion-rates/)
- **Export reach as a dry, named list.** Six named countries is a credibility-dense one-liner; "international presence" is noise. *For Kasia:* "Vyvážíme do Polska, Slovenska, Ukrajiny, Izraele, Běloruska a Nizozemska" — the IL/BY/NL entries signal real trading relationships. [orkla.cz/en/about-orkla-foods-cesko-a-slovensko](https://www.orkla.cz/en/about-orkla-foods-cesko-a-slovensko)
- **State the B2B-only model as intentional positioning.** A silent gap where a cart/price-list would be reads as incomplete. *For Kasia:* "Dodáváme výhradně velkoobchodně — obraťte se na nás." [vitachem.eu/ingredients](https://www.vitachem.eu/ingredients)

### Accessibility & performance

- **(P1) WCAG 2.2 AA contrast on *every* text token, plus the new 2.2 criteria.** Designers check brand green and stop; muted/secondary tokens are where small text fails. *For Kasia:* `--muted #6b7c75` ≈ 4.41:1 on white fails AA at the .82rem stat-label size → darken to ~`#5c6961`; `--spice #c2581c` ≈ 4.45:1 is borderline as a text color → `#b34e16`. Also: 24×24px min touch targets (SC 2.5.8), focus not obscured by the sticky header (SC 2.4.11, add `scroll-margin-top`), consistent footer contact placement (SC 3.2.6). [webaim.org/resources/contrastchecker](https://webaim.org/resources/contrastchecker/) · [w3.org/WAI/standards-guidelines/wcag/new-in-22](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- **prefers-reduced-motion as opt-in.** Vestibular disorders affect 35%+ of adults over 40. *For Kasia:* move `scroll-behavior: smooth` and the `.btn`/`.card` hover translates inside `@media (prefers-reduced-motion: no-preference)`; never add scroll-reveal fade-ins. [web.dev/articles/prefers-reduced-motion](https://web.dev/articles/prefers-reduced-motion)
- **Skip link + `:focus-visible` ring.** Two non-negotiable keyboard primitives; never `outline:none` without a replacement. *For Kasia:* "Přejít na obsah" as first focusable element, `id="main-content"` on `<main>`, 3px green ring + white offset. [developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible](https://developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible)
- **Never lazy-load the LCP image; system-ui for body; inline the CSS.** Biggest perf wins for a light site. *For Kasia:* hero building photo gets `fetchpriority="high"` and no `loading=lazy`; everything below the fold gets `loading="lazy"`; swap Inter-body for `system-ui` to drop a Google Fonts round-trip (Czech ě/š/č/ř/ž renders fine); load Sora only (Latin-Extended subset, `font-display:swap`, one preload, `size-adjust` fallback). [web.dev/articles/lcp-lazy-loading](https://web.dev/articles/lcp-lazy-loading) · [web.dev/articles/font-best-practices](https://web.dev/articles/font-best-practices)
- **Responsive images for the 7 real photos.** `<picture>` + WebP source + JPEG fallback + `srcset/sizes` + explicit `width`/`height` (prevents CLS). One-time, low-effort task. [web.dev/learn/design/responsive-images](https://web.dev/learn/design/responsive-images)
- **Specific, contextual alt text.** The 4 building + 3 exec photos are meaningful, not decorative. *For Kasia:* e.g. "Provozovna Týniště nad Orlicí, kde v roce 1995 vznikla první česneková pasta"; logo alt = "Kasia vera s.r.o."; decorative SVG gets `alt=""` or lives in CSS background. [wcag.com/blog/good-alt-text-bad-alt-text](https://www.wcag.com/blog/good-alt-text-bad-alt-text-making-your-content-perceivable/)
- **Nav as disclosure widget, no `role="menu"`, no JS framework.** For a flat nav, flex-wrap at intermediate widths + a `<button aria-expanded>` toggle at the narrowest viewport satisfies WCAG and stays inlineable. [adrianroselli.com/2019/06/link-disclosure-widget-navigation.html](https://adrianroselli.com/2019/06/link-disclosure-widget-navigation.html)

### Microcopy

- **(P1) Vykání, lean-formal register, destination-named buttons.** B2B Czech default is vykání; buttons name what happens next. *For Kasia:* keep "Spojte se s námi", "Komu dodáváme"; replace any "Zjistěte více" with the destination ("O nás", "Naše provozovny"); CTA "Poptat sortiment" / "Domluvit schůzku se zástupcem" beats "Kontaktujte nás" because it names the outcome; add "Obvykle odpovídáme do 1–2 pracovních dnů." [nngroup.com/articles/tone-of-voice-dimensions](https://www.nngroup.com/articles/tone-of-voice-dimensions/) · [windmillstrategy.com/five-tips-for-a-high-conversion-cta-on-your-industrial-b2b-website](https://www.windmillstrategy.com/five-tips-for-a-high-conversion-cta-on-your-industrial-b2b-website/)
- **B2B risk-reduction language, not D2C aspiration.** The buyer audits reliability, not novelty. *For Kasia:* "Stejná specifikace, každá dodávka" beats "premium koření pro náročné"; sensory phrasing belongs at segment level ("Výrobci uzenin — od kmínu po majoránku, základ každé klobásy"), not on consumer product cards. [burlapandbarrel.com](https://burlapandbarrel.com)
- **Nielsen H8 minimalism — every section answers one distinct buyer question.** Who are you / what do you make / who buys / how do I reach you. *For Kasia:* actively resist a "Naše hodnoty" four-card block (Kvalita/Spolehlivost/Tradice/Inovace) — the single most common Czech-B2B AI tell, circular and verifiable-content-free. [nngroup.com/articles/ten-usability-heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
- **Nav is a contract — no dead/placeholder links.** A "coming soon" nav item signals an unmaintained operator. *For Kasia:* add Produkty/Sortiment to the nav only when the page ships with real content; footer-only "Přihlášení do skladu" is the right boundary.

---

## 3. Anti-patterns to escape

Matej finds the current site reads "AI-only." These are the specific tells and the honest alternative for each.

| AI-template tell | Honest Kasia alternative |
|---|---|
| Purple-to-blue / mesh gradients on buttons, hero, "orbs" | Flat brand green (`#235c33`), warm spice-orange accent (`#c2581c`) — earned from herbs + ground spice; tints via `--green-soft`, never gradients. [impeccable.style/slop](https://impeccable.style/slop/) |
| Abstract hero: bokeh spice pile, smiling stock chef, 3D blob | A real provozovna exterior, a named year, a named exec. Kasia owns 4 building + 3 portrait photos — use them; keep the hand-authored mortar-and-herbs SVG until a real Petr-supplied photo lands. [cxl.com/blog/stock-photography-vs-real-photos-cant-use](https://cxl.com/blog/stock-photography-vs-real-photos-cant-use/) |
| Three stacked identical 3-col icon-card grids | One earned 6-cell capability grid; every other section a different shape (prose band, checklist, inline rows, dark CTA band). |
| One font flat at every size | Sora (display) + Inter (body), distinct roles, no third face. |
| "Naše hodnoty": Kvalita · Spolehlivost · Tradice · Inovace cards | Demonstrate values through the milestone chain, process narrative, and named facts — never state them as abstract cards. |
| Cert / HACCP / BIO badge wall | Process-chain narrative + soft "dohledatelnost od suroviny po balení". Kasia holds zero certs; fabricating them fails a procurement audit. |
| Testimonial carousel / logo wall / star ratings | Omit entirely. Substitute checkable institutional signals: 4 addresses, 3 named execs, 6 export countries, dated milestones. Fake social proof actively *creates* distrust. [easysocialproof.io/why-fake-social-proof-backfires](https://easysocialproof.io/why-fake-social-proof-backfires-the-research-on-authenticity-and-consumer-trust/) |
| Glassmorphism frosted cards (`backdrop-filter: blur`) | Flat colored cards (`--green-soft` + left-border accent). Wrong register for a 30-year Czech food house and a readability hit. [nngroup.com/articles/glassmorphism](https://www.nngroup.com/articles/glassmorphism/) |
| Emoji bullets (✅ 🌿 🚚) in copy/headings | CSS `::before` checkmarks / inline SVG line-icons. Czech B2B register is terse and professional. [clearb2b.com/news-views/emojisinb2b](https://www.clearb2b.com/news-views/emojisinb2b/) |
| "Empower / transform / seamlessly / passionate about quality" | Dated, named facts that can only describe Kasia. "Přes 369 druhů koření" > "comprehensive spice portfolio". [atomwriter.com/blog/ai-content-homogenization-brand-voice](https://www.atomwriter.com/blog/ai-content-homogenization-brand-voice/) |
| Scroll-reveal fade-in on every section | No scroll animation; gate the few small hover transitions behind reduced-motion. Adds zero info for B2B; risks physical distress. |
| Gray "foto bude doplněno" boxes on the live site | Either commit to hand-authored SVG illustration or to pure typography — never ship a visible gap. (Internal "doplníme" notes stay internal.) |
| "Under construction" / placeholder nav items | Four accurate pages beat twelve with eight placeholders. Nav grows only as real pages ship. |
| E-commerce funnel structure (hero → product grid → "checkout" CTA relabeled "kontakt") | Buyer-checklist section order (Is this for me? → Can they deliver? → Are they credible? → How do I start?). The funnel shape itself is an AI tell. |

---

## 4. Visual point of view

Kasia should feel like **a real, 30-year-old Czech family spice house — concrete, warm, and quietly confident** — not a startup landing page. The emotional register is the one a purchasing manager at a velkoobchod or a šéfkuchař at a gastro provoz trusts on sight: sober, specific, reachable. The site's authority comes not from polish-for-its-own-sake but from physical reality — a building in Týniště that has milled spice since the nineties, a face with a name and a phone number, six countries on an export list. Every design choice should reinforce "we exist, we've been here since 1993, you can come visit us," because that is precisely the question a food-ingredient buyer is asking and precisely what Kasia can answer with the truth.

Warmth comes from provenance, not decoration. The brand green roots the site in the herbs-from-earth story; the spice-orange accent carries the warmth of ground kmín — both earned from the product, neither a SaaS-trend gradient. Imagery is honest and load-bearing: the four building exteriors and three portraits do the trust work, and hand-authored green SVG (commodity icons, the mortar-and-herbs motif) fills the visual space photography can't yet reach. There is breathing room and editorial restraint — large Sora headings, generous whitespace, one precise fact per beat — the same restraint a premium house like La Boîte uses to signal confidence without a single product photo. Crucially, the typography and the named facts carry the premium signal, so the "no stock photography, ever" rule is load-bearing, not cosmetic: a single Unsplash spice market shot would instantly undercut the credibility the specific copy builds.

The tone is sober Czech B2B throughout — vykání, short factual sentences, no superlatives, no enthusiasm-signaling. The site opens conversations (poptávka, a rep meeting, a phone call), it does not close transactions. Where a competitor's template shouts, Kasia states; where a template fabricates a badge, Kasia describes a real process. That discipline — specificity over adjectives, real over staged, honest absence over manufactured completeness — *is* the aesthetic.

---

## 5. Per-page UX blueprint

Seven pages. Note up front: **Kvalita** and **Pro koho** are the two pages most dependent on content we either lack (certs/testimonials) or that overlaps other pages. Both can stand alone *or* fold into Domů/O nás sections — that is a **Checkpoint-C** call, flagged in each subsection.

### Domů (Home)

- **Single job:** in under 5 seconds, answer "is this the right supplier for me?" for a Czech B2B buyer.
- **Section anatomy (in order):** (1) Nav with logo + 4 segment-aware links + visible phone/CTA. (2) Hero — positioning headline (category + buyer angle + "od roku 1993"), subhead naming the four segments, one primary CTA ("Poptat sortiment"), one real building photo. (3) Facts strip — three safe hard numbers: "369 druhů koření · 236 kulinářských produktů · 30+ let na trhu" (CSS grid, auto-wrap, no media query). (4) Co děláme — the earned 6-cell capability grid (process verbs: dovoz, čištění, třídění, mletí, míchání, mokrá výroba). (5) Pro koho — 3–4 inline segment rows (not cards), each one sentence in the buyer's vocabulary. (6) Jak pracujeme / origin — prose band, milestone chain, "dohledatelnost od suroviny po balení", with a building photo. (7) Naše značky — VERA GURMET, VEGA, Zlaté kuře as named examples, large type, no product photos. (8) Export one-liner (6 named countries as green `.badge` pills). (9) Dark-green CTA band — "Spojte se s námi" + phone. (10) Footer (statutory data + sklad login).
- **Key interaction:** scroll; segment rows are anchor links into Pro koho. Hero CTA → Kontakt.
- **Facts / slots:** all safe facts feed this; `hero-photo.jpg` slot stays the SVG until Petr supplies a real image. No "doplníme" visible to users.

### O nás (About)

- **Single job:** establish 30-year institutional credibility and show the real humans behind the brand.
- **Section anatomy:** (1) Positioning headline (not literally "O nás"). (2) Founding narrative anchored to a specific fact (leden 1993). (3) Milestone timeline — CSS-only, real dates only: 1993 → 1995 Týniště → 1998 Strančice → 2011 Sezimovo Ústí → Toužim gastro směsi. (4) Leadership — 3 exec portraits + names + titles. (5) Geographic reach — Czech provozovny + 6 export countries (flag/pill strip). (6) Jak pracujeme — process philosophy in plain language (no invented "values"). (7) Obchodní zástupci note. (8) CTA to Kontakt.
- **Key interaction:** timeline scroll (CSS transform/scroll, zero JS).
- **Facts / slots:** milestones, portraits, export list — all real. No values paragraph, no CSR statement, no fabricated quotes.

### Produkty (Catalogue showcase)

- **Single job:** convey breadth and invite enquiry — **not** simulate an e-shop. Metric is enquiry, not add-to-cart.
- **Section anatomy:** (1) Category nav — anchor links / CSS `:target`, no JS. (2) Intro — breadth claim ("369 druhů koření, 236 kulinářských produktů") + honest note this is an overview, not a full list. (3) 4–5 capability clusters in buyer-volume order: celé/drcené koření (přímý dovoz — kmín, pepř, koriandr) · mleté/standardizované (vlastní mlýny) · kořenicí směsi a gastro receptury (Strančice/Toužim) · mokrá výroba (pasty, sójová omáčka, tekuté polévkové koření, marinády) · sušený česnek/cibule/majoránka (silná pozice). (4) Per cluster: name + 2–3 sentences + flagship commodity exemplars + one line of provenance/process context (proximity principle) + "Vyžádat specifikaci" CTA. (5) VERA GURMET brand callout. (6) "Nenašli jste?" fallback CTA.
- **Key interaction:** category anchor navigation.
- **Facts / slots:** named commodities and wet-production items are all safe. **No SKU grid, no pack sizes, no prices (not even "cena na vyžádání" columns).** Photo slots → hand-authored SVG commodity icons, never stock spice imagery. Nav adds "Produkty" only when this page ships with real content.

### Kvalita (Quality / trust) — *slot-dependent; Checkpoint-C fold candidate*

- **Single job:** give a food-safety/QA buyer enough factual confidence to enquire — without any claim that could blow up in due diligence.
- **Section anatomy:** (1) Responsibility/ethos statement ("Naše koření vstupuje do vašich výrobků a na stoly vašich hostů…"), not a compliance claim. (2) Process chain — 5–6 box CSS flex strip with SVG icons (dovoz → vstupní kontrola → zpracování → míchárna → mokrá výroba → distribuce). (3) Provenance — named commodities + honest origin framing. (4) Export-as-proof line (náročné trhy). (5) **Certification slot — OMITTED entirely** (zero certs exist); add only when a cert genuinely exists. (6) "Technické dotazy" CTA.
- **Key interaction:** process infographic (CSS only).
- **Facts / slots:** soft "dohledatelnost od suroviny po balení" only — never "certifikovaná sledovatelnost", never ISO/HACCP/BIO badges. **Flag:** because its strongest would-be element (certs) is empty, Kvalita may not warrant a standalone page — its process chain is arguably stronger living as the "Jak pracujeme" section on Domů + O nás. Checkpoint-C decides standalone vs. fold.

### Pro koho (Audience / segments) — *overlap-dependent; Checkpoint-C fold candidate*

- **Single job:** make each buyer type read their panel and think "they understand my situation."
- **Section anatomy:** (1) Headline naming the segments explicitly. (2) One anchor-linked panel per real segment, in revenue priority: Gastro provozy · Výrobci uzenin · Výrobci potravin · Velkoobchody a obchodní řetězce (+ optionally obchodní řetězce / private-label *only if true*). (3) Per panel: segment name (large) → one-sentence pain-point recognition → how Kasia fits (real product categories) → relevant product families → "Kontaktujte obchodního zástupce" CTA. (4) "Nejste si jistí?" catch-all.
- **Key interaction:** segment self-selection via anchor / CSS `:target`.
- **Facts / slots:** segment-relevant facts are safe (kmín/majoránka for uzeniny; mokrá výroba for výrobci; VERA GURMET shelf-ready for velkoobchod). **Name no clients** — no "naši zákazníci" logo/quote block (we have none). **Flag:** this content overlaps the Domů "Pro koho" rows; a standalone page is justified only if each panel carries genuinely distinct, segment-specific depth. Otherwise fold into the homepage rows. Checkpoint-C call.

### Provozovny (Locations)

- **Single job:** answer "how do I get there, and which site do I contact?"
- **Section anatomy:** (1) Intro — "Čtyři provozovny, síť obchodních zástupců po celé ČR." (2) Overview — hand-authored inline SVG CZ map with 4 dots, *or* a 2×2 card grid. (3) Per-location block ×4: name + street address + site function (výroba/sklad/zastoupení) + the real building photo + phone + hours (or "Otevírací dobu sdělíme na vyžádání" if unknown — never invented) + standard Google Maps `iframe` + "Naplánovat cestu" plain `href`. (4) Obchodní zástupci note. (5) Footer with IČO/DIČ.
- **Key interaction:** standard map iframe (no JS map library); "Naplánovat cestu" opens Maps in a new tab.
- **Facts / slots:** 4 real building photos + addresses + milestone years per site. First photo eager-loads; rest `loading="lazy"`.

### Kontakt

- **Single job:** route the right enquiry to the right human with zero friction — info-only, no form.
- **Section anatomy:** (1) Headline naming intent ("Spojte se s námi"). (2) Department-segmented directory: Obchodní oddělení → Technické dotazy → Vedení — each with `tel:` click-to-call, `mailto:`, and named contact where a portrait exists. (3) Response expectation ("Obvykle odpovídáme do 1–2 pracovních dnů"). (4) Statutory block — Kasia vera s.r.o. · IČO · DIČ · sídlo (procurement needs this for vendor setup). (5) Locations reference linking back to Provozovny.
- **Key interaction:** click-to-call on mobile, `mailto:` on desktop. No contact form, no live chat.
- **Facts / slots:** 3 exec portraits + names/titles in Vedení; central obchodní phone/email (no personal rep mobiles without consent); IČO/DIČ are public. Continue the existing hide-when-empty discipline for any missing field.

---

## 6. Named design directions

Four candidate directions for Checkpoint A. **The current 0054 look — centered/curvy/green, Sora + Inter — is one candidate (closest to "Warm provenance editorial"), not the default.** All must honor the light-stack constraint (inline CSS, hand-authored CSS/SVG, system/Google fonts only, no JS framework) and the no-fabrication rule.

### A. Warm provenance editorial *(closest to current 0054)*

- **Intent:** A 30-year family spice house told as an editorial story — provenance-led, milestone-anchored, generous whitespace, each section its own shape. Confidence through restraint.
- **POV:** Palette — forest green `#235c33` + warm spice-orange `#c2581c` + cream/`--green-soft` bands; rounded cards (18px) / pill badges. Type — Sora display + Inter (or system-ui) body, large headings, lots of air. Imagery — real building photos + 3 portraits + hand-authored green SVG commodity icons; mortar-and-herbs motif. Motion — none beyond tiny reduced-motion-gated hovers.
- **Why it fits Kasia:** Directly dramatizes the honest assets (history, provenance, real places) and reads warm and human — exactly the family-house register. Lowest-risk evolution of what exists.

### B. Clean technical B2B

- **Intent:** Sober, document-like, procurement-trusted — the register of AVO/Fuchs/Kotányi. The site as a precise spec sheet for a supply relationship.
- **POV:** Palette — green as a restrained accent on white/light-gray; sharper radii (4–8px), thin rules. Type — tighter scale, possibly IBM Plex Mono for facts/numerals echoing the sklad side; smaller headings, denser fact strips. Imagery — building photos framed plainly, process-chain diagrams in flat SVG, minimal illustration. Motion — effectively none.
- **Why it fits Kasia:** Speaks the literal language of a food-technologist / nákupní ředitel; the process-chain and facts strips become the centerpiece. Best if the audience skews industrial (výrobci uzenin/potravin) over gastro.

### C. Bold modern grocer

- **Intent:** Confident, contemporary food brand — large type, strong green blocks, commodity SVG illustration as hero. Premium-house restraint (La Boîte / Diaspora) without any consumer-shop machinery.
- **POV:** Palette — deeper greens with the spice-orange used assertively as a block/accent color; high contrast. Type — oversized Sora display, dramatic scale jumps (within 3 tiers). Imagery — large hand-authored commodity-illustration panels carry sections where photography is absent; building photos as full-width bands. Motion — none / reduced-motion-gated only.
- **Why it fits Kasia:** Turns the photography gap into a strength — illustration *is* the look — and signals a brand proud of its product. Risk: must stay sober enough to read B2B, not D2C; the no-urgency / no-cart discipline is essential here.

### D. Dark premium

- **Intent:** Quiet authority on a dark ground — spice warmth glowing against deep green-black. Heritage-premium, gallery-like.
- **POV:** Palette — near-black/deep-green base, cream text, spice-orange as the single warm accent (contrast-checked carefully against the dark ground for AA). Type — Sora display in light/cream, restrained. Imagery — building photos and portraits gain drama against dark; SVG icons in warm line-work. Motion — none.
- **Why it fits Kasia:** Maximal "premium without superlatives" feel and makes the limited real photos look intentional and curated. Caveats: dark-ground contrast must be verified for every text token (the existing `--muted`/`--spice` failures are *more* acute on dark); risks reading as "tech/luxury startup" rather than "working Czech spice house" — the highest-risk direction against the honest-family-house brief.

---

## 7. Sources

- https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://www.nngroup.com/articles/empty-state-interface-design/
- https://www.nngroup.com/articles/b2b-vs-b2c/
- https://www.nngroup.com/articles/tone-of-voice-dimensions/
- https://www.nngroup.com/articles/contact-us-pages/
- https://www.nngroup.com/articles/glassmorphism/
- https://www.nngroup.com/reports/ecommerce-ux-trust-and-credibility/
- https://www.nngroup.com/articles/ecommerce-homepages-listing-pages/
- https://www.smashingmagazine.com/2022/10/typographic-hierarchies/
- https://www.smashingmagazine.com/2021/10/respecting-users-motion-preferences/
- https://www.smashingmagazine.com/2024/06/how-improve-microcopy-ux-writing-tips-non-ux-writers/
- https://www.smashingmagazine.com/2022/11/navigation-design-mobile-ux/
- https://medium.com/built-to-adapt/intro-to-the-8-point-grid-system-d2573cde8632
- https://web.dev/articles/color-and-contrast-accessibility
- https://web.dev/articles/prefers-reduced-motion
- https://web.dev/articles/font-best-practices
- https://web.dev/articles/preload-optional-fonts
- https://web.dev/articles/lcp-lazy-loading
- https://web.dev/articles/optimize-lcp
- https://web.dev/learn/performance/lazy-load-images-and-iframe-elements
- https://web.dev/learn/design/responsive-images
- https://web.dev/articles/responsive-web-design-basics
- https://web.dev/learn/accessibility/focus
- https://webaim.org/articles/contrast/
- https://webaim.org/resources/contrastchecker/
- https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum
- https://developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Understanding_WCAG/Perceivable/Color_contrast
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/menu_role
- https://developer.mozilla.org/en-US/blog/fix-image-lcp/
- https://adrianroselli.com/2019/06/link-disclosure-widget-navigation.html
- https://www.wcag.com/blog/good-alt-text-bad-alt-text-making-your-content-perceivable/
- https://css-tricks.com/responsive-layouts-fewer-media-queries/
- https://fontfyi.com/blog/font-display-strategies/
- https://www.mqlmagnet.com/post/landing-page-best-practices-that-actually-convert
- https://www.goprimer.com/blog/the-winning-hero-section-formula
- https://unbounce.com/conversion-rate-optimization/b2b-conversion-rates/
- https://www.lowcode.agency/blog/what-makes-a-high-converting-b2b-website
- https://www.everything.design/blog/trust-signals-b2b-website
- https://blueprintdigital.com/blog/b2b-marketing-food-industry-guide/
- https://frogspark.co.uk/blog/why-great-photography-is-key-in-b2b-website-design/
- https://closo.co/blogs/blog/how-to-source-people-photos-4885
- https://foxecom.com/blogs/all/b2b-vs-d2c
- https://www.windmillstrategy.com/five-tips-for-a-high-conversion-cta-on-your-industrial-b2b-website/
- https://grow-conversions.com/blog/b2b-conversion-rate-optimization/
- https://beetlebeetle.com/post/b2b-website-design-guide-structure-content-best-practices
- https://valmax.agency/insights/best-manufacturing-websites-of-2026/
- https://tendocom.com/thought-leadership/how-to-write-an-engaging-b2b-about-us-page-with-8-examples/
- https://www.webstacks.com/blog/about-us-page
- https://clutch.co/resources/8-pillars-trust-examples-b2b-credibility
- https://www.itac-professional.com/en/blog/suppliers-food-traceability-process/
- https://genixdigital.com/blog/ui-ux-for-b2b-businesses-page-patterns/
- https://elevationb2b.com/blog/7-best-practices-for-b2b-ux-website-design-why-its-different-from-b2c/
- https://localu.org/designing-business-location-website-pages-part-2-multiple-location-business/
- https://contentamigo.com/articles/location-page-examples-best-practices-must-have-elements/
- https://www.blendb2b.com/blog/contact-page-design
- https://www.diasporaco.com/collections/all
- https://burlapandbarrel.com / https://burlapandbarrel.com/products/royal-cinnamon / https://burlapandbarrel.com/collections/all
- https://laboiteny.com/collections
- https://www.frontiercoop.com
- https://www.doehler.com/en/
- https://www.avo.de/en/ / https://www.avo.de/en/company/portrait/ / https://www.avo.de/en/company/quality/
- https://www.wiberg.eu/
- https://www.kotanyi.com/en/company/ / https://www.kotanyi.com/en/sustainability/ / https://www.kotanyi.com/en/b2b/
- https://fuchsgruppe.com/en/about-us / https://fuchsgruppe.com/en/about-us/quality/
- https://fuchsfoodsolutions.com/en/
- https://www.korenicko.cz/
- https://www.viatrading.cz/en/
- https://www.exver.cz/
- https://www.vitachem.eu/ingredients / https://www.vitachem.eu/who-we-are
- https://www.orkla.cz/en/about-orkla-foods-cesko-a-slovensko
- https://en.bidfood.cz/
- https://www.griffithfoods.com/
- https://impeccable.style/slop/
- https://shuffle.dev/blog/2026/01/why-do-most-ai-generated-websites-look-the-same/
- https://axe-web.com/insights/ai-website-design-sameness/
- https://cxl.com/blog/stock-photography-vs-real-photos-cant-use/
- https://tailorededgemarketing.com/why-stock-photos-can-destroy-credibility/
- https://www.mattrobertsphoto.com/blog/authentic-vs-stock-photos/
- https://www.fontspring.com/trends
- https://elements.envato.com/learn/font-trends
- https://www.axongarside.com/blog/b2b-website-design-trends-2026
- https://www.beachmarketing.co.uk/b2b-design-trends-for-2026/
- https://www.atomwriter.com/blog/ai-content-homogenization-brand-voice/
- https://translated.com/resources/food-provenance-translation-authentic-origin-stories
- https://easysocialproof.io/why-fake-social-proof-backfires-the-research-on-authenticity-and-consumer-trust/
- https://www.wisecoda.com/blog/social-proof-testimonials-credibility-conversion-optimization
- https://medium.com/marketing-rewired/social-proof-in-2025-its-not-just-testimonials-anymore-715f315bc238
- https://medium.com/design-bootcamp/glassmorphism-the-most-beautiful-trap-in-modern-ui-design-a472818a7c0a
- https://www.emlen.io/blog/top-tips-for-using-emojis
- https://www.clearb2b.com/news-views/emojisinb2b/
- https://www.newbreedrevenue.com/blog/emojis-in-b2b-marketing
- https://foodindustryexecutive.com/2025/02/biting-into-branding-food-industry-design-trends-for-2025-according-to-experts/
- https://www.emerald.com/insight/content/doi/10.1108/ccij-12-2021-0136/full/html