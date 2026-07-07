"""E-mailová schránka (outbox) — the vlastník-only „E-maily" Správa page (0075).

Lists every business e-mail the app sent (dodák / low-stock alert / SMTP-test),
its status, recipients, subject/body and reason, with a resend action. A dodák
row re-renders from the live DodaciList on resend; a non-dodák row re-sends its
stored subject/body/recipients. All three views are vlastník-gated.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_POST

from ..models import EmailLog
from ..services import render_dodaci_list_pdf, send_and_log, send_dodaci_list_email
from ._shared import _require_vlastnik, _safe_next


@require_GET
def email_log_index(request):
    _require_vlastnik(request)

    qs = EmailLog.objects.select_related("dodaci_list", "sent_by")

    status = request.GET.get("status") or ""
    category = request.GET.get("category") or ""
    if status in EmailLog.Status.values:
        qs = qs.filter(status=status)
    if category in EmailLog.Category.values:
        qs = qs.filter(category=category)

    total = EmailLog.objects.count()
    failed = EmailLog.objects.filter(status=EmailLog.Status.FAILED).count()

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    page_params = {}
    if status:
        page_params["status"] = status
    if category:
        page_params["category"] = category
    page_querystring = urlencode(page_params)

    status_tabs = [
        ("", "Vše", total),
        (
            EmailLog.Status.SENT,
            "Odesláno",
            EmailLog.objects.filter(status=EmailLog.Status.SENT).count(),
        ),
        (EmailLog.Status.FAILED, "Selhalo", failed),
    ]

    return render(
        request,
        "inventory/email_log_index.html",
        {
            "logs": list(page_obj.object_list),
            "page_obj": page_obj,
            "page_querystring": page_querystring,
            "total": total,
            "failed_count": failed,
            "status_tabs": status_tabs,
            "categories": EmailLog.Category.choices,
            "filter_status": status,
            "filter_category": category,
        },
    )


@require_GET
def email_log_detail(request, pk: int):
    _require_vlastnik(request)
    log = get_object_or_404(
        EmailLog.objects.select_related("dodaci_list", "sent_by"), pk=pk
    )
    return render(
        request,
        "inventory/email_log_detail.html",
        {
            "log": log,
            "recipient_list": [
                r.strip() for r in log.recipients.split(",") if r.strip()
            ],
        },
    )


@require_POST
def email_log_resend(request, pk: int):
    _require_vlastnik(request)
    log = get_object_or_404(EmailLog, pk=pk)

    if log.dodaci_list_id:
        # Dodák: re-render PDF + subject/body from the live DodaciList.
        pdf_bytes = render_dodaci_list_pdf(log.dodaci_list)
        new_log = send_dodaci_list_email(
            dodaci_list=log.dodaci_list,
            trigger_reason="ruční opětovné odeslání",
            pdf_bytes=pdf_bytes,
            sent_by=request.user,
        )
    else:
        # Non-dodák: re-send the stored subject/body/recipients as-is.
        new_log = send_and_log(
            category=log.category,
            trigger_reason="ruční opětovné odeslání",
            subject=log.subject,
            body=log.body,
            recipients=[r.strip() for r in log.recipients.split(",") if r.strip()],
            from_email=log.from_email or None,
            sent_by=request.user,
        )

    if new_log.status == EmailLog.Status.SENT:
        messages.success(request, f"E-mail odeslán ({new_log.recipients}).")
    else:
        messages.error(request, f"Odeslání selhalo: {new_log.error_message}")

    return redirect(
        _safe_next(request, reverse("inventory:email_log_detail", args=[log.pk]))
    )
