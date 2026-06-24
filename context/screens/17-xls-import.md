# Import receptury z XLS / XLS recipe importer

## Purpose
Petr keeps mixture (směs) recipes as Excel files; transcribing each
recipe into the catalogue by hand takes a day for the MVP-scope ~25
směsi and re-burns whenever Petr tweaks a recipe. This screen lets
the vlastník upload one XLS file, review the parsed result (name,
ingredients, quantities, ratios, notes), and commit it as a new
mixture Product plus its RecipeComponent rows in one atomic action.
Per decision [`0047`](../decisions/0047-xls-recipe-importer.md).

## Who uses it
Vlastník (Petr / Karolína) on desktop. Used at MVP load-time
(initial recipe import) and occasionally afterwards when Petr edits
a recipe. Obsluha does not see this screen — the catalogue's
"Importovat z XLS" button is gated `{% if user.is_vlastnik %}`.

## What it shows

**Step 1 — Upload (`GET /katalog/import-xls/`):**
- Help paragraph explaining the expected XLS shape (name in row 0,
  ingredients with kg, CELKEM row, optional notes).
- File picker (`.xls` / `.xlsx`, max 2,5 MB).
- "Načíst soubor" submit + "Zrušit" link back to `/katalog/`.

**Step 2 — Review (`POST /katalog/import-xls/`):**
- Warnings banner (yellow) if the parser added any (e.g. CELKEM row
  missing → fell back to sum).
- Card "Směs": editable `name_cs` (pre-filled, Title-Cased), readonly
  `total_kg` (from CELKEM), editable `notes` (post-CELKEM rows
  joined with newlines).
- Card "Suroviny": one row per ingredient with editable `name_cs`,
  editable `qty_kg`, "Stav v katalogu" badge (`v katalogu` /
  `+ nová surovina`) and a "× Smazat" toggle (formset DELETE).
- "Vytvořit směs" primary submit + "Zrušit" link back to `/katalog/`.

## What you can do here

- **Upload an XLS recipe** → see the parsed shape on the review page.
- **Edit ingredient names** before commit (e.g. "Vločky Pf 51" →
  "Vločky PF 51", "Krupička" → "Krupička pšeničná").
- **Edit ingredient quantities** — re-computes ratios on confirm.
- **Delete ingredient rows** that shouldn't be in the recipe.
- **Edit the mixture name** before commit.
- **Edit the notes** before commit.
- **Confirm** → atomic write of the mixture Product + N
  RecipeComponent rows + auto-created raw-spice Products for any
  unmatched ingredient name. Redirects to the mixture's product
  detail.
- **Cancel** → return to `/katalog/` without saving anything.

## What it links to / from

- Reached from: `/katalog/` "Importovat z XLS" button (vlastník-only).
- Goes to: `/katalog/<pk>/` (the newly created mixture's detail
  page) on successful confirm.

## Business rules & validation

- **Vlastník-only.** Obsluha gets 403 via `_require_vlastnik`.
- **File format:** `.xls` (BIFF8, parsed by xlrd) or `.xlsx` (parsed
  by openpyxl). Max 2,5 MB.
- **Required XLS shape:** row 0 col 0 = mixture name (non-empty);
  rows 2+ until CELKEM = ingredient rows with `name` (col 0) +
  `qty_kg > 0` (col 1).
- **Title Case** is applied to the mixture name + every ingredient
  name on parse. Operator can edit anything on the review page.
- **Ratios:** computed as `qty / sum(qty)`, quantised to 6 dp;
  the largest ratio absorbs rounding drift so the sum is exactly
  `Decimal("1.000000")`. Re-computed on confirm from the (possibly
  edited) quantities — the parsed ratios are display-only.
- **Zero-ratio guard:** if any ingredient is so small its ratio
  quantises to 0 (e.g. 0.001 kg in a 10 000 kg total), the confirm
  refuses with a Czech message naming the offending ingredient.
- **Duplicate mixture name** (case-insensitive) → confirm refuses
  with "Směs s názvem „X" už v katalogu existuje."
- **Unmatched ingredient names** auto-create a RAW_SPICE Product
  with the operator-edited name. The match is case-insensitive via
  `.casefold()` so "KRUPIČKA" / "Krupička" / "krupička" all reuse
  the same row.
- **Atomic transaction.** Any failure during commit (validation,
  unique-constraint race, full_clean rejection) rolls back every
  write — no half-imported state.

## States

- **Empty (GET upload):** empty file picker.
- **Parse error:** upload form re-rendered with Czech error on the
  file field ("Soubor je prázdný.", "Soubor neobsahuje název směsi
  v prvním řádku.", "Receptura je prázdná — žádné suroviny.",
  "Soubor nelze přečíst — očekáván formát .xls nebo .xlsx.").
- **Review (POST upload OK):** review page with warnings banner if
  any, header + line formset pre-filled.
- **Confirm validation error:** review page re-rendered with field
  errors + non-form errors (Czech).
- **Confirm OK:** redirect to `/katalog/<pk>/` + Czech success
  flash "Směs „X" vytvořena včetně receptury."

## What this screen explicitly does NOT do

- **No diff-and-replace.** Re-importing the same recipe is refused
  with the duplicate-name error; operator must archive the old
  mixture first (or use the existing edit flow at
  `/katalog/<pk>/upravit/`).
- **No bulk upload.** One file at a time. Add a management
  command if Petr ever asks.
- **No pack-size extraction.** "BALIT Á 5 KG" goes into the notes
  field verbatim; not parsed as a structured field.
- **No CSV.** XLS only.
- **No reservations / stock impact.** Mixture rows are catalogue
  entries with recipes — no stock created at import time. Stock
  enters via the existing míchání flow once the recipe is in the
  catalogue.
- **No mailing the recipe to anyone.** Pure local catalogue edit.

## Open questions for this screen

None. The flow is deliberately tight; deferred items live in the
"Future considerations" section of decision
[`0047`](../decisions/0047-xls-recipe-importer.md).
