**UI direction is locked by [`0054`](../../context/decisions/0054-adopt-ui-directions.md) (sklad) and [`0058`](../../context/decisions/0058-public-redesign-and-produkty-page.md) (public — supersedes 0054's public look). The two surfaces diverge on purpose; the shared CSS class names and the JS/HTMX hooks are a stable contract.**

## The two systems

- **Sklad** (`kasia/templates/base.html`, `inventory` + `accounts` under
  `/sklad/…`) — **sharp / technical**: radius 0 everywhere, brand green accent,
  left **sidebar** shell, **Inter** (UI) + **IBM Plex Mono** (numerals/codes/
  kg/dates, tabular-nums), KPI strip on dashboards. Tokens live in
  `kasia/static/css/tokens-sklad.css` (`--accent` green, `--fg*`, `--line*`,
  `--ok-soft`, …), `<link>`ed from `base.html` (per [`0069`](../../context/decisions/0069-css-externalization.md)).
- **Public** (`kasia/templates/web/base.html`, `web` app at `/`) — **mono ×
  centered, green-sections** (decision 0058, supersedes 0054 for the public
  surface): a **green `#006634` sticky nav bar** (white text + the jpg logo),
  **Space Grotesk** (display) + **Inter** (body), white body with **deep
  forest-green `#0a3b20` section bands** (`.proc` / `.closing`), pill buttons,
  green primary / ink-outline secondary. Tokens live in
  `kasia/static/css/tokens-web.css` (`--green`, `--brandbar`, `--lgreen`,
  `--on-green`, `--ink*`, `--tint*`, …), `<link>`ed from `web/base.html`.
  **Five pages:** Domů · O nás · Sortiment (`/produkty/`) ·
  Provozovny · Kontakt. Maps are **Google Maps** embeds (`map_embed`/`map_link`
  from `web/content.py`).

Both carry the jpg Kasia logo (`brand/kasia-logo.jpg`) top-left. Imagery is
hand-authored green SVG/CSS + marked photo slots — no raster generation.

## CSS lives in static, layered (per [`0069`](../../context/decisions/0069-css-externalization.md) + [`0070`](../../context/decisions/0070-round2-structure-refinements.md))

All CSS is in `kasia/static/css/`, `<link>`ed (never inline `<style>`, never
`@import`): `tokens-sklad.css` + `tokens-web.css` (the two `:root` sets — kept
separate because both define `--line` with different values), `base-sklad.css`
/ `base-web.css` (shell + shared classes per surface), `components/*.css`
(**sklad-scoped** — see below), and `pages/<screen>.css` (per-screen). Shared
partials fold into a component file (`_confirm_dialog` → `components/dialogs.css`,
`_movement_form_lines` → `components/forms.css`) or their htmx host page's css
(`_mixing_preview` → `pages/mixing_job_create.css`). **Kept inline on purpose:**
PDF (`dodaci_list.html`, `recipe_pdf.html`) + e-mail templates (WeasyPrint /
inbox) and the `404.html` / `500.html` error pages (self-contained — must not
depend on the static pipeline during a failure).

**Sklad component CSS (0070) lives in `components/*.css` and is `<link>`ed from
`base.html` in this exact order, after `base-sklad.css` and before
`{% block extra_head %}`; never inline, never `@import`:**

```
tokens-sklad.css → base-sklad.css →
  components/tables.css → forms.css → kpis.css → filters.css → chips.css →
  groups.css → dialogs.css →
{% block extra_head %}  (pages/<screen>.css, still loads last, still wins)
```

`components/groups.css` holds the grouped stock-state section look —
`.sub-head` (+ `.empty`/`.low`/`.ok`/`.ordered` variants + `.dot`/`.count`),
`.cat-group`, `.prod-sub`, `.eff-empty`/`.eff-warn`, `.low-branch`/
`.empty-branch` — shared by the grouped Katalog, the vlastník Přehled (home)
and the obsluha Přehled (branch_dashboard). The `.empty-branch` chip
(„Prázdný na" column) is fed by the row's **`empty_branches`** (carried branches
at `effective ≤ 0`, per [`0091`](../../context/decisions/0091-empty-branch-chip-independent-of-threshold.md)),
the `.low-branch` chip („Dochází na") by **`low_branches`** (`effective` below a
nonzero threshold) — two **separate** lists in `_catalogue_rows`; merging them is
a new decision. These rules are **no longer**
page-scoped or duplicated in `pages/catalogue_index.css` / `pages/home.css`;
the only per-page override left is the `.sub-head` **margins** (home's differ
from the Katalog canonical and load later, so win).

The `components/` layer is **sklad-only** — the public surface keeps
`base-web.css` and there is no shared cross-surface component tier (the `--line`
token collision + the deliberate 0054-vs-0058 divergence). Two cascade
constraints are load-bearing: the `.over-stock` red-fill stays in
`components/tables.css` *after* the `table.lines` zebra, and the KPI-column
`@media` overrides live in `components/kpis.css` *after* the base `.kpi` rules
(both would lose if separated across the load order). The locked class names and
JS/HTMX hooks in this file are unchanged and **must not be renamed**; moving a
rule between these files is fine, renaming a class or reordering the layer is a
new decision.

## Keep stable (renaming these = a new decision)

Child templates inherit the look through **shared class names**; the operator
JS/HTMX wiring depends on **specific hooks**. Restyle freely, but do not rename
or restructure:

- **Shared sklad classes:** `.card`, `.primary`/`.secondary`, `table.lines`,
  `.field`, `.messages`/`.msg.*`, `.tab-chip`, `details`, `.row-link`,
  `.recipients`, `.stock-warn`, `.non-form-errors`, `.warnings-banner`,
  `.row-delete-btn`, `.kpis`/`.kpi`, **`data-kpi-live`** (the live-recompute KPI
  value hook, per 0084), `.js-confirm`, and **`.sub-head`** (the
  grouped-section header: dot + label + count, coloured red/orange/green —
  used by the grouped Katalog and the per-branch Přehled). Keep the `:root`
  vars child templates use: `--fg-soft`, `--warn`, `--ok`, `--ok-soft`,
  `--error`, `--accent`. Per-screen CSS is a linked stylesheet
  `kasia/static/css/pages/<screen>.css`, `<link>`ed from the template's
  **`{% block extra_head %}`** (the shell exposes it in `base.html`'s `<head>`).
  **`<link>` only — never inline `<style>`, never `@import`** (the manifest
  storage rewrites `url()`/`@import`; per [`0069`](../../context/decisions/0069-css-externalization.md)).
  Do not re-declare the `:root` tokens or shared classes there.
- **Per-page contextual help (per [`0078`](../../context/decisions/0078-per-page-contextual-help.md)):**
  `{% block page_help %}` (each screen overrides it with a focused help
  excerpt; the fallback in `base.html` points at Podpora), the global help
  `<dialog id="kasia-help" class="kasia-dialog help-dialog">` with its
  `.help-body`, and the fixed `#help-fab` „?" button — all inside the
  `{% if user.is_authenticated %}` block of `base.html`. Styling
  (`.help-dialog` / `#help-fab` / `.help-body`) is in
  `components/dialogs.css`. Renaming any of these hooks is a new decision. `.wrap`/`.narrow`, `.btn`/`.btn-primary`/
  `.btn-ghost` (+`.btn-outline` alias), `.site-header`/`.nav`/`.brand-logo`/
  `.nav-toggle`, `.hero`/`.kicker`/`.hero-cta`, `.photo-band`/`.photo-frame`,
  `.facts`/`.facts-grid`/`.fact`, `.sec-head`/`.sec-label`, `.band-tint`,
  `.cap-grid`/`.cap-card`, `.proc`/`.proc-chain`/`.step`/`.proc-cap`,
  `.seg-grid`/`.seg`, `.sort-chips`/`.chip`/`.brand`/`.brand-sep`,
  `.story-photo`/`.timeline`, `.closing`/`.contact-card`/`.prov-grid`/`.prov`,
  `.site-footer`. Auth/form pages reuse `.login-card`/`.login-panels`/
  `.login-aside`/`.login-meta`/`.card`/`.eyebrow`/`.lead` + `form .field`.
  Page-specific CSS (e.g. kontakt `.k-split`, produkty `.cat-grid`, provozovny
  location cards) lives in `kasia/static/css/pages/<screen>.css`, `<link>`ed from
  each template's `{% block extra_head %}` (`<link>` only, no `@import`).
- **JS/HTMX hooks (sklad `base.html`):** the row-delete toggle (`.row-delete-btn`
  + `data-target` + `.line-row`/`.marked-deleted`, `<button type="button">`
  inside a `<td>`); whole-row nav (`tr.row-link[data-href]` + the
  `a,button,input,select,label` ignore-list); **the recipe-formset reorder
  (per [`0092`](../../context/decisions/0092-recipe-component-order.md)):**
  `.row-move-btn` + `data-dir="up|down"` and the hidden per-row `position`
  input on `product_form.html`, whose `renumber()` rewrites 0..n-1 in **DOM
  order over all rows incl. `.marked-deleted`** after every move / add-row /
  delete-toggle and dispatches a bubbling `change` so `data-guard-unsaved`
  arms — plus the recipe clone hooks `#recipe-table`/`#recipe-body`/
  `#recipe-empty-row`/`#recipe-add-row`/`recipe-TOTAL_FORMS` (locked here;
  0090 left them implicit). The server re-normalizes positions to dense
  0..n-1 over all surviving forms on save (form-index fallback) — don't
  make the hidden field required or trust client values; the `line_row_partial` add-row
  HTMX targets `#lines-table` / `#lines-body` (beforeend) and the `.secondary`
  "Přidat řádek" button — the button additionally carries `id="add-line-btn"` so
  the auto-append `<script>` in `_movement_form_lines.html` can programmatically
  `.click()` it when the operator types in the trailing row. On **výdej**
  (`show_stock_warn=True`) the add-line button appends `?warn=1` to the
  `line_row_partial` URL so added rows get the `#stock-warn-cell-{idx}` div (the
  JS render target below) too.
- **Výdej live over-stock check — pure JS (no htmx round-trip; server overdraw
  card per 0042 is the real guardrail):** the výdej view embeds a
  `{{ stock_map|json_script:"vydej-stock-map" }}` blob — a
  `dict[branch_id → dict[product_id → "qty" (3-dp dot string)]]` of raw
  `Stock.quantity` for active branches. A script in `_movement_form_lines.html`
  (inside `{% if show_stock_warn %}`) parses it once, then on any
  `#lines-body` `input`/`change`, any deferred (`queueMicrotask`)
  `.row-delete-btn` click, and any `[name=branch]` `change` re-runs `recompute()`:
  it reads the selected `[name=branch]`, walks each
  `.line-row:not(.marked-deleted)`'s `select[name$="-product"]` +
  `input[name$="-quantity_kg"]`, **aggregates requested qty per product**
  (mirroring the server `_compute_overdraw`), compares `round3(sum) >
  round3(avail)`, and writes each row's `#stock-warn-cell-{idx}` div (over → red
  `.stock-warn.over` box; product picked, within stock or no qty yet →
  `.stock-warn` "Na skladě: X kg" shown the moment the product is selected; no
  product yet → faint `.stock-warn.stock-hint` "Na skladě: —" placeholder),
  toggles `.over-stock` on offending `tr.line-row` (red-fill, CSS in
  `base.html`). On výdej that `.stock-warn-cell` div lives **in the Šarže column
  cell** (`_line_row.html`) — výdej never uses Šarže, so its column header reads
  "Sklad" and the sarze field becomes a hidden input; this keeps the warning out
  of the Množství cell so it can't stack under the qty input and grow the row.
  The JS finds it by `row.querySelector(".stock-warn-cell")` / the
  `#stock-warn-cell-{idx}` id regardless of which `<td>` holds it. While any line
  is over it disables `#vydej-submit` + un-hides
  the red `#stock-block-banner` in `vydej_form.html`. When the operator can fix
  stock the banner also carries a `#stock-block-inventura` link the JS points at
  inventura pre-filtered to **all products on the výdej** (not just the flagged
  ones — same as míchání: `?products=<all selected ids>&next=<výdej path>`, the
  0060 contract, same-tab); the per-branch base URLs come from a
  `{{ branch_inventura|json_script:"vydej-inventura-urls" }}` blob emitted for a
  **vlastník** (all active branches) **and — per 0073 — for an obsluha on their
  own branch** (`{str(user.branch_id): inventura_edit(user.branch.code)}`), so
  obsluha's live jump *and* the static 0042 overdraw-table link
  (`inventura_fix_url`) always target their **own-branch** inventura, never the
  vlastník-only `stock_adjust_edit` (which 403s for obsluha). The blob/link are
  hidden only when neither role applies. A second helper,
  `refreshProductOptions()`, **disables an already-chosen product in every other
  row's dropdown** so a product can't be picked on two lines; it runs on the
  same `input`/`change` + `htmx:afterSwap` (fresh added rows) + row-delete
  events. Per [`0071`](../../context/decisions/0071-prijem-dedup-products.md)
  this dedup runs on **both** movement forms (an always-rendered IIFE in
  `_movement_form_lines.html`, outside the `show_stock_warn` block) — příjem now
  blocks duplicate products too (client-side only; a posted duplicate is
  harmless — two additive received lines). `show_stock_warn` still gates **only**
  the výdej over-stock check, not the dedup. Missing (branch, product)
  ⇒ `0` avail. The server aggregate-duplicates overdraw check (0042) stays as a
  harmless safety net. The
  old htmx machinery (`stock_warn_partial` view/route, `_stock_warn.html`,
  `stockWarnVals` in `base.html`, per-input `hx-target="#stock-warn-cell-{idx}"`)
  is **removed** — do not reintroduce it.
- **Live list filter (`base.html`, per [`0063`](../../context/decisions/0063-diacritic-insensitive-client-filtering.md)):**
  the attribute-driven, diacritic-insensitive, typo-tolerant as-you-type row
  filter. A search `<input data-filter-rows="<tbody selector>">` (optionally
  `data-filter-count` / `data-filter-empty`, both element selectors) filters
  every `tr[data-filter-text="…"]` in that tbody. The row text is built from
  Django's **default auto-escaping** — do **not** apply `escapejs` (it would
  emit `\"` that `dataset` reads literally). Renaming `data-filter-rows` /
  `-count` / `-empty` / `-text`, or the `foldText` / `levenshtein` /
  `matchesQuery` helpers, is a new decision. Used on `#history-table` /
  `#stock-table` and the grouped Katalog (+ matching `-count` / `-empty`).
  **The matcher is also exposed as `window.kasiaRowFilter`** (`fold` /
  `tokenize` / `matches`) so bespoke filters that can't use the `data-filter-*`
  hook reuse the SAME fold/fuzzy logic (per
  [`0080`](../../context/decisions/0080-inventura-critical-toggle-and-fuzzy-filter.md)
  — the inventura name filter uses it). Renaming `window.kasiaRowFilter` is a
  new decision. **Live KPI / group-count recompute (per
  [`0084`](../../context/decisions/0084-live-kpi-recompute-on-name-filter.md)):**
  on the grouped stock screens the same `apply()` also **recomputes the KPI
  strip + each group's `.sub-head .count` from the visible rows as you type**,
  and **restores** the server-original values when the box is cleared
  (cache-and-restore — each target caches its server text on first run). KPI
  value spans carry **`data-kpi-live`** (`empty`/`low`/`products`/
  `products-stocked`/`total-kg`); it is a **separate** hook from the
  reserved-but-unwired `data-filter-count` (the KPI strip is several per-state
  buckets + a kg sum, not one visible-row total). Gated on any matched tbody
  carrying `data-filter-bucket`, so history / email-log single lists and the
  filter-less home Přehled are untouched. Renaming `data-kpi-live` is a new
  decision. **Dropping** `data-kpi-live` from a span (as `branch_dashboard` does
  for `products-stocked`/`total-kg` under 0094, once V pořádku no longer renders
  there) is a per-template choice that makes that KPI static — it is **not** a
  hook rename, which stays forbidden.
  The číselníky (Dodavatelé / Odběratelé / Pobočky) carry **no** name search
  (the locked mockups 12–14 show only the Stav filter) — the 0063 standalone
  input added there was removed in the Phase-2 swap. Do **not** reuse the
  reserved ids `#lines-table` / `#lines-body` (movement-form hook above).
- **Grouped multi-tbody filter (extends 0063, per
  [`0064`](../../context/decisions/0064-grouped-catalogue-client-filter.md)):**
  `apply()` uses `querySelectorAll(data-filter-rows)`, so `data-filter-rows` may
  match **several** tbodies (the grouped Katalog wires `data-filter-rows=".cat-body"`
  onto its three group `<tbody class="cat-body">`). A tbody may carry
  **`data-filter-group="<section selector>"`**; when that group has rows but none
  match, its whole section (the `.sub-head` header + table, wrapped in one
  container, e.g. `#cat-group-empty`) is hidden. A tbody without
  `data-filter-group` is a plain single list and behaves exactly as under 0063
  — so every existing single-tbody filter is untouched. Renaming
  `data-filter-group` or the multi-selector behaviour is a new decision.
  Per [`0084`](../../context/decisions/0084-live-kpi-recompute-on-name-filter.md)
  the group `<tbody>` also carries **`data-filter-bucket`** (`empty`/`low`/`ok`)
  and each row a **`data-filter-kg`** (raw on-hand sum, `|unlocalize`d
  dot-decimal — never `floatformat`, whose comma breaks the JS sum) so `apply()`
  can tally per-state buckets + a kg total for the live KPI recompute above.
  Renaming `data-filter-bucket` / `data-filter-kg` is a new decision.

## Movement.status (planned príjem) — per 0059

`Movement` carries a `status` (`done` / `planned`). A **PLANNED** row is a
planned příjem (objednávka) and behaves differently in the UI:

- It routes to **`prijem_confirm`** (Přijmout), **not** `movement_edit` — the
  Historie "Plánované" tab and the inventura inline "upravit" link both point
  there. A PLANNED row must never open the DONE-movement editor.
- Its cancel (`prijem_plan_cancel`) is an **out-of-form** `<button
  form="plan-cancel-{pk}">` driven by `_confirm_dialog.html`, so no `<form>`
  nests inside `tr.row-link` (same locked-hook gotcha as inventura).
- The low-stock **"Objednáno"** badge is sourced from **PLANNED příjem movement
  lines** (`Sum(quantity_kg)`/`Min(expected_on)`), not `PlannedOrder`. It stays
  badge-only — informational, never changing effective/deficit/membership.

See [`0059`](../../context/decisions/0059-merge-objednavka-into-prijem.md).

## Native browser dialogs are forbidden in sklad (per 0061)

**No `confirm()` / `alert()` / `prompt()` in any sklad template or script.**
Every confirm/alert uses the in-app dialog: give a submit button
`class="js-confirm"` plus `data-confirm-title` / `data-confirm-body` /
`data-confirm-cta`, or call `window.kasiaConfirm({...})` → `Promise<bool>`.
The partial (`inventory/_confirm_dialog.html`) is included once globally at the
bottom of `base.html`. Destructive confirms are red by default; a
non-destructive confirm ("Provést převod?", "Spustit dávku?") sets
`data-confirm-danger="false"`. The delegated handler submits the button's
`form=` (or closest `<form>`) via `requestSubmit()`, so a `.js-confirm` button
must never sit inside a `tr.row-link` (whole-row-nav hook) — same gotcha as the
row-delete button.

The **per-page help panel (0078)** follows the same rule: `#kasia-help` is a
`<dialog>` opened with `showModal()` and closed via a „Zavřít" button / `Esc` /
backdrop — **no native `alert()`**. It reuses `.kasia-dialog` styling.

**Unsaved-changes guard — `data-guard-unsaved` on a `<form>`.** A reusable,
opt-in guard also lives in `_confirm_dialog.html` (so it ships everywhere
`kasiaConfirm` does). Put `data-guard-unsaved` on any data-entry `<form>`: once
the operator edits a field in it, an in-page link click (sidebar, "Zrušit",
header — any `a[href]`) is intercepted and confirmed via `kasiaConfirm` before
navigating away, so half-filled work isn't dropped silently. New-tab links
(`target` set), `#anchors` and `javascript:` are left alone; any intentional
form submit (the save, or an out-of-form `.js-confirm` cancel/remove) clears the
guard. Wired on **příjem / výdej / míchání / plánovaný převod+míchání / produkt
/ číselníky (pobočka·dodavatel·odběratel) / nastavení / úprava stavu / potvrzení
plánovaného příjmu**. **`inventura_edit.html` keeps its own bespoke guard** (its
message is inventura-specific and it works) — do **not** also add
`data-guard-unsaved` there or the dialog fires twice. Renaming
`data-guard-unsaved` is a new decision.

## Quantities display at 1 dp, comma from the locale (per 0061)

Quantity displays use **`floatformat:1`** (never `:3`, never raw
`{{ x }}` — raw output localizes the comma but keeps 3 dp); the Czech comma
comes free from the active `cs` locale — **no custom filter**. This applies to
**every kg display on every page**, including the dodací-list PDF
(`{{ line.quantity_kg|floatformat:1 }}`). Operator quantity entry uses
`step="0.1"` on `type="number"` inputs (browser shows the comma, submits a dot —
no server comma-parsing). JS-truth / native-input attributes (`data-current`,
`value=` on `type=number`) keep the **dot** — via `|unlocalize` (JS-math /
URL params) or a **`ROUND_HALF_UP` 1-dp** value for prefills. **Never
`floatformat` inside a `type=number` `value=`** — it emits a comma the browser
rejects, blanking the field.

**Rounding for kg is ROUND_HALF_UP at 1 dp — everywhere, one value.** Display
(`floatformat:1`), the input **prefill**, the **`data-current`** JS-truth, and
the **server no-op compare** must all round the *same* current value with
`quantize(Decimal("0.1"), ROUND_HALF_UP)` (a shared view helper is the pattern —
e.g. inventura's `_kg1`). `data-current` is that clean 1-dp dot value
(`{{ row.current_1dp|unlocalize }}`), **not** the raw 3-dp stock.
**Ban `f"{x:.1f}"` / `|stringformat:'.1f'` for kg prefills** — Python's default
`Decimal`/`format` rounding is banker's (HALF_EVEN: `45.45 → 45.4`), which
disagrees with `floatformat:1`'s HALF_UP (`45.45 → 45,5`); the mismatch makes a
`.x5` row load looking edited and re-submit as a phantom correction demanding a
reason. Use `quantize(Decimal("0.1"), ROUND_HALF_UP)` instead. The **recipe** is
the only
exception to 1 dp: recipe-PDF **percentages** stay at `floatformat:"2"` and the
component **ratios** (`rc.ratio`, proportions not kg) render raw — both may need
more precision. Model `decimal_places` stays 3 — no migration; values round to
0.1 on the next save.

The inventura **Dochází** view prefills the nový-stav cell with current stock
(1 dp), same as the per-branch and *Vše* views — it is **not** left blank.

Stock-correction saves (inventura, upravit-stav) **compare edits at 1 dp** — a
value equal to current at 1 dp is a no-op (no movement, no reason required); the
client-side delta/dirty check rounds to 1 dp (`Math.round(x*10)`) to match the
server (`quantize(Decimal("0.1"), ROUND_HALF_UP)`). Stored values are left
untouched (sub-0.1 residue from historical 3dp entry is harmless and invisible).
Do not restore full-precision comparison — it resurfaces phantom `+0.00x`
corrections that demand a spurious reason.

## Don't hardcode what rots

Reference the tokens (`var(--accent)`, `var(--green)`, …), not raw hex, in new
templates. The canonical palette/radius/font values live in the two `:root`
blocks and in `0054` — point there rather than copying hex into this rule.

## Katalog is grouped; Inventura is a nav landing

- **Katalog** (`catalogue_index`, per
  [`0064`](../../context/decisions/0064-grouped-catalogue-client-filter.md)) is
  **grouped by stock state** into three separate `<table>`s — Prázdné (red) /
  Dochází (orange) / V pořádku (green) — under `.sub-head` headers, with a KPI
  strip. The view groups its rows server-side and renders **only the non-empty
  groups**. Rows are **whole-row `row-link` with no per-row buttons** (editing is
  on the product detail page). It uses the grouped multi-tbody filter above.
  Per [`0072`](../../context/decisions/0072-reorder-threshold-not-null.md) the
  **"Prázdné" group keys on effective ≤ 0 alone** — the reorder threshold (now
  always set, default 0) no longer gates it, so a genuinely-empty product always
  lands in the red group. The grouping + KPI logic is the shared view helper
  `catalogue_stock_groups(products, branches)` (in `inventory/views/catalogue.py`)
  — **one source of truth** for both the Katalog and the obsluha Přehled below;
  the group section itself is the `_catalogue_group.html` partial.
- **Obsluha Přehled** (`branch_dashboard`) — its **"Stav skladu"** card uses the
  **same grouped design** as the Katalog: `catalogue_stock_groups([branch])`
  branch-scoped, `show_branch_chips=False` (single branch → no per-branch chips).
  Per [`0094`](../../context/decisions/0094-branch-dashboard-critical-only.md)
  **only the two CRITICAL groups render** — `empty_rows` (Prázdné) + `low_rows`
  (Dochází), via `_catalogue_group.html`; **V pořádku is Katalog-only** (the view
  computes `ok_rows` but no longer passes it) so obsluha isn't flooded by the
  healthy long tail — the full catalog stays reachable via the branch-scoped
  **Katalog** + Inventura. When nothing is critical the card shows a positive
  empty-state („Vše nad objednacím bodem…"). The search input uses the grouped
  multi-tbody hook (`data-filter-rows=".cat-body"` /
  `data-filter-empty="#branch-stock-empty"`). The header **Dochází/Prázdné** KPIs
  are sourced from the groups (not `low_stock_rows()`) so they match the
  sub-heads; the **`products-stocked` + `total-kg`** KPIs are **static** here (no
  `data-kpi-live` — the 0084 live recompute would under-count without V pořádku
  rendered), while **`empty` + `low` stay live**. All active **stock-tracked**
  products are grouped — an un-stocked (but tracked) product surfaces as Prázdné.
  Products with `is_stock_tracked=False` are excluded from this card (as from
  Katalog and inventura). **Do not flatten this back to a plain status-badge
  table**, re-add V pořádku, or rename the shared group hooks; that is a new
  decision.
- **Owner Přehled** (`home`) — its attention buckets (the „Vyprodáno"/Prázdné KPI
  + per-branch empty lists) are intentionally sourced from
  **`low_stock_rows(include_empty=True)`** — the broadened `_below_alert` rule
  (Katalog Prázdné + Dochází), per
  [`0093`](../../context/decisions/0093-owner-prehled-empty-rule.md) — so a pair
  empty at the default threshold 0 is counted, not dropped by the narrow
  `effective < threshold`. **Do not "fix" this back to the narrow rule.** (The
  inventura „Dochází zboží" roll-up keeps the narrow `low_stock_rows()`, its 0057
  contract; and `branch_dashboard`'s Dochází/Prázdné still come from the
  *groups*, not `low_stock_rows`.)
- **Untracked products (`Product.is_stock_tracked=False`, per
  [`0088`](../../context/decisions/0088-recipe-component-notes-and-untracked-ingredients.md)):**
  e.g. „Voda". They carry **no Stock rows** and are **unlimited** — excluded from
  Katalog / obsluha Přehled / inventura (both self-built querysets) /
  `low_stock_rows` / `catalogue_stock_groups` / the low-stock alert, and
  unselectable in the movement product dropdown. They are **never deducted**
  (`_apply_line_to_stock` early-returns), **never seeded**
  (`seed_branch_carriage_for_product` early-returns), **never reserved** or
  consumed in míchání (`plan_mixing_job` / `start_mixing_job` fresh-start skip
  them), and **never block** a výdej/míchání overdraw. In
  `_mixing_preview.html` their row shows **„neomezeno"** (Stav „ok"). They still
  appear on the recipe PDF + mixture detail recipe table (a real ingredient with
  a ratio/kg). The flag is set at product creation only (ORM/admin), not on
  `ProductForm`. Adding or removing this exclusion — or exposing the flag on the
  operator form — is a new decision.
- **Finished products (`Product.kind == "hotovy_vyrobek"`, „hotový výrobek",
  per [`0095`](../../context/decisions/0095-hotovy-vyrobek-finished-product-type.md)):**
  a bought-in unlimited good sold **by the piece**. Behaviour keys
  on **`Product.is_unlimited`** (`not is_stock_tracked OR kind == HOTOVY_VYROBEK`)
  — the single concept every stock chokepoint uses (never
  deducted/seeded/reserved, never blocks výdej/míchání overdraw, never alerts).
  Visibility keys on **`is_stock_tracked`**, so unlike Voda a hotový výrobek
  **stays visible**: own Katalog group **„Hotové výrobky — neomezeno"**
  (`unlimited_rows`, rendered only when no `state=` filter), **selectable on
  výdej** (lands on the dodací list), but **excluded from inventura** (both
  querysets `.exclude(kind=HOTOVY_VYROBEK)`) and **příjem**
  (`MovementLineForm(exclude_finished=True)`). Display unit derives from the
  kind via **`Product.unit`** (`"ks"`/`"kg"`); the piece count lives in the
  existing `quantity_kg` — **no schema change**. Never in
  `empty_rows`/`low_rows`/`ok_rows` (computed from the non-unlimited rest), so
  it can't reach the obsluha Přehled or the inventura „Dochází" toggle.
  Adding/removing any exclusion, or storing pieces anywhere but `quantity_kg`,
  is a new decision.
- **`RecipeComponent.note` (per
  [`0088`](../../context/decisions/0088-recipe-component-notes-and-untracked-ingredients.md)):**
  a per-ingredient free-text comment (the same raw spice may carry a different
  note in a different mixture). Renders on `recipe_pdf.html` (a per-ingredient
  „Poznámka" column — the `<tfoot>` „Celkem" row carries a matching empty `<td>`)
  and on `product_detail.html`'s **mixture** recipe table — **not** on the raw
  ingredient's own page (`used_in` table) nor the second "Spočítat dávku" scaler
  table. Keep it flowing to both surfaces when editing either. **Editable on the
  operator recipe formset** (`RecipeComponentForm`, a „Poznámka" column on
  `product_form.html`, vlastník-only like the whole formset — per
  [`0090`](../../context/decisions/0090-component-note-on-operator-recipe-form.md),
  which reverses 0088's admin/ORM-only clause); the add-row clone JS rewrites the
  `note` widget's `name`/`id` alongside `component_product`/`ratio`/`position`
  (the hidden mixing-order input, per 0092). Also settable via admin / ORM.
- **`RecipeComponent.position` (per
  [`0092`](../../context/decisions/0092-recipe-component-order.md)):** 0-based
  per-mixture **mixing order** („míchat v tom pořadí, jak jsou suroviny odshora
  řazeny") — every component render site (product detail recipe + scaler,
  recipe PDF, míchání preview, the operator formset, admin) orders by
  `("position", "id")`; `MixingJobLine`s are created in that order and re-read
  by `("id",)`. Reordered via the `.row-move-btn` hook above; importer, seed
  and ORM entry scripts set it from source row order. Do **not** restore an
  alphabetical `order_by` on these sites.
- **`Product.default_batch_kg` (per
  [`0089`](../../context/decisions/0089-mixture-default-batch-kg.md)):** the
  mixture's default batch size (`0` = unset, gated on `> 0`). Prefills the míchání
  `#id_target_qty` — **GET-only** server echo (never on POST) + a
  `{{ mixture_defaults|json_script:"mixture-defaults" }}` blob read by a
  capture-phase `change` listener on `#id_mixture` that overwrites the total on
  dropdown change — and seeds the product-detail „Spočítat dávku" scaler (dot
  string, quantized inline in `catalogue.py`) + shows a „Výchozí dávka" line.
  Editable on `ProductForm` **vlastník-only** (reuses `can_edit_threshold`); set
  via ORM / admin otherwise. Renaming the `#mixture-defaults` hook or the `> 0`
  gating is a new decision.
- **Inventura** (per
  [`0065`](../../context/decisions/0065-inventura-sidebar-nav.md), access
  amended by [`0073`](../../context/decisions/0073-obsluha-own-branch-inventura.md))
  has a sidebar + mobile nav item in the Provoz group, under Katalog, shown for
  **`is_vlastnik or is_obsluha`**. Its href is conditional in `base.html`: the
  user's own branch (`inventura_edit code=<user.branch.code>`) if they have one,
  else the all-branch **"Vše"** (`code='vse'`). No new view/chooser. A
  **single-branch** inventura carries a **"Dochází / prázdné"** checkbox next to
  the name filter that scopes the visible rows to the **critical** products at
  that branch — everything the Katalog puts in **Prázdné OR Dochází** (per
  [`0080`](../../context/decisions/0080-inventura-critical-toggle-and-fuzzy-filter.md);
  `data-low` row attr, membership from `catalogue_stock_groups([branch])` — NOT
  `low_stock_rows()` alone, which would miss an empty product whose threshold is
  0). It is ANDed with the name query in the screen's own custom filter (not the
  0063 `data-filter-*` hook), and that name filter reuses the shared
  `window.kasiaRowFilter` matcher so it is diacritic-/typo-tolerant like the
  Katalog. Hidden on the cross-branch "Vše" / "Dochází zboží" views (the
  `dochazi` roll-up still uses `low_stock_rows()`, its own 0057 contract).
  - **Obsluha access (0073) — hard constraint.** `inventura_edit` lets an
    **obsluha run inventura only for their OWN branch** (the full editor —
    `[STAV]` corrections **and** dated objednávky); the cross-branch **"Vše"**
    (`vse`) / **"Dochází zboží"** (`dochazi`) views and any other branch code
    raise **403** for a non-vlastník. The inventura template's **branch switcher
    / Vše / Dochází links are `{% if user.is_vlastnik %}`-gated** (obsluha would
    403 on them); the single-branch "Dochází" **toggle** stays available to
    obsluha. The branch **Přehled** (`branch_dashboard`) carries a top-right
    **Inventura** button (`.inv-btn`, orange) → `inventura_edit code=branch.code`.
    The Katalog's own `cta-inventura` button stays **vlastník-only**. Don't
    re-restrict inventura to vlastník-only or widen obsluha to cross-branch —
    that's a new decision.

## Dodací listy are obsluha own-branch scoped (per 0040)

The dodací-list views enforce branch scoping for `obsluha`, mirroring
`movement_history`/`branch_dashboard`: `dodaci_list_index` filters to the
operator's own branch and renders **no branch dropdown** (the vlastník keeps
it); `dodaci_list_detail` / `_pdf` / `_resend` **early-return a 403** when the
dodák belongs to another branch (shared `_deny_other_branch` helper). This is a
locked contract per decision 0040 — don't drop the filter or expose the
dropdown to obsluha. (`recipe_pdf` is a product document, not branch-scoped, and
is deliberately exempt.)

## Nastavení recipients — per-flag opt-ins + branch scope (per 0081)

The `/sklad/nastaveni/` „Příjemci dodacího listu" table
(`settings_form.html`) now carries, per row, **two extra checkboxes** —
**„Dodací listy"** (`is_dodaci_recipient`) and **„Podpora"**
(`is_feedback_recipient`) — plus a **„Pobočka" dropdown** (`dodaci_branch`,
first option **„Všechny"** = null). `is_active` is the master switch. Routing is
now per-flag: dodáky go to `is_active AND is_dodaci_recipient AND (dodaci_branch
null OR == dodák.branch)`; Podpora to `is_active AND is_feedback_recipient` (with
`FEEDBACK_NOTIFY_EMAIL` fallback); the „dochází" souhrn unchanged
(`is_low_stock_recipient`). Every dodák is **also** mailed to its issuer
(`movement.created_by`), so the old `_assert_recipients_set` výdej guard is gone.
The JS-clone hooks (`#recipient-body` / `#recipient-empty-row` /
`#recipient-add-row` / `recipient-TOTAL_FORMS`) are unchanged — the hidden empty
row hand-writes the two new checkboxes (dodák pre-checked) + a `<select>` whose
first `<option value="">` is „Všechny". These are **no new GET partial
endpoint**, so `frontend-and-templates.md`'s `EXCLUDED_URL_NAMES` rule needs no
entry.

## Out of scope for web chrome

`inventory/dodaci_list.html` is a **WeasyPrint PDF** and e-mail templates are
**inbox** documents — they keep their own print/mail styling, not this system.

## Cross-references

- [`0054-adopt-ui-directions.md`](../../context/decisions/0054-adopt-ui-directions.md) — the decision
- [`0059-merge-objednavka-into-prijem.md`](../../context/decisions/0059-merge-objednavka-into-prijem.md) — Movement.status + planned príjem UI
- [`0060-michani-immediate-only.md`](../../context/decisions/0060-michani-immediate-only.md) — míchání immediate action + inventura `?products=`/`next` contract
- [`0061-display-1dp-comma.md`](../../context/decisions/0061-display-1dp-comma.md) — 1 dp comma display + banned native dialogs
- [`0063-diacritic-insensitive-client-filtering.md`](../../context/decisions/0063-diacritic-insensitive-client-filtering.md) — the `data-filter-*` live filter hook
- [`0064-grouped-catalogue-client-filter.md`](../../context/decisions/0064-grouped-catalogue-client-filter.md) — grouped Katalog + multi-tbody filter extension
- [`0065-inventura-sidebar-nav.md`](../../context/decisions/0065-inventura-sidebar-nav.md) — Inventura nav landing
- [`0066-planned-in-vse-and-prehled.md`](../../context/decisions/0066-planned-in-vse-and-prehled.md) — planned in Historie "Vše" + Přehled; history pagination
- [`context/public-site.md`](../../context/public-site.md) — public visual assets
- [`no-premature-tech-choices.md`](./no-premature-tech-choices.md) — why design direction is gated
