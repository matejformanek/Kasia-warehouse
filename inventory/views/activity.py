"""Aktivita — the vlastník-only operator screen-usage page (per 0077).

Reads the append-only ``ScreenVisit`` log written by
``inventory.middleware.ScreenVisitMiddleware``: per-user summary (last visit,
7/30-day counts), top screens over 30 days, and a filterable, paginated
recent-visits list with Czech screen labels.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

from ..models import ScreenVisit
from ._shared import _require_vlastnik

# Czech labels for the primary screens; an unmapped url_name renders raw.
SCREEN_LABELS = {
    "home": "Přehled",
    "branch_dashboard": "Přehled pobočky",
    "catalogue_index": "Katalog",
    "product_detail": "Detail produktu",
    "product_create": "Nový produkt",
    "product_edit": "Úprava produktu",
    "recipe_pdf": "Receptura (PDF)",
    "prijem_create": "Příjem",
    "prijem_confirm": "Potvrzení plánovaného příjmu",
    "vydej_create": "Výdej",
    "movement_history": "Historie",
    "movement_saved": "Uložený pohyb",
    "movement_edit": "Úprava pohybu",
    "inventura_edit": "Inventura",
    "stock_adjust_edit": "Úprava stavu",
    "mixing_job_index": "Míchání — historie",
    "mixing_job_create": "Míchání",
    "mixing_job_detail": "Míchání — detail",
    "xls_import_upload": "Import receptur (XLS)",
    "dodaci_list_index": "Dodací listy",
    "dodaci_list_detail": "Dodací list — detail",
    "dodaci_list_pdf": "Dodací list (PDF)",
    "email_log_index": "E-maily",
    "email_log_detail": "E-mail — detail",
    "settings_edit": "Nastavení",
    "support": "Podpora",
    "supplier_index": "Dodavatelé",
    "customer_index": "Odběratelé",
    "branch_index": "Pobočky",
    "user_index": "Uživatelé",
    "activity_index": "Aktivita",
    "password_change": "Změna hesla",
    "password_change_done": "Změna hesla — hotovo",
}


def _label(url_name: str) -> str:
    return SCREEN_LABELS.get(url_name, url_name)


@require_GET
def activity_index(request):
    _require_vlastnik(request)

    now = timezone.now()
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    users = list(
        get_user_model()
        .objects.filter(is_active=True)
        .annotate(
            last_visit=Max("screen_visits__created_at"),
            visits_7d=Count(
                "screen_visits", filter=Q(screen_visits__created_at__gte=since_7d)
            ),
            visits_30d=Count(
                "screen_visits", filter=Q(screen_visits__created_at__gte=since_30d)
            ),
        )
        .order_by(F("last_visit").desc(nulls_last=True), "email")
    )

    top_screens = [
        {
            "label": _label(row["url_name"]),
            "url_name": row["url_name"],
            "count": row["count"],
        }
        for row in ScreenVisit.objects.filter(created_at__gte=since_30d)
        .values("namespace", "url_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:15]
    ]

    # Filter values are validated against what's actually in the table.
    screen_values = list(
        ScreenVisit.objects.values_list("url_name", flat=True)
        .distinct()
        .order_by("url_name")
    )
    user_ids = {str(u.pk) for u in users}

    filter_user = request.GET.get("user") or ""
    filter_screen = request.GET.get("screen") or ""
    if filter_user not in user_ids:
        filter_user = ""
    if filter_screen not in screen_values:
        filter_screen = ""

    qs = ScreenVisit.objects.select_related("user")
    if filter_user:
        qs = qs.filter(user_id=filter_user)
    if filter_screen:
        qs = qs.filter(url_name=filter_screen)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    visits = list(page_obj.object_list)
    for visit in visits:
        visit.screen_label = _label(visit.url_name)

    page_params = {}
    if filter_user:
        page_params["user"] = filter_user
    if filter_screen:
        page_params["screen"] = filter_screen
    page_querystring = urlencode(page_params)

    return render(
        request,
        "inventory/activity_index.html",
        {
            "users": users,
            "top_screens": top_screens,
            "visits": visits,
            "page_obj": page_obj,
            "page_querystring": page_querystring,
            "total": paginator.count,
            "screen_choices": [(v, _label(v)) for v in screen_values],
            "filter_user": filter_user,
            "filter_screen": filter_screen,
        },
    )
