"""Dashboards: owner home + per-branch."""

from __future__ import annotations

from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from ..models import (
    Branch,
    DodaciList,
    DodaciListEmailLog,
    Movement,
    Stock,
)
from ..services import (
    low_stock_rows,
    reserved_kg,
    threshold_for,
)
from ._shared import _dl_failed_at_current_version


@require_GET
def home(request):
    """Post-login landing.

    Role routing per screens/02 + screens/03:
    - Branch staff (`obsluha` group, has `user.branch` FK) redirect
      to `/pobocka/<branch.code>/` (screen 03).
    - Everyone else (vlastník / superuser / unassigned) lands on
      the owner dashboard below (screen 02).
    """
    if request.user.is_obsluha and request.user.branch_id:
        return redirect(
            "inventory:branch_dashboard", code=request.user.branch.code
        )

    from django.db.models import Sum

    branches = list(Branch.objects.filter(is_active=True).order_by("code"))

    # "Dochází zboží" rows per 0043 + 0044 (same low_stock_rows() that feeds
    # the daily digest), grouped per branch into vyprodáno / dochází / objednáno.
    # Objednáno reuses the existing PLANNED-příjem order overlay (0057) — a row
    # with an open order sinks into its own "on the way" group.
    low_stock = low_stock_rows()
    rows_by_branch = {
        b.pk: {"empty": [], "low": [], "ordered": []} for b in branches
    }
    for r in low_stock:
        grp = rows_by_branch.get(r.branch.pk)
        if grp is None:
            continue
        if r.ordered_kg is not None:
            grp["ordered"].append(r)
        elif r.effective <= 0:
            grp["empty"].append(r)
        else:
            grp["low"].append(r)

    branch_panels = []
    for b in branches:
        stocks = list(
            Stock.objects.filter(branch=b, quantity__gt=0)
            .select_related("product")
            .order_by("-quantity")
        )
        total_mass = (
            Stock.objects.filter(branch=b).aggregate(s=Sum("quantity"))["s"]
            or Decimal("0.000")
        )
        recent_movements = list(
            Movement.objects.filter(branch=b, status=Movement.Status.DONE)
            .select_related("odberatel", "dodavatel", "created_by")
            .prefetch_related("lines__product")
            .order_by("-date_issued", "-id")[:5]
        )
        branch_dodaky = list(
            DodaciList.objects.filter(branch=b)
            .select_related("odberatel")
            .order_by("-date_issued", "-id")[:5]
        )
        grp = rows_by_branch[b.pk]
        branch_panels.append(
            {
                "branch": b,
                "product_count": len(stocks),
                "total_mass": total_mass,
                "top_stocks": stocks[:5],
                "recent_movements": recent_movements,
                "recent_dodaky": branch_dodaky,
                "empty_rows": grp["empty"],
                "low_rows": grp["low"],
                "ordered_rows": grp["ordered"],
            }
        )

    def _breakdown(key):
        parts = [
            f"{b.code} {len(rows_by_branch[b.pk][key])}"
            for b in branches
            if rows_by_branch[b.pk][key]
        ]
        return " · ".join(parts)

    # K vyřešení: failed sends whose dodák hasn't yet been re-sent
    # successfully at the current version. Uses the same rule as the
    # per-detail banner in `dodaci_list_detail` via
    # `_dl_failed_at_current_version`.
    failed_dodaky = []
    for dl in DodaciList.objects.prefetch_related("email_logs"):
        logs = list(dl.email_logs.all())
        if not _dl_failed_at_current_version(dl, logs):
            continue
        logs_at_current = [log for log in logs if log.version == dl.current_version]
        last_failed = max(
            (
                log
                for log in logs_at_current
                if log.status == DodaciListEmailLog.Status.FAILED
            ),
            key=lambda log: log.sent_at,
        )
        failed_dodaky.append({"dodaci_list": dl, "last_failed": last_failed})

    # Recently edited dodáky (current_version > 1), latest first, top 5.
    edited_dodaky = list(
        DodaciList.objects.select_related("branch", "odberatel")
        .filter(current_version__gt=1)
        .order_by("-id")[:5]
    )

    # Due planned příjmy (per 0066): a PLANNED objednávka whose promised arrival
    # date has arrived (or passed) is a K-vyřešení task — confirm the receipt.
    today = timezone.localdate()
    due_planned = list(
        Movement.objects.filter(
            status=Movement.Status.PLANNED,
            kind=Movement.Kind.PRIJEM,
            expected_on__lte=today,
        )
        .select_related("branch", "dodavatel")
        .prefetch_related("lines__product")
        .order_by("expected_on", "id")
    )
    for mv in due_planned:
        mv.total_kg = sum(
            (line.quantity_kg for line in mv.lines.all()), Decimal("0.000")
        )

    # KPI overview strip (decision 0054, per-branch grouped Přehled): the
    # attention buckets, with a per-branch breakdown sub-label.
    kpi_empty = sum(len(rows_by_branch[b.pk]["empty"]) for b in branches)
    kpi_low = sum(len(rows_by_branch[b.pk]["low"]) for b in branches)
    kpi_ordered = sum(len(rows_by_branch[b.pk]["ordered"]) for b in branches)

    return render(
        request,
        "inventory/home.html",
        {
            "branch_panels": branch_panels,
            "failed_dodaky": failed_dodaky,
            "edited_dodaky": edited_dodaky,
            "due_planned": due_planned,
            "can_order": request.user.is_vlastnik,
            "to_resolve_count": (
                len(failed_dodaky) + len(edited_dodaky) + len(due_planned)
            ),
            "kpi_empty": kpi_empty,
            "kpi_low": kpi_low,
            "kpi_ordered": kpi_ordered,
            "kpi_empty_breakdown": _breakdown("empty"),
            "kpi_low_breakdown": _breakdown("low"),
            "kpi_ordered_breakdown": _breakdown("ordered"),
        },
    )



@require_GET
def branch_dashboard(request, code: str):
    """Per-branch dashboard. Vlastník / superuser users may open any
    branch; obsluha users are scoped to their own branch (403 on the
    other branch).
    """
    branch = get_object_or_404(Branch, code=code)

    if request.user.is_obsluha:
        if request.user.branch_id != branch.pk:
            return HttpResponse(
                "Nemáte oprávnění zobrazit tuto pobočku.",
                content_type="text/plain; charset=utf-8",
                status=403,
            )

    stocks_qs = (
        Stock.objects.filter(branch=branch)
        .select_related("product")
        .order_by("product__name_cs")
    )
    # Per 0063: the product search (`q`) is filtered client-side in the browser
    # over the rendered stock rows. The server only echoes the term back into
    # the input. KPIs are branch-wide (not search-scoped), so they are
    # unaffected.
    search = (request.GET.get("q") or "").strip()
    stocks = list(stocks_qs)
    # Threshold-aware status per 0043 + 0044. Replaces the old hardcoded
    # `< 1 kg` near-empty marker.
    stock_rows = []
    for s in stocks:
        threshold = threshold_for(s.product, branch)
        reserved = reserved_kg(s.product, branch)
        effective = (s.quantity - reserved).quantize(Decimal("0.001"))
        if effective <= 0:
            status = "prazdne"
        elif threshold is not None and effective < threshold:
            status = "dochazi"
        else:
            status = ""
        stock_rows.append(
            {
                "stock": s,
                "reserved": reserved,
                "effective": effective,
                "threshold": threshold,
                "status": status,
            }
        )

    recent_movements = list(
        Movement.objects.filter(branch=branch, status=Movement.Status.DONE)
        .select_related("odberatel", "dodavatel", "created_by")
        .prefetch_related("lines__product")
        .order_by("-date_issued", "-id")[:15]
    )

    # Per-branch KPI header (decision 0054). Computed branch-wide, not over
    # the search-filtered list, so the numbers stay stable while searching.
    from django.db.models import Sum

    kpi_products = Stock.objects.filter(branch=branch, quantity__gt=0).count()
    kpi_total_mass = Stock.objects.filter(branch=branch).aggregate(
        s=Sum("quantity")
    )["s"] or Decimal("0.000")
    kpi_low_stock = sum(
        1 for r in low_stock_rows() if r.branch.pk == branch.pk
    )

    return render(
        request,
        "inventory/branch_dashboard.html",
        {
            "branch": branch,
            "stocks": stocks,
            "stock_rows": stock_rows,
            "recent_movements": recent_movements,
            "search": search,
            "kpi_products": kpi_products,
            "kpi_total_mass": kpi_total_mass,
            "kpi_low_stock": kpi_low_stock,
        },
    )


# ---------------------------------------------------------------------------
# Příjem (screen 06)
# ---------------------------------------------------------------------------


