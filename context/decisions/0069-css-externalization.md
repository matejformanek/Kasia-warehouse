# 0069 — Externalize CSS into a static layered token system

**Date:** 2026-07-03
**Decider:** Matej
**Status:** Active
**Amends:** [`0054-adopt-ui-directions.md`](./0054-adopt-ui-directions.md) +
[`0058-public-redesign-and-produkty-page.md`](./0058-public-redesign-and-produkty-page.md)
(where the CSS *lives*, not how it *looks*)

## Context

All CSS is inline: 311 LOC in `kasia/templates/base.html` (sklad), 388 in
`kasia/templates/web/base.html` (public), plus 17 per-screen `{% block
extra_head %}` `<style>` blocks. There are zero static `.css` files and only 3
`!important` declarations — the problem is *scattering* (tokens and rules copied
across templates), not specificity wars. Part of the 0068 restructure. The look
is locked (0054 sklad / 0058 public) and must stay **pixel-identical**.

## Options considered

- **Static layered files, `<link>`-loaded (chosen).** Extract to
  `kasia/static/css/` with a token layer, per-surface base layers, a shared
  components layer, and per-page files. Served by the existing WhiteNoise
  `CompressedManifestStaticFilesStorage` (same path that already hashes
  `brand/` + `vendor/`).
- **Single `tokens.css`.** Rejected: the sklad and web `:root` sets both define
  `--line` with **different values** (`#d9dcd9` vs `#d9dad3`); one file would
  clobber one surface. Kept as two files.
- **`@import` between layers.** Rejected: the manifest storage's `HashedFilesMixin`
  rewrites `url()`/`@import` during `collectstatic`; import chains are fragile and
  serialize requests. Use multiple `<link>` tags instead.
- **Leave inline.** Rejected: the whole point of the restructure.

## Choice

```
kasia/static/css/
  tokens-sklad.css   sklad :root only (--accent, --fg*, --line #d9dcd9, --ok*, --warn, --error, radius, fonts)
  tokens-web.css     web  :root only (--green, --brandbar, --ink*, --tint*, --line #d9dad3, --radius, --pill, --maxw)
  base-sklad.css     sklad shell/sidebar + shared sklad classes
  base-web.css       public nav/hero/bands/buttons + shared public classes
  components/        kpis · tables · dialogs · filters · forms  (shared)
  pages/             per-screen rules from the 17 extra_head blocks (genuinely unique only)
```

- `base.html` / `web/base.html` `<link>` their token + base + component files;
  child templates' `{% block extra_head %}` **`<link>`s** `pages/<screen>.css`
  (never inline `<style>`, never `@import`).
- **Shared CSS class names and JS/HTMX hooks are unchanged** — the stable
  contract in `design-system.md` is preserved verbatim.
- PDF (`inventory/dodaci_list.html`, `recipe_pdf.html`) and e-mail templates
  **keep their inline styles** — WeasyPrint/inbox documents, out of the
  web-chrome system.

## Rationale

Two token files remove the only real collision risk while keeping one source of
truth per surface. `<link>`-only loading sidesteps the manifest's `@import`
rewriting. The visual contract is untouched; this is a move, not a redesign.

## Consequences

- `.claude/rules/design-system.md` updated: tokens now in `tokens-*.css`;
  per-screen CSS is a linked `pages/*.css`; `@import` forbidden in app CSS;
  class-name + hook contract preserved.
- Tests must not depend on the static manifest: a repo-root `conftest.py`
  overrides `STORAGES["staticfiles"]` to `FileSystemStorage` for the test
  session (templates now emit `{% static 'css/...' %}` widely).
- `collectstatic` at Docker build already runs before gunicorn — runtime
  `{% static %}` is fine on prod.
- Any visual discrepancy surfaced during extraction is logged in
  [`../refactors/0068-restructure-discrepancies.md`](../refactors/0068-restructure-discrepancies.md)
  and approved before landing. No schema/migration change.
