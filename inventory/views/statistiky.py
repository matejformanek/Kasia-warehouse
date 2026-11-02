"""Statistiky — vlastník-only analytics screen (per 0107).

Full-page GET only. Filters live in the query string so a view is shareable;
the panels come from the registry in ``inventory.services.analytics``.
"""

from __future__ import annotations

from datetime import date

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

from accounts.permissions import require_vlastnik

from ..services import analytics


def _parse_date(raw: str):
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_filters(request, branches, products):
    today = timezone.localdate()
    preset = request.GET.get("rozsah") or "30d"
    if preset not in dict(analytics.RANGES):
        preset = "30d"
    date_from, date_to = analytics.resolve_range(
        preset,
        today,
        _parse_date(request.GET.get("od") or ""),
        _parse_date(request.GET.get("do") or ""),
    )
    granularity = request.GET.get("gran") or "mesic"
    if granularity not in analytics.GRANULARITIES:
        granularity = "mesic"
    branch_ids = {str(b.pk): b.pk for b in branches}
    branch_id = branch_ids.get(request.GET.get("pobocka") or "")
    valid_products = {p.pk for p in products}
    product_ids = {
        int(raw)
        for raw in request.GET.getlist("produkt")
        if raw.isdigit() and int(raw) in valid_products
    }
    f = analytics.Filters(date_from, date_to, granularity, branch_id, tuple(sorted(product_ids)))
    return f, preset


@require_GET
def statistiky_index(request):
    require_vlastnik(request, "Statistiky vidí pouze vlastník.")

    branches = analytics.branch_choices()
    products = analytics.product_choices()
    f, preset = _parse_filters(request, branches, products)

    if request.GET.get("format") == "csv":
        panel = analytics.PANELS_BY_KEY.get(request.GET.get("panel") or "")
        if panel is None:
            raise Http404("Neznámý panel.")
        response = HttpResponse(
            analytics.panel_csv(panel, f), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="statistiky-{panel.key}-{f.date_from}-{f.date_to}.csv"'
        )
        return response

    section = request.GET.get("sekce") or "prehled"
    if section not in dict(analytics.SECTIONS):
        section = "prehled"

    panels = []
    for panel in analytics.PANELS:
        if panel.section != section:
            continue
        result = panel.query(f)
        panels.append(
            {
                "key": panel.key,
                "title": panel.title,
                "wide": panel.wide,
                "dom_id": f"stat-{panel.key}",
                "chart": {
                    "type": panel.chart,
                    "stacked": result.get("stacked", False),
                    "labels": result["labels"],
                    "datasets": result["datasets"],
                    "drill": result["drill"],
                    "explorer": result.get("explorer"),
                },
                "has_data": result["has_data"],
                "table": result["table"],
            }
        )

    query = [
        ("rozsah", preset),
        ("od", f.date_from.isoformat()),
        ("do", f.date_to.isoformat()),
        ("gran", f.granularity),
    ]
    if f.branch_id:
        query.append(("pobocka", f.branch_id))
    query += [("produkt", pk) for pk in f.product_ids]

    return render(
        request,
        "inventory/statistiky_index.html",
        {
            "section": section,
            "sections": analytics.SECTIONS,
            "ranges": analytics.RANGES,
            "granularities": analytics.GRANULARITIES.items(),
            "preset": preset,
            "date_from": f.date_from,
            "date_to": f.date_to,
            "granularity": f.granularity,
            "effective_granularity": analytics.effective_granularity(f),
            "branches": branches,
            "branch_id": f.branch_id,
            "products": products,
            "product_ids": set(f.product_ids),
            "panels": panels,
            "kpis": analytics.kpis(f) if section == "prehled" else [],
            "previous": f.previous(),
            "filter_querystring": urlencode(query),
        },
    )
