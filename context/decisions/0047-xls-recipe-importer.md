# 0047 — XLS recipe importer

**Date:** 2026-06-24
**Decider:** Matej (2026-06-24, post-prod-bootstrap session — request
placed alongside "three real users on prod" pass)
**Status:** Accepted

## Context

Per [`0032`](./0032-mixing-in-mvp.md), MVP ships with ~25 míchané
směsi (mixed spice blends). Each mixture has a recipe stored as a
`Product` (kind=MIXTURE) plus a row of `RecipeComponent` per
ingredient with a `ratio` (Decimal, 6dp, 0<r≤1, must sum to ≤ 1.0).

Today the only way to create a mixture is `/katalog/novy/` → fill in
mixture name → switch to the recipe editor → manually type each
ingredient name + ratio. With ~25 mixtures, this is a day of typing,
and re-typing every time Petr tweaks a recipe.

Petr already keeps the recipes as Excel files. Sample:

```
Row 0: ('toužimský knedlík', '', '', '')
Row 1: ('druh suroviny', 'množství kg', '', 'přidáno')
Rows 2+: ingredients in kg
Row N: ('CELKEM', 800.8, 'KG', '')
Rows N+: free-form Czech notes (BALIT Á 5 KG, doba míchání, …)
```

Petr's source files are BIFF8 `.xls` (Excel 2003 format). Future
files may be `.xlsx` if he upgrades.

## Options considered

- **A — Stay manual.** Reject: ~25 recipes × ~6 ingredients × periodic
  re-edits = real cost. The XLS source already exists; we're paying
  for ignoring it.
- **B — CLI management command (`uv run manage.py import_recipe …`).**
  Reject: requires Matej as middle-man for every recipe; doesn't fit
  the operator-CRUD tiering of
  [`0040`](./0040-operator-crud-tiering.md). Vlastník (Karolína /
  Petr) should be able to import recipes herself.
- **C — Direct one-step upload-and-commit.** Reject: no review step
  means typos in the XLS (KRUPIČKA vs Krupička) become real catalogue
  rows; ratio drift from rounding is invisible. Petr's recipes are
  hand-edited Excel — they will have surprises.
- **D — Two-step `/katalog/import-xls/` upload → review (editable) →
  confirm flow, vlastník-only, auto-drafts raw-spice Products for
  unmatched names, atomic commit.** **Chosen.** Operator sees the
  parsed shape before anything lands; can fix names; can delete rows;
  ratio normalization explained on-page; one transaction so a failed
  confirm leaves no half-imported state.

## Choice

**Implement option D.**

### URL routes

- `GET /katalog/import-xls/` — upload form
- `POST /katalog/import-xls/` — parse + render review page
- `POST /katalog/import-xls/potvrdit/` — validate review + atomically
  commit the mixture + components + any new raw-spice products

All three vlastník-only via the existing `_require_vlastnik(request)`
helper in `inventory/views.py`.

### Parser

New `parse_recipe_xls(file_obj, filename)` in `inventory/services.py`,
returning a `ParsedRecipe` dataclass:

- Dispatch by extension: `.xls` → `xlrd.open_workbook(file_contents=…)`;
  `.xlsx` → `openpyxl.load_workbook(file_obj, data_only=True,
  read_only=True)`. **In-memory invocation only** (no filesystem path)
  — the file is a Django `UploadedFile`, not on disk.
- Mixture name = `cell(0, 0)`, stripped, Title Case.
- Ingredient rows = non-empty rows between row 1 (header) and the
  `CELKEM` row where col 0 is text and col 1 is a positive number.
  Names get Title Case (`"KRUPIČKA"` → `"Krupička"`).
- Total kg = `CELKEM`'s col 1 if present, else `sum(qty_kg)` plus a
  warning in `parsed.warnings`.
- Notes = every non-empty col 0 text after `CELKEM`, joined with
  newlines → goes into `Product.notes`.
- Ratio = `qty_kg / total_kg` quantized to 6 dp (`ROUND_HALF_UP`),
  largest ratio absorbs the rounding drift so the sum is exactly
  `Decimal("1.000000")`.
- **Zero-ratio rejection.** If any ratio quantizes to 0 (edge case:
  0.0001 kg ingredient in 1000 kg total), raise `ValidationError`
  with Czech message naming the offending ingredient. Avoids hitting
  the model's `ratio > 0` constraint at commit time.

### Service

`create_mixture_from_review(*, header_data, line_data, user)` in
`inventory/services.py`, wrapped in `transaction.atomic()`:

1. Refuse if `header_data["name_cs"]` matches an existing active
   `Product` (`iexact`) — Czech `ValidationError`.
2. Pre-fetch all active `RAW_SPICE` products in one query; dedupe
   via `.casefold()` so "KRUPIČKA" / "Krupička" / "krupička" all
   resolve to the same row.
3. For each line: if `existing_product_id` set, reuse; else
   `get_or_create(name_cs=…, kind=RAW_SPICE)`.
4. Create mixture Product (kind=MIXTURE, notes from header).
5. Recompute ratios from edited quantities; normalize the max so
   sum == `Decimal("1.000000")`; re-check zero-ratio.
6. For each component: build `RecipeComponent(…)`, call
   `.full_clean()` to enforce the model invariants (no
   self-reference, parent must be mixture), then `.save()`.
   `bulk_create()` would bypass `clean()` — don't use it.

### Forms

- `XLSImportUploadForm` — single FileField, accepts `.xls`+`.xlsx`.
- `XLSImportReviewHeaderForm` — `name_cs`, `notes`, readonly
  `total_kg`.
- `XLSImportReviewLineForm` — `name_cs`, `qty_kg`,
  `existing_product_id` (hidden); used with `formset_factory(
  extra=0, can_delete=True)`.

### Catalogue button

`{% if user.is_vlastnik %}` block on `catalogue_index.html`, sits
next to the existing "+ Nový produkt" button.

### Dependencies

- `openpyxl` — `.xlsx` reader, pure-Python.
- `xlrd` 2.x — legacy `.xls` reader, pure-Python. xlrd 2.x removes
  `.xlsx` support but still reads BIFF8 `.xls` (which is what Petr's
  files are).

Both pure-Python — Dockerfile needs no extra apt packages on the
`python:3.14-slim-trixie` runtime stage.

## Rationale

The review step is doing the load-bearing work: it's where the
operator sees the parser's interpretation before it lands, can fix
spelling for new raw-spice ingredients, and can delete spurious rows.
Without it, Petr's hand-edited Excel typos would land as catalogue
rows requiring cleanup; we'd be saving manual entry but creating
manual cleanup. With it, the import flow stays operator-driven and
the catalogue stays clean.

`transaction.atomic()` + pre-fetch closes the case-insensitivity
race (two operators importing the same new ingredient simultaneously).
At 6 users the race is theoretical, but the cost of correctness is a
single decorator and one extra query.

Picking the largest ratio for normalization (tiebreak: first equal
one wins) absorbs the rounding drift in one place rather than
spreading it. Documented in the parser docstring.

## Consequences

**Now:**
- New decision file (this one).
- New screen design doc `context/screens/17-xls-import.md`.
- New code: parser + service in `inventory/services.py`; 4 forms
  + 1 formset in `inventory/forms.py`; 2 views in
  `inventory/views.py`; 2 routes in `inventory/urls.py`; 2
  templates under `inventory/`; CSS update + nav link in
  `base.html`; catalogue button update.
- New deps in `pyproject.toml` + `uv.lock`: `openpyxl`, `xlrd`.
- New fixture `inventory/tests/fixtures/touzimsky.xls` (Petr's real
  recipe, ~33 KB).
- ~13 new tests.

**Blocks / unblocks:**
- Unblocks Karolína / Petr loading the existing ~25 recipes
  themselves during the shadow run
  ([0034](./0034-shadow-run-before-go-live.md)).
- Unblocks future iteration where Petr edits the XLS source and
  re-imports as part of his recipe-tweak workflow (out of scope:
  diff-vs-existing UI; current behavior refuses duplicate name).

**Future considerations (deferred):**
- Diff-and-replace flow when re-importing an existing mixture.
  Today: must delete the existing one first.
- Bulk upload (folder of XLS files). Add a management command if
  Petr ever asks.
- Pack-size extraction from notes ("BALIT Á 5 KG") into a
  structured field — only if pack-size ever needs to be queried.
- CSV variant — if a customer ever sends one.

## Cross-references

- [`0032-mixing-in-mvp.md`](./0032-mixing-in-mvp.md) — why ~25
  mixtures matter in MVP
- [`0039-mixing-job-shape.md`](./0039-mixing-job-shape.md) —
  RecipeComponent + ratio model
- [`0040-operator-crud-tiering.md`](./0040-operator-crud-tiering.md)
  — vlastník-only operator UI tier
- [`0034-shadow-run-before-go-live.md`](./0034-shadow-run-before-go-live.md)
  — context for "Karolína loads recipes herself"
- [`right-sized-for-small-business.md`](../../.claude/rules/right-sized-for-small-business.md)
  — single-app, one DB, no separate import service
