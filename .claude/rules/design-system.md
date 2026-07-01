**UI direction is locked by [`0054`](../../context/decisions/0054-adopt-ui-directions.md) (sklad) and [`0058`](../../context/decisions/0058-public-redesign-and-produkty-page.md) (public — supersedes 0054's public look). The two surfaces diverge on purpose; the shared CSS class names and the JS/HTMX hooks are a stable contract.**

## The two systems

- **Sklad** (`kasia/templates/base.html`, `inventory` + `accounts` under
  `/sklad/…`) — **sharp / technical**: radius 0 everywhere, brand green accent,
  left **sidebar** shell, **Inter** (UI) + **IBM Plex Mono** (numerals/codes/
  kg/dates, tabular-nums), KPI strip on dashboards. Tokens live in the
  `base.html` `:root` (`--accent` green, `--fg*`, `--line*`, `--ok-soft`, …).
- **Public** (`kasia/templates/web/base.html`, `web` app at `/`) — **mono ×
  centered, green-sections** (decision 0058, supersedes 0054 for the public
  surface): a **green `#006634` sticky nav bar** (white text + the jpg logo),
  **Space Grotesk** (display) + **Inter** (body), white body with **deep
  forest-green `#0a3b20` section bands** (`.proc` / `.closing`), pill buttons,
  green primary / ink-outline secondary. Tokens live in the `web/base.html`
  `:root` (`--green`, `--brandbar`, `--lgreen`, `--on-green`, `--ink*`,
  `--tint*`, …). **Five pages:** Domů · O nás · Sortiment (`/produkty/`) ·
  Provozovny · Kontakt. Maps are **Google Maps** embeds (`map_embed`/`map_link`
  from `web/content.py`).

Both carry the jpg Kasia logo (`brand/kasia-logo.jpg`) top-left. Imagery is
hand-authored green SVG/CSS + marked photo slots — no raster generation.

## Keep stable (renaming these = a new decision)

Child templates inherit the look through **shared class names**; the operator
JS/HTMX wiring depends on **specific hooks**. Restyle freely, but do not rename
or restructure:

- **Shared sklad classes:** `.card`, `.primary`/`.secondary`, `table.lines`,
  `.field`, `.messages`/`.msg.*`, `.tab-chip`, `details`, `.row-link`,
  `.recipients`, `.stock-warn`, `.non-form-errors`, `.warnings-banner`,
  `.row-delete-btn`, `.kpis`/`.kpi`. Keep the `:root` vars child templates use:
  `--fg-soft`, `--warn`, `--ok`, `--ok-soft`, `--error`, `--accent`.
- **Shared public classes (0058):** `.wrap`/`.narrow`, `.btn`/`.btn-primary`/
  `.btn-ghost` (+`.btn-outline` alias), `.site-header`/`.nav`/`.brand-logo`/
  `.nav-toggle`, `.hero`/`.kicker`/`.hero-cta`, `.photo-band`/`.photo-frame`,
  `.facts`/`.facts-grid`/`.fact`, `.sec-head`/`.sec-label`, `.band-tint`,
  `.cap-grid`/`.cap-card`, `.proc`/`.proc-chain`/`.step`/`.proc-cap`,
  `.seg-grid`/`.seg`, `.sort-chips`/`.chip`/`.brand`/`.brand-sep`,
  `.story-photo`/`.timeline`, `.closing`/`.contact-card`/`.prov-grid`/`.prov`,
  `.site-footer`. Auth/form pages reuse `.login-card`/`.login-panels`/
  `.login-aside`/`.login-meta`/`.card`/`.eyebrow`/`.lead` + `form .field`.
  Page-specific CSS (e.g. kontakt `.k-split`, produkty `.cat-grid`, provozovny
  location cards) lives in each template's `{% block extra_head %}`.
- **JS/HTMX hooks (sklad `base.html`):** the row-delete toggle (`.row-delete-btn`
  + `data-target` + `.line-row`/`.marked-deleted`, `<button type="button">`
  inside a `<td>`); whole-row nav (`tr.row-link[data-href]` + the
  `a,button,input,select,label` ignore-list); `stockWarnVals(row)` (row stays
  `<tr class="line-row" data-index>`, form is the `.closest("form")` with
  `[name=branch]`, inputs `lines-{idx}-product` / `lines-{idx}-quantity_kg`);
  HTMX targets `.stock-warn-cell` / `#lines-table` / `#lines-body` (beforeend)
  and the `.secondary` "Přidat řádek" button — the button additionally carries
  `id="add-line-btn"` so the auto-append `<script>` in
  `_movement_form_lines.html` can programmatically `.click()` it when the
  operator types in the trailing row. The `.app` wrapper must not nest
  the movement form such that `.closest("form")` / `[name=branch]` resolution
  changes.

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

## Don't hardcode what rots

Reference the tokens (`var(--accent)`, `var(--green)`, …), not raw hex, in new
templates. The canonical palette/radius/font values live in the two `:root`
blocks and in `0054` — point there rather than copying hex into this rule.

## Out of scope for web chrome

`inventory/dodaci_list.html` is a **WeasyPrint PDF** and e-mail templates are
**inbox** documents — they keep their own print/mail styling, not this system.

## Cross-references

- [`0054-adopt-ui-directions.md`](../../context/decisions/0054-adopt-ui-directions.md) — the decision
- [`0059-merge-objednavka-into-prijem.md`](../../context/decisions/0059-merge-objednavka-into-prijem.md) — Movement.status + planned príjem UI
- [`context/public-site.md`](../../context/public-site.md) — public visual assets
- [`no-premature-tech-choices.md`](./no-premature-tech-choices.md) — why design direction is gated
