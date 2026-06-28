"""Public marketing site views (decisions 0050 + 0051; 0052 made Kontakt info-only).

Every view is decorated ``@login_not_required`` — the global
LoginRequiredMiddleware (decision 0020) has no include-level opt-out, so each
public view must exempt itself, exactly like ``healthz`` and the ``/navrhy/``
redirect in ``kasia/urls.py``. Every page is a plain GET render; the public
site stores no data (the contact form was removed in 0052), so ``web`` no
longer imports from ``inventory`` — it is a clean leaf app.
"""

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import reverse

from .content import COMPANY, EXECUTIVES, NAV, PROVOZOVNY


def _public_context(active: str, **extra) -> dict:
    """Shared context for every public page: company facts + nav state."""
    ctx = {"company": COMPANY, "nav": NAV, "active": active}
    ctx.update(extra)
    return ctx


@login_not_required
def home(request):
    return render(request, "web/home.html", _public_context("web:home"))


@login_not_required
def o_nas(request):
    return render(request, "web/o_nas.html", _public_context("web:o_nas"))


@login_not_required
def provozovny(request):
    return render(
        request,
        "web/provozovny.html",
        _public_context("web:provozovny", provozovny=PROVOZOVNY),
    )


@login_not_required
def kontakt(request):
    """Info-only Kontakt page (decision 0052): contact panel + executive
    directory + an embedded map. No form, no POST."""
    return render(
        request,
        "web/kontakt.html",
        _public_context("web:kontakt", executives=EXECUTIVES),
    )


# --- robots.txt + sitemap.xml (hand-rolled; no django.contrib.sitemaps) -----
# Right-sized for four pages per decision 0051.
@login_not_required
def robots_txt(request):
    return TemplateResponse(
        request, "web/robots.txt", content_type="text/plain"
    )


@login_not_required
def sitemap_xml(request):
    pages = ["web:home", "web:o_nas", "web:provozovny", "web:kontakt"]
    urls = [request.build_absolute_uri(reverse(name)) for name in pages]
    return TemplateResponse(
        request,
        "web/sitemap.xml",
        {"urls": urls},
        content_type="application/xml",
    )
