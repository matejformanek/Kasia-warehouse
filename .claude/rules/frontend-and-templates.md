**Django templates + the post-0068 frontend architecture. Read this before editing any `kasia/templates/**` or `kasia/static/css/**` file. The gotchas below render *silently wrong* — no exception, no crash — so they slip past a quick eyeball. Two of them are enforced by `inventory/tests/test_template_hygiene.py`; the rest are convention.**

This rule is the orientation layer. The *visual* contract (class names, hooks,
tokens, the exact CSS load order) lives in [`design-system.md`](./design-system.md)
and decisions [`0068`](../../context/decisions/0068-code-architecture-restructure.md)
/ [`0069`](../../context/decisions/0069-css-externalization.md) /
[`0070`](../../context/decisions/0070-round2-structure-refinements.md) — this file
points there, it does not restate it.

## Template gotchas (these have actually bitten us)

- **`{# … #}` comments are single-line only.** Django's lexer matches `{#.*?#}`
  *without* DOTALL, so a comment that wraps onto a second line is **not**
  recognised as a comment — it is printed verbatim onto the page as visible text.
  This shipped to prod twice. Use a one-line `{# … #}`, or, for anything longer,
  **`{% comment %}…{% endcomment %}`**. *Enforced:* `test_no_multiline_django_comments`.
- **Never inline `<style>` or use `@import`.** All CSS is `<link>`ed from
  `kasia/static/css/` (per 0069) — the manifest storage rewrites `url()`/`@import`
  at collectstatic, so an `@import` silently breaks. The only templates allowed to
  inline styles are the self-contained PDF (`dodaci_list.html`, `recipe_pdf.html`),
  e-mail, and `404`/`500` pages (they must not depend on the static pipeline).
  *Enforced:* `test_no_inline_style_or_import`.
- **Never `floatformat` inside a `type="number"` `value=`.** In the `cs` locale
  `floatformat` emits a comma (`45,5`); a number input rejects the comma and
  renders **blank**. For prefills use `|unlocalize` (dot) or a `ROUND_HALF_UP`
  1-dp value; display cells use `floatformat:1` freely. (Full rounding contract:
  design-system.md § "Quantities display at 1 dp".)
- **Finished-product quantities render by unit, not always kg** (per 0095). A
  „hotový výrobek" line shows „N ks" (int, `floatformat:0`) vs „X kg" (1 dp)
  keyed on `line.product.unit` — on the dodák PDF + on-screen detail, and via a
  per-row `.line-unit` label the výdej JS flips to „ks" on product `change`. The
  movement-form / dodák „Množství" headers are unit-neutral (no „(kg)"). Don't
  reintroduce a hardcoded „kg" on those surfaces.
- **Don't `escapejs` a `data-filter-text` value** (the 0063 live-filter hook). The
  row text is built from Django's default auto-escaping; `escapejs` emits `\"`
  that `dataset` reads literally and the filter breaks. Likewise **`data-filter-kg`
  (the 0084 live-KPI sum) must be `|unlocalize`d (dot), never `floatformat`
  (comma)** — a comma makes JS `parseFloat` truncate the kg total silently.
- **Don't rename the locked class names / JS-HTMX hooks** (`.card`, `table.lines`,
  `.sub-head`, `.row-link[data-href]`, `#lines-body`, `.row-move-btn` +
  the hidden `position` input (recipe reorder, 0092), `data-filter-rows`,
  `data-filter-bucket` / `data-filter-kg` / `data-kpi-live` (live KPI recompute, 0084),
  `data-guard-unsaved`, `.js-confirm`, `{% block page_help %}` / `#kasia-help` /
  `#help-fab` / `.help-dialog` / `.help-body` (per-page help, 0078), …). Restyle
  freely; renaming a hook or reordering the component CSS layer is a **new
  decision**. The full list is in design-system.md § "Keep stable".
- **No native `confirm()`/`alert()`/`prompt()` in sklad** (per 0061) — use
  `.js-confirm` / `window.kasiaConfirm()`. See design-system.md.
- **A new GET htmx partial endpoint must also be added to `EXCLUDED_URL_NAMES`
  in `inventory/middleware.py`** (per 0077), or every fragment swap writes a
  `ScreenVisit` row and pollutes the Aktivita log. POST endpoints need no entry
  (the middleware skips non-GET).

## Where things live (post-0068)

The `inventory` app is split into packages — **don't recreate the old monolith
files**:

- **Views:** `inventory/views/<area>.py` (e.g. `dodaci.py`, `dashboard.py`,
  `catalogue.py`, `inventura.py`, `movements/…`). Cross-view helpers live in
  `inventory/views/_shared.py`; permission gates in `accounts/permissions.py`
  (`require_vlastnik`). One area = one module; put a new view next to its siblings.
- **Templates:** `kasia/templates/inventory/<screen>.html` (sklad, extends
  `base.html`) and `kasia/templates/web/<page>.html` (public, extends
  `web/base.html`). Reusable fragments are `_partial.html`.
- **CSS (0069/0070):** `kasia/static/css/` — `tokens-sklad.css` /
  `tokens-web.css` → `base-sklad.css` / `base-web.css` → `components/*.css`
  (**sklad-only**, fixed `<link>` order in `base.html`) → `pages/<screen>.css`
  (`<link>`ed from the template's `{% block extra_head %}`, loads last, wins). The
  exact component order is documented in design-system.md § "CSS lives in static,
  layered" — a shared grouped-section look lives in `components/groups.css`.
- **Two surfaces, on purpose:** sklad (sharp/green, sidebar) vs public
  (mono/centered/green). They **diverge** and share no cross-surface component
  tier — don't try to unify them (design-system.md § "The two systems").

## Role-scoping is a recurring correctness concern

Obsluha (branch staff) are scoped to **their own branch** across the app —
movements, dodáky, the Přehled, and now inventura (per
[`0073`](../../context/decisions/0073-obsluha-own-branch-inventura.md)). When you
add a view or a template branch that shows branch data, ask *"what does an obsluha
on the other branch see/reach by URL?"* and gate it (`request.user.is_vlastnik` /
`is_obsluha` + `branch_id`, 403 on mismatch). The vlastník-only cross-branch
roll-ups ("Vše"/"Dochází zboží") must 403 for obsluha. Mirror the established
pattern (`movement_history`, `branch_dashboard`, `dodaci._deny_other_branch`).

## Before you commit a template/CSS change

1. **Run the guards:** `uv run pytest inventory/tests/test_template_hygiene.py`
   (comments + inline CSS) and the screen's own tests.
2. **Render it, don't just read it.** Static analysis missed the multi-line
   comment twice. Load the page (`make up`, or render via the test client /
   `curl`) and confirm no stray `{#`/`#}`/template syntax appears and the layout
   is intact.
3. **`uv run python manage.py collectstatic --noinput`** if you touched CSS — a
   bad `<link>`/`@import` fails here.
4. Full suite before pushing: `uv run pytest -q` · `uv run ruff check .` ·
   `uv run python manage.py check`.

## Cross-references

- [`design-system.md`](./design-system.md) — the visual contract, class names, hooks, CSS layer order (source of truth).
- [`0068`](../../context/decisions/0068-code-architecture-restructure.md) — the package split.
- [`0069`](../../context/decisions/0069-css-externalization.md) / [`0070`](../../context/decisions/0070-round2-structure-refinements.md) — CSS externalization + component layer.
- `inventory/tests/test_template_hygiene.py` — the mechanical guard for this rule.
