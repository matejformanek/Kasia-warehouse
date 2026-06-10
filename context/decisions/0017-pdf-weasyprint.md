# 0017 — PDF library: WeasyPrint 69

## Context

R5 in [`../tech-options.md`](../tech-options.md) demands
deterministic, typography-faithful PDF generation of dodací listy with
Czech diacritics, A4 portrait, repeating header on continuation
pages, page N/M footer. The structural rules are locked in
[`../screens/14-nastaveni.md`](../screens/14-nastaveni.md) § PDF
šablona.

WeasyPrint renders HTML+CSS to PDF deterministically. CSS Paged
Media gives `@page` rules for headers/footers and N/M page counters.
Python-native (no Chromium dependency), so the container stays small.

WeasyPrint 69 (current major as of mid-2026) depends only on the
**Pango** stack (`libpango-1.0-0`, `libpangoft2-1.0-0`,
`libharfbuzz-subset0`) plus a font with full Czech-diacritic coverage
(`fonts-dejavu-core` ships free, embeddable, with diacritics intact).
**Cairo is no longer a runtime dependency** — older tutorials say
otherwise; ignore them.

## Options considered

- **WeasyPrint 69.** Native Python; CSS-driven layout; deterministic
  output; Czech diacritics flawless with DejaVu or any embedded
  TrueType.
- **ReportLab.** Lower-level (canvas + flowables). Faster, but
  layout work is bespoke Python rather than CSS. A4 with
  continuation header + N/M footer is more code than CSS @page.
- **wkhtmltopdf.** Bundles WebKit; deprecated upstream; binary
  drift; output less faithful for Czech typography.
- **Headless Chromium (Puppeteer / Playwright print-to-PDF).**
  Hundreds of MB of Chromium in the container, slow startup,
  non-deterministic between Chromium releases. Wrong shape for a
  6-user warehouse tool.
- **Server-side LaTeX.** Excellent typography but the
  toolchain footprint is enormous and the dev-experience for line
  table + conditional šarže column is heavy.

## Choice

**WeasyPrint 69** (`weasyprint==69.*`). Templates live as Django
HTML templates rendering CSS Paged Media. Runtime container
installs:

```
libpango-1.0-0  libpangoft2-1.0-0  libharfbuzz-subset0  fonts-dejavu-core
```

No Cairo. No Chromium. Embedded font is DejaVu Sans family as the
sans-serif default ratified on 2026-06-03 (see
[`../state.md`](../state.md) entry).

## Rationale

- CSS Paged Media @page rules render the continuation-header + N/M
  footer requirement directly.
- DejaVu Sans has complete Czech diacritic coverage and is
  free for commercial embedding.
- The container stays small (~180–220 MB compressed per
  [`0022`](./0022-container-image.md)); no Chromium.
- WeasyPrint is the mainstream Python pick; CZ Django developers
  taking over in 2028 will not be surprised.

## Date & by-whom

2026-06-08 — Matej.

## Consequences — things this now blocks or unblocks

**Unblocks:**

- [`0022`](./0022-container-image.md) — runtime stage in the
  Dockerfile installs the Pango runtime deps + DejaVu fonts.
- The dodací list PDF generation pipeline can be implemented in the
  first models+views pass (next pass).

**Forecloses (without follow-on decision):**

- Chromium-based PDF rendering.
- Pure-Python ReportLab layout work.

**Satisfies (from [`../tech-options.md`](../tech-options.md)):**

- R1 (Czech UTF-8 in PDFs), R5 (deterministic A4 layout with
  continuation pages and N/M footer).

**Makes implementable (0001–0013):**

- [`0007`](./0007-auto-reissue-corrected-dodaky.md) auto-reissue —
  the PDF re-render call is one `HTML(...).write_pdf(...)`.
- [`0010`](./0010-prices-on-dodaci-list.md) no-prices template —
  the line table CSS variant.
- [`0008`](./0008-dodaci-list-numbering.md) číslo formatting — Czech
  formatting is built into Django's templating.
