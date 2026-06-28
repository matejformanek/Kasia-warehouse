**UI direction is locked by [`0054`](../../context/decisions/0054-adopt-ui-directions.md). The two surfaces diverge on purpose; the shared CSS class names and the JS/HTMX hooks are a stable contract.**

## The two systems

- **Sklad** (`kasia/templates/base.html`, `inventory` + `accounts` under
  `/sklad/…`) — **sharp / technical**: radius 0 everywhere, brand green accent,
  left **sidebar** shell, **Inter** (UI) + **IBM Plex Mono** (numerals/codes/
  kg/dates, tabular-nums), KPI strip on dashboards. Tokens live in the
  `base.html` `:root` (`--accent` green, `--fg*`, `--line*`, `--ok-soft`, …).
- **Public** (`kasia/templates/web/base.html`, `web` app at `/`) — **centered /
  curvy**: radius 18px (cards) / 999px (pills), company green
  (`--green:#235c33` family), soft shadows, **Sora** (headings) + **Inter**
  (body). Tokens live in the `web/base.html` `:root`.

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
- **Shared public classes:** `.btn`/`.btn-primary`/`.btn-outline`, `.card`,
  `.eyebrow`, `.stat`, `.lead`, `.grid`/`.cols-3`/`.cols-2`, `.login-card`/
  `.login-panels`/`.login-aside`/`.login-meta`, `.contact-panel`, `.people`/
  `.person`, `.badge`/`.badge.hq`, `.branches`/`.branch`, `.map-embed`,
  `header.site`, `footer.site`.
- **JS/HTMX hooks (sklad `base.html`):** the row-delete toggle (`.row-delete-btn`
  + `data-target` + `.line-row`/`.marked-deleted`, `<button type="button">`
  inside a `<td>`); whole-row nav (`tr.row-link[data-href]` + the
  `a,button,input,select,label` ignore-list); `stockWarnVals(row)` (row stays
  `<tr class="line-row" data-index>`, form is the `.closest("form")` with
  `[name=branch]`, inputs `lines-{idx}-product` / `lines-{idx}-quantity_kg`);
  HTMX targets `.stock-warn-cell` / `#lines-table` / `#lines-body` (beforeend)
  and the `.secondary` "Přidat řádek" button. The `.app` wrapper must not nest
  the movement form such that `.closest("form")` / `[name=branch]` resolution
  changes.

## Don't hardcode what rots

Reference the tokens (`var(--accent)`, `var(--green)`, …), not raw hex, in new
templates. The canonical palette/radius/font values live in the two `:root`
blocks and in `0054` — point there rather than copying hex into this rule.

## Out of scope for web chrome

`inventory/dodaci_list.html` is a **WeasyPrint PDF** and e-mail templates are
**inbox** documents — they keep their own print/mail styling, not this system.

## Cross-references

- [`0054-adopt-ui-directions.md`](../../context/decisions/0054-adopt-ui-directions.md) — the decision
- [`context/public-site.md`](../../context/public-site.md) — public visual assets
- [`no-premature-tech-choices.md`](./no-premature-tech-choices.md) — why design direction is gated
