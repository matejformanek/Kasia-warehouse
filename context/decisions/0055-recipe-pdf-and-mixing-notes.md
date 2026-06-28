# 0055 — Recipe PDF export + surface mixing notes on product detail

- **Date:** 2026-06-29
- **By:** Matej (owner stand-in), implemented by agent

## Context

The mixture (*směs*) product-detail screen showed only the recipe ratios plus a
client-side "Spočítat dávku" scaler. Two gaps surfaced on Matej's walkthrough:

1. The free-form **mixing notes** Petr keeps in the recipe XLS (packing size,
   mixing time, etc. — captured on import per [`0048`](./0048-xls-recipe-importer.md)
   into `Product.notes`) were buried in the stock card and not presented as part
   of the recipe. They are "additional info to the mixing we need."
2. There was **no way to print/share a recipe** — operators wanted a clean
   downloadable recipe sheet.

(The scaler inputs also weren't inside a `<form>`, so they missed the themed
field styling — fixed as a cosmetic bug, not a decision.)

## Options considered

- **A model field for procedure/notes** — rejected: `Product.notes` already holds
  exactly this text from the XLS import; no schema change needed.
- **A new PDF document type rendered with WeasyPrint** vs. a print-CSS HTML view —
  chose WeasyPrint, reusing the dodák PDF infrastructure
  ([`0017`](./0017-pdf-weasyprint.md)): same renderer, same logo-fallback path,
  one new template + view + route. No new dependency.

## Choice

1. **Surface `Product.notes` as "Poznámky k míchání"** inside the Receptura card
   on the mixture product-detail page (and stop double-showing it in the stock
   card for mixtures). Add a "Zahájit míchání →" link to the real mixing-job flow
   so the recipe view has an actionable next step.
2. **Add a recipe PDF**: `render_recipe_pdf(product)` in `services.py` →
   `inventory/recipe_pdf.html` (A4, ingredient table with podíl / % / per-100 kg,
   plus the mixing notes), served by `recipe_pdf` view at
   `/sklad/katalog/<pk>/receptura/pdf/`. 404 for non-mixtures / recipe-less
   mixtures.

No new model, no migration, no new dependency. Reuses WeasyPrint + the bundled
logo fallback.

## Rationale

The data already exists (`Product.notes`); the work is presentation + a printable
document. Reusing the dodák PDF stack keeps it right-sized — one renderer, one
template — rather than introducing a reporting layer. A recipe is an internal
document, so the PDF carries an "Interní receptura" footer, not customer framing.

## Consequences

- The mixture detail page now shows recipe + mixing notes + "Stáhnout recepturu
  (PDF)" + "Zahájit míchání →".
- `Product.notes` is now load-bearing for mixtures as the canonical mixing-notes
  field. The XLS importer already populates it; manual edits via product edit
  feed the same surface and the PDF.
- A second WeasyPrint document exists; any future shared PDF chrome (header/logo)
  could be factored out, but two documents don't yet justify it
  ([right-sized](../../.claude/rules/right-sized-for-small-business.md)).
