---
name: kasia-sklad-frontend
description: >-
  Orientation + guardrails for editing the Kasia warehouse frontend — any
  Django template under kasia/templates/** or CSS under kasia/static/css/**.
  Use this WHENEVER you are about to add or change a sklad/public screen,
  partial, template comment, or stylesheet in this repo — even for a
  one-line tweak — because several mistakes here render silently wrong (no
  error, no failing test elsewhere) and have shipped to prod: multi-line
  `{# #}` comments printing as page text, `floatformat` blanking number
  inputs, inline `<style>`/`@import` breaking collectstatic, renamed locked
  hooks, and un-scoped branch data leaking to obsluha. Load it before you
  touch templates or CSS, not after something looks off.
---

# Editing the Kasia sklad/public frontend

This repo has a settled, layered frontend (decisions 0068–0073). The rules of
the road live in two files — **read them, this skill just routes you and lists
the traps that keep recurring**:

- **`.claude/rules/frontend-and-templates.md`** — the architecture map + the
  silently-wrong gotchas (source of truth for *this* skill).
- **`.claude/rules/design-system.md`** — the visual contract: locked class
  names, JS/HTMX hooks, the exact CSS `<link>` order, the 1-dp quantity rules.

Do not restate or fork those — link to them and follow them.

## The traps that keep biting (check every time)

1. **Multi-line `{# … #}` comment → renders as visible text.** Django's lexer
   only matches `{# #}` on one line. For anything longer use
   `{% comment %}…{% endcomment %}`. This reached prod twice.
2. **`floatformat` inside a `type="number"` `value=` → blank field.** The `cs`
   locale emits a comma the input rejects. Prefill with `|unlocalize` or a
   `ROUND_HALF_UP` 1-dp value; use `floatformat:1` only in display cells.
3. **Inline `<style>` or `@import` → breaks the manifest pipeline** (0069).
   `<link>` from `base.html` (component) or `{% block extra_head %}` (page CSS).
   Only PDF/e-mail/`404`/`500` templates may inline.
4. **Renaming a locked class or JS/HTMX hook is a new decision** (design-system.md
   § "Keep stable"). Restyle freely; do not rename `.sub-head`, `table.lines`,
   `.row-link[data-href]`, `#lines-body`, `data-filter-rows`, `.js-confirm`, etc.
5. **Branch scoping.** Obsluha see only their own branch (movements, dodáky,
   Přehled, inventura per 0073). Any new view/template branch that shows branch
   data must 403 an obsluha reaching another branch or a cross-branch roll-up.

## Where to put things

- **Template:** `kasia/templates/inventory/<screen>.html` (sklad, `extends "base.html"`)
  or `kasia/templates/web/<page>.html` (public). Fragments: `_partial.html`.
- **View:** `inventory/views/<area>.py` — add next to its siblings, not a monolith.
- **CSS:** per-screen `kasia/static/css/pages/<screen>.css`, `<link>`ed from the
  template's `{% block extra_head %}`. Shared sklad look → `components/*.css` in
  the fixed order (design-system.md). Reference `var(--token)`, never raw hex.

## Before you're done — verify, don't just read

Static reading missed the multi-line comment twice. Always:

```
uv run pytest inventory/tests/test_template_hygiene.py   # comments + inline CSS guard
uv run python manage.py collectstatic --noinput          # if you touched CSS
```

Then render the page for real (`make up`, or the Django test client / `curl`) and
confirm no stray `{#`/`#}`/`{% … %}` shows on the page and the layout holds. Finish
with `uv run pytest -q`, `uv run ruff check .`, `uv run python manage.py check`.
