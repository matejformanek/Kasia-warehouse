"""Podpora / feedback."""

from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import (
    FeedbackForm,
)
from ..models import (
    Feedback,
)
from ..services import send_feedback_notification


def support_view(request):
    """Single-page Podpora: docs accordions + submit form + history.

    All logged-in users can submit and see the full list. Vlastník-only
    resolved toggle lives on `feedback_toggle_view`.
    """
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            f = form.save(commit=False)
            f.created_by = request.user
            f.save()
            # Notify the admin (per 0079). Scheduled on_commit so SMTP latency
            # (up to the 10s timeout) stays off the request; send_and_log logs
            # FAILED and never re-raises, so a mail outage can't block the save.
            transaction.on_commit(lambda: send_feedback_notification(f))
            messages.success(
                request, "Děkujeme — vaše hlášení bylo uloženo."
            )
            return redirect("inventory:support")
    else:
        form = FeedbackForm()
    # Per 0059-part-B: resolved (vyřešená) reports are hidden by default (the
    # list grows long and slows the page). Open reports always render; resolved
    # rows are fetched only when explicitly requested via ?show_resolved=1.
    open_feedbacks = list(
        Feedback.objects.select_related("created_by")
        .filter(resolved_at__isnull=True)
        .order_by("-created_at")
    )
    resolved_count = Feedback.objects.filter(resolved_at__isnull=False).count()
    show_resolved = request.GET.get("show_resolved") == "1"
    resolved_feedbacks = []
    if show_resolved:
        resolved_feedbacks = list(
            Feedback.objects.select_related("created_by", "resolved_by")
            .filter(resolved_at__isnull=False)
            .order_by("-resolved_at", "-created_at")
        )
    return render(
        request,
        "inventory/support.html",
        {
            "form": form,
            "open_feedbacks": open_feedbacks,
            "resolved_feedbacks": resolved_feedbacks,
            "resolved_count": resolved_count,
            "show_resolved": show_resolved,
        },
    )


@require_POST
def feedback_toggle_view(request, pk: int):
    """Vlastník-only: flip a Feedback row between open and resolved."""
    if not request.user.is_vlastnik:
        messages.error(
            request,
            "Pouze vlastník může označovat hlášení jako vyřešená.",
        )
        return redirect("inventory:support")
    f = get_object_or_404(Feedback, pk=pk)
    if f.is_open:
        f.resolved_at = timezone.now()
        f.resolved_by = request.user
    else:
        f.resolved_at = None
        f.resolved_by = None
    f.save(update_fields=["resolved_at", "resolved_by"])
    return redirect("inventory:support")


# ---------------------------------------------------------------------------
# XLS recipe importer (per decision 0048)
# ---------------------------------------------------------------------------


