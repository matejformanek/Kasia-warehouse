"""Template-hygiene guards — mechanical enforcement of the frontend rules.

These catch a class of mistakes that render silently-wrong (no exception, no
test failure elsewhere) and have bitten us more than once:

- **Multi-line ``{# … #}`` comments.** Django's template lexer matches ``{#.*?#}``
  *without* DOTALL, so a comment that spans two lines is NOT recognised — it is
  emitted verbatim onto the page as visible text. Use single-line ``{# … #}`` or
  ``{% comment %}…{% endcomment %}`` instead. (See
  ``.claude/rules/frontend-and-templates.md``.)
- **Inline ``<style>`` / ``@import`` in web-served templates.** Per decision 0069
  (CSS externalization) all sklad/public CSS is ``<link>``ed, never inlined and
  never ``@import``ed (the manifest storage rewrites ``url()``/``@import``). Only
  the self-contained PDF / e-mail / error templates are allowed to inline styles.

Keeping these as tests (not just prose) means CI / ``make test`` fails the moment
one is reintroduced, instead of the mistake reaching prod.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "kasia" / "templates"

# Templates deliberately allowed to carry an inline <style> block: the
# self-contained WeasyPrint PDFs, inbox e-mails, and the error pages, which must
# not depend on the static pipeline. Per .claude/rules/design-system.md.
_INLINE_STYLE_ALLOWED = {
    "inventory/dodaci_list.html",
    "inventory/recipe_pdf.html",
    "404.html",
    "500.html",
}

# Django lexer: single-line {# #} only (no DOTALL). Strip well-formed comments;
# any leftover {# or #} means a comment spans lines and will render as text.
_SINGLE_LINE_COMMENT = re.compile(r"\{#.*?#\}")


def _all_templates() -> list[Path]:
    return sorted(_TEMPLATES_DIR.rglob("*.html"))


def _rel(path: Path) -> str:
    return path.relative_to(_TEMPLATES_DIR).as_posix()


@pytest.mark.parametrize("template", _all_templates(), ids=_rel)
def test_no_multiline_django_comments(template: Path) -> None:
    """A {# #} comment must open and close on the same line, else Django emits
    it as literal page text."""
    stripped = _SINGLE_LINE_COMMENT.sub("", template.read_text(encoding="utf-8"))
    leftovers = [
        i + 1
        for i, line in enumerate(stripped.splitlines())
        if "{#" in line or "#}" in line
    ]
    assert not leftovers, (
        f"{_rel(template)}: multi-line '{{# #}}' comment near line(s) {leftovers}. "
        "Django only strips single-line {# #}; a multi-line one renders as visible "
        "text. Use {% comment %}…{% endcomment %} or keep it on one line."
    )


@pytest.mark.parametrize("template", _all_templates(), ids=_rel)
def test_no_inline_style_or_import(template: Path) -> None:
    """No inline <style> / @import in web-served templates (decision 0069)."""
    text = template.read_text(encoding="utf-8")
    rel = _rel(template)
    if "@import" in text:
        pytest.fail(
            f"{rel}: '@import' is forbidden — the manifest storage rewrites it. "
            "Add a <link> in base.html or {% block extra_head %} instead."
        )
    if "<style" in text and rel not in _INLINE_STYLE_ALLOWED:
        pytest.fail(
            f"{rel}: inline <style> is forbidden (decision 0069) — move it to a "
            "kasia/static/css/ file and <link> it. Only PDF/e-mail/error templates "
            "may inline styles."
        )
