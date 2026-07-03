"""Planned inter-branch transfers."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import (
    PlannedTransferForm,
)
from ..models import (
    PlannedTransfer,
)
from ..services import (
    cancel_planned_transfer,
    execute_planned_transfer,
)


@require_GET
def planned_transfer_index(request):
    """List of plánované převody. Default: PLANNED only."""
    state = request.GET.get("state") or PlannedTransfer.State.PLANNED
    qs = (
        PlannedTransfer.objects.select_related(
            "source_branch", "target_branch", "product", "created_by"
        )
        .order_by("-scheduled_for", "-id")
    )
    if state in {s.value for s in PlannedTransfer.State}:
        qs = qs.filter(state=state)
    if request.user.is_obsluha and request.user.branch_id:
        qs = qs.filter(
            Q(source_branch_id=request.user.branch_id)
            | Q(target_branch_id=request.user.branch_id)
        )
    transfers = list(qs[:200])
    return render(
        request,
        "inventory/planned_transfer_index.html",
        {
            "transfers": transfers,
            "count": len(transfers),
            "filter_state": state,
        },
    )


def planned_transfer_create(request):
    if request.method == "POST":
        form = PlannedTransferForm(request.POST)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.created_by = request.user
            transfer.save()
            messages.success(
                request,
                f"Převod {transfer.product.name_cs} "
                f"{transfer.quantity_kg} kg naplánován.",
            )
            return redirect(
                "inventory:planned_transfer_detail", pk=transfer.pk
            )
    else:
        initial = {}
        if request.user.is_obsluha and request.user.branch_id:
            initial["source_branch"] = request.user.branch_id
        form = PlannedTransferForm(initial=initial)
    return render(
        request,
        "inventory/planned_transfer_form.html",
        {"form": form, "mode": "create"},
    )


@require_GET
def planned_transfer_detail(request, pk: int):
    transfer = get_object_or_404(
        PlannedTransfer.objects.select_related(
            "source_branch", "target_branch", "product", "created_by"
        ).prefetch_related("movements__branch"),
        pk=pk,
    )
    paired_movements = list(
        transfer.movements.select_related("branch").order_by("kind", "id")
    )
    return render(
        request,
        "inventory/planned_transfer_detail.html",
        {
            "transfer": transfer,
            "paired_movements": paired_movements,
        },
    )


@require_POST
def planned_transfer_execute(request, pk: int):
    transfer = get_object_or_404(PlannedTransfer, pk=pk)
    try:
        execute_planned_transfer(transfer, executed_by=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:planned_transfer_detail", pk=transfer.pk)
    messages.success(
        request,
        f"Převod proveden ({transfer.product.name_cs} "
        f"{transfer.quantity_kg} kg "
        f"{transfer.source_branch.code} → {transfer.target_branch.code}).",
    )
    return redirect("inventory:planned_transfer_detail", pk=transfer.pk)


@require_POST
def planned_transfer_cancel(request, pk: int):
    transfer = get_object_or_404(PlannedTransfer, pk=pk)
    try:
        cancel_planned_transfer(transfer, cancelled_by=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:planned_transfer_detail", pk=transfer.pk)
    messages.success(request, "Plánovaný převod zrušen.")
    return redirect("inventory:planned_transfer_detail", pk=transfer.pk)


# ---------------------------------------------------------------------------
# Plánované míchání (per 0044). Wraps plan_mixing_job.
# ---------------------------------------------------------------------------


