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
and the obsluha Přehled (branch_dashboard). These rules are **no longer**
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
  `.row-delete-btn`, `.kpis`/`.kpi`, `.js-confirm`, and **`.sub-head`** (the
  grouped-section header: dot + label + count, coloured red/orange/neutral —
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
  `a,button,input,select,label` ignore-list); the `line_row_partial` add-row
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
  the red `#stock-block-banner` in `vydej_form.html`. For a **vlastník** that
  banner also carries a `#stock-block-inventura` link the JS points at inventura
  pre-filtered to **all products on the výdej** (not just the flagged ones —
  same as míchání: `?products=<all selected ids>&next=<výdej path>`, the 0060
  contract, same-tab); the per-branch base URLs come from a
  `{{ branch_inventura|json_script:"vydej-inventura-urls" }}` blob emitted only
  for vlastník (obsluha can't open inventura). A second helper,
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
  new decision.
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
  Dochází (orange) / V pořádku (neutral) — under `.sub-head` headers, with a KPI
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
  **same grouped design** as the Katalog: `catalogue_stock_groups([branch])` fed
  into the three `_catalogue_group.html` includes (Prázdné / Dochází / V pořádku),
  branch-scoped, `show_branch_chips=False` (single branch → no per-branch chips).
  The search input uses the grouped multi-tbody hook (`data-filter-rows=".cat-body"`
  / `data-filter-empty="#branch-stock-empty"`). The header **Dochází/Prázdné** KPIs
  are sourced from the groups (not `low_stock_rows()`) so they match the sub-heads.
  All active products show — an un-stocked product surfaces as Prázdné. **Do not
  flatten this back to a plain status-badge table** or rename the shared group
  hooks; that is a new decision.
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
