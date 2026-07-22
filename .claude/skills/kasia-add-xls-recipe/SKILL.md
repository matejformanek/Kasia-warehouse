---
name: kasia-add-xls-recipe
description: >-
  Import a real receptura from one of Petr's XLS files into the warehouse DB
  (local smoke + prod) via an idempotent ORM script. Use whenever the user says
  "add recipe", "add a receptura", "xls recipe", "recept z xls", "import recipe
  to db", "importuj recepturu", or hands over an .xls/.xlsx recipe file. Real
  recipes are deliberately NOT entered through the in-app XLS importer button
  (decision 0088) — that path can't set is_stock_tracked, RecipeComponent.note,
  or default_batch_kg. Skeleton skill: refine it as more recipes land.
---

# Add an XLS receptura to the Kasia DB

Real recipes from Petr arrive as XLS files (usually in `~/Downloads/`). They are
entered via a **one-off idempotent ORM script in `scratchpad/`** of the main
checkout (untracked, kept), smoke-run locally, then run on prod. The canonical
reference scripts are `scratchpad/import_garlic_recipes.py` (multi-recipe, TYN)
and `scratchpad/import_sez_recipes.py` (14-recipe SEZ batch, branch variable,
composed postup blocks) — copy their shape.

## 1. Read the XLS

`xlrd` is already a project dep (`.xls` only; for `.xlsx` use `openpyxl` —
also installed — with `load_workbook(path, data_only=True)`). Dump the first
sheet:

```bash
uv run python - <<'EOF'
import xlrd
book = xlrd.open_workbook("/Users/matej/Downloads/<file>.xls")
sh = book.sheet_by_index(0)
for r in range(sh.nrows):
    vals = [sh.cell_value(r, c) for c in range(sh.ncols)]
    if any(v not in ("", None) for v in vals):
        print(r, vals)
EOF
```

Typical sheet shape:
- row 0 ≈ mixture name (often lowercase / abbreviated — confirm the proper
  `name_cs` with the user, e.g. sheet "česnek 90 %" → "Česneková pasta 90 %")
- ingredient rows: `(name, kg)` pairs; kg cells may be **blank** or hold text
- `Datum` / `Podpis` rows, then the **pracovní postup** free text below them
  (becomes `Product.notes`; keep Czech quotes „…" intact; ALL-CAPS lines are
  sentence-cased on import). SEZ knedlíkárna sheets also carry a balení line
  („BALIT Á 5 KG") — include it in the postup.

**Not every XLS is a recipe**: files named „obj …" / „objednávka" are
finished-product **orders** (product codes + kusy/palety) — context only
(proper display names, which products exist), never imported. Files with the
same name but different dates: diff them — identical → one import; different
→ newest wins (confirm with the user).

## 2. Resolve gaps with the user (AskUserQuestion)

Before writing any script, list the existing candidate products from the
**target** DB (`Product.objects.filter(kind=RAW)` names) and ask about:

- **Missing kg** — known convention: *1 pytel sůl = 32 kg*. Confirm anyway.
- **Ingredient → existing Product mapping** — granulation matters (G2 vs G5),
  salt naming varies ("sůl říčany" on the pytel label ≠ a new product; so far
  it maps to existing "Sůl na drť"). Never create a near-duplicate raw without
  the user picking it explicitly.
- **Same-product rows must be merged** — `RecipeComponent` refuses duplicate
  (mixture, component) pairs. Sum the kg; preserve the split in the per-line
  `note` (e.g. `35 + 37,5 kg (3x12,5 stříbrné pytle)`).
- **Mixture name** (`name_cs`) and **default batch** (`default_batch_kg` =
  sum of component kg unless the user says otherwise).

### Petr's ingredient-unification rulings (2026-07-22 — reuse, don't re-ask)

- VLOČKY PF51 = BRAMBOROVÉ VLOČKY → one product **„Bramborové vločky"**
  (component note `PF51` where the XLS said PF51).
- KRUPICE ≠ KRUPIČKA → **„Krupice hrubá"** vs **„Krupička"** (and „CUKR
  KRUPICE" is sugar → **„Cukr krupice"**).
- All škrob is the same → one product **„Škrob"** (note `Maisita` where the
  XLS said „škrob maisita").
- SŮL in SEZ recipes = **„Sůl jedlá"** — a different product from TYN's
  **„Sůl na drť"** (the „sůl říčany" pytle for česnekové drtě).
- VEJCE = **„Vejce sušená"** (dried egg; „vaječný bílek" would be separate
  and is spelled out in recipes when used).
- AROMA VANILKA = aroma Vanilka Silesia → **„Aroma vanilka"** (note
  `Silesia`); aroma Jahoda Strawberry → **„Aroma jahoda"** (note
  `Strawberry`).
- SMAŽENÁ CIBULE → **„Cibule smažená"**, distinct from the other cibule
  products.

## 3. Write the ORM script — `scratchpad/import_<slug>.py`

Follow `scratchpad/import_garlic_recipes.py` exactly:

- `Product.objects.get_or_create(name_cs=…)` for raws; **Voda** (and any other
  unlimited ingredient) gets `is_stock_tracked=False` in defaults.
- `Product.objects.update_or_create(name_cs=…)` for the mixture with
  `kind=MIXTURE`, `notes=<postup>`, `default_batch_kg=<Decimal>`.
- Ratios via `inventory.services.recipe_import._normalize_ratios([kg, …])`,
  then `assert sum(ratios) == Decimal("1.000000")` (drift is absorbed by the
  largest line inside the helper).
- Upsert each `RecipeComponent` (filter → update or create), set `note` **and
  `position` = the XLS row index (0-based; update it on upsert too — mixing
  order is part of the recipe, per decision 0092)**, call `full_clean()`
  before `save()` (mirrors `create_mixture_from_review`).
- Seed **0-kg `Stock` rows on the TARGET branch only** for the mixture + all
  its tracked raws (`get_or_create`, skip untracked) — put the branch in one
  variable at the top (`TYN` for the garlic recipes, `SEZ` for the knedlíkárna
  batch). **Never create rows on the other branch**; a raw already carried on
  the other branch (e.g. Medvědí česnek TYN→SEZ) just gains the target-branch
  row and keeps its existing one.
- End with a printed summary: counts, ratio sums, `default_batch_kg`, stock
  row counts on the target branch **and** the other branch (must be 0 new).

## 4. Local smoke run

Stack up via `make up`, then:

```bash
docker compose exec -T web python manage.py shell < scratchpad/import_<slug>.py
```

Check the summary (ratio sum `1.000000`, expected batch kg, 0 SEZ rows).
Re-running must be a no-op (idempotent).

## 5. Prod run

```bash
scp -i ~/.ssh/kasia_prod scratchpad/import_<slug>.py app@91.98.47.1:/srv/kasia/
ssh -i ~/.ssh/kasia_prod app@91.98.47.1 \
  "cd /srv/kasia && docker compose exec -T web python manage.py shell < import_<slug>.py"
```

`exec` into the running container is safe. Caveat: the box `.env` pins a stale
`WEB_IMAGE` (RUNBOOK § 5b) — if you need more than `exec` (e.g. `compose run`),
read the RUNBOOK first. Verify on `/sklad/katalog/`: mixture appears (Prázdné
group), detail shows the recipe lines + notes + „Výchozí dávka", míchání
prefills the batch.

## 6. Close out

- `context/state.md` Done entry (script path, recipe name, prod date).
- Keep the script in `scratchpad/` (untracked); the scp'd copy on the box can
  stay (idempotent) or be removed.

## Gotchas

- **In-app importer button is NOT used for real recipes** (0088) — ORM only.
- Duplicate components refused → merge same-product rows, note the split.
- Name collision → `update_or_create` by `name_cs` updates in place; make sure
  that's intended before running.
- Postup text: keep Czech typographic quotes („…") verbatim from the XLS;
  sentence-case ALL-CAPS instruction lines.
- Stock rows only on the recipe's target branch — never the other one.
- Blank kg cells in the XLS are common — ask, don't guess (except the
  confirmed *1 pytel sůl = 32 kg* convention).
- A recipe's XLS „CELKEM" may carry float noise (`800.1999…`) — compute the
  batch as the exact `Decimal` sum of the component kg, not the CELKEM cell.
