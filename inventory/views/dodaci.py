"""Dodaci listy: index, detail, PDF, resend, recipe PDF."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from ..models import (
    Branch,
    DodaciList,
    DodaciListEmailLog,
    Product,
)
from ..services import (
    render_dodaci_list_pdf,
    render_recipe_pdf,
    send_dodaci_list_email,
)
from ._shared import _dl_failed_at_current_version


def _deny_other_branch(request, branch_id):
    """403 if an obsluha tries to reach a dodák outside their own branch.
    Mirrors the `movement_history` / `branch_dashboard` own-branch scoping
    (decision 0040 §"obsluha sees only own-branch documents")."""
    if request.user.is_obsluha and request.user.branch_id != branch_id:
        return HttpResponse(
            "Nemáte oprávnění zobrazit tento dodací list.",
            status=403,
            content_type="text/plain; charset=utf-8",
        )
    return None


@require_GET
def dodaci_list_index(request):
    qs = DodaciList.objects.select_related("branch", "odberatel", "created_by")
    year = request.GET.get("year") or ""
    edited_only = request.GET.get("edited") == "1"

    # Branch scoping — obsluha is forced to own branch (0040); the branch
    # filter/dropdown is only for vlastník. Mirrors movement_history.
    if request.user.is_obsluha and request.user.branch_id:
        qs = qs.filter(branch_id=request.user.branch_id)
        branch_locked = request.user.branch
        branch_id = ""
    else:
        branch_locked = None
        branch_id = request.GET.get("branch") or ""
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

    if year:
        qs = qs.filter(year_issued=year)
    if edited_only:
        qs = qs.filter(current_version__gt=1)

    qs = qs.order_by("-date_issued", "-id")
    branches = list(Branch.objects.filter(is_active=True).order_by("code"))
    years = list(
        DodaciList.objects.order_by("-year_issued")
        .values_list("year_issued", flat=True)
        .distinct()
    )
    return render(
        request,
        "inventory/dodaci_list_index.html",
        {
            "dodaci_listy": qs,
            "count": qs.count(),
            "branches": branches,
            "years": years,
            "filter_branch": branch_id,
            "filter_year": year,
            "filter_edited": edited_only,
            "branch_locked": branch_locked,
        },
    )


# ---------------------------------------------------------------------------
# Detail dodacího listu (screen 09)
# ---------------------------------------------------------------------------


@require_GET
def dodaci_list_detail(request, cislo: str):
    dodaci_list = get_object_or_404(
        DodaciList.objects.select_related(
            "branch", "odberatel", "movement", "created_by"
        ),
        cislo=cislo,
    )
    denied = _deny_other_branch(request, dodaci_list.branch_id)
    if denied is not None:
        return denied
    lines = list(dodaci_list.movement.lines.select_related("product").order_by("id"))
    email_logs = list(
        dodaci_list.email_logs.order_by("sent_at", "id").all()
    )
    return render(
        request,
        "inventory/dodaci_list_detail.html",
        {
            "dodaci_list": dodaci_list,
            "movement": dodaci_list.movement,
            "lines": lines,
            "email_logs": email_logs,
            "last_status": email_logs[-1].status if email_logs else None,
            "current_version_unresolved": _dl_failed_at_current_version(
                dodaci_list, email_logs
            ),
        },
    )


@require_GET
def dodaci_list_pdf(request, cislo: str):
    dodaci_list = get_object_or_404(DodaciList, cislo=cislo)
    denied = _deny_other_branch(request, dodaci_list.branch_id)
    if denied is not None:
        return denied
    pdf_bytes = render_dodaci_list_pdf(dodaci_list)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{dodaci_list.cislo}.pdf"'
    return response


@require_GET
def recipe_pdf(request, pk: int):
    """Download a mixture's recipe sheet (ingredient amounts for the chosen
    batch size + mixing notes) as a PDF. The batch size comes from ``?qty=``
    (the "Spočítat dávku" box; defaults to 100 kg). 404 for non-mixtures or
    recipe-less mixtures."""
    product = get_object_or_404(Product, pk=pk)
    try:
        target_qty = Decimal(request.GET.get("qty", ""))
    except (InvalidOperation, ValueError):
        target_qty = None
    try:
        pdf_bytes = render_recipe_pdf(product, target_qty=target_qty)
    except ValueError as exc:
        raise Http404(str(exc)) from exc
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    slug = slugify(product.name_cs) or f"smes-{product.pk}"
    response["Content-Disposition"] = f'inline; filename="receptura-{slug}.pdf"'
    return response


@require_POST
def dodaci_list_resend(request, cislo: str):
    dodaci_list = get_object_or_404(DodaciList, cislo=cislo)
    denied = _deny_other_branch(request, dodaci_list.branch_id)
    if denied is not None:
        return denied
    pdf_bytes = render_dodaci_list_pdf(dodaci_list)
    log = send_dodaci_list_email(
        dodaci_list=dodaci_list,
        trigger_reason="ruční opětovné odeslání",
        pdf_bytes=pdf_bytes,
    )
    if log.status == DodaciListEmailLog.Status.SENT:
        messages.success(
            request, f"E-mail odeslán ({log.recipients})."
        )
    else:
        messages.error(
            request, f"Odeslání selhalo: {log.error_message}"
        )
    return redirect("inventory:dodaci_list_detail", cislo=cislo)


# ---------------------------------------------------------------------------
# Úprava pohybu (screen 11)
# ---------------------------------------------------------------------------


