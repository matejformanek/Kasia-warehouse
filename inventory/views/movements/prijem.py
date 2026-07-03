"""Příjem: create, confirm planned arrival, cancel planned."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from ...forms import (
    MovementLineFormSet,
    PrijemForm,
    assert_no_future_date,
)
from ...models import (
    Movement,
    Supplier,
)
from ...services import (
    apply_movement,
    confirm_planned_receipt,
)
from .._shared import _safe_next
from ._shared import (
    _build_lines,
    _push_validation_error_to_formset,
    _recent_movements_for_form,
)


@require_http_methods(["GET", "POST"])
def prijem_create(request):
    if request.method == "POST":
        form = PrijemForm(request.POST, user=request.user)
        formset = MovementLineFormSet(request.POST, prefix="lines")
        if form.is_valid() and formset.is_valid():
            try:
                assert_no_future_date(form.cleaned_data["date_issued"])
            except ValidationError as exc:
                form.add_error("date_issued", exc)
            else:
                lines = _build_lines(formset)
                if not lines:
                    formset._non_form_errors = formset.error_class(
                        ["Pohyb musí mít alespoň jednu položku."]
                    )
                else:
                    from datetime import date as _date

                    exp = form.cleaned_data.get("expected_on")
                    is_planned = exp is not None and exp > _date.today()
                    if is_planned:
                        # Planned príjem (objednávka) — date_issued stays today
                        # (keeps the not-null field + ordering valid); the
                        # promised arrival lives in expected_on. No stock now.
                        movement = Movement(
                            branch=form.cleaned_data["branch"],
                            kind=Movement.Kind.PRIJEM,
                            status=Movement.Status.PLANNED,
                            date_issued=_date.today(),
                            expected_on=exp,
                            dodavatel=form.cleaned_data.get("dodavatel"),
                            note=form.cleaned_data.get("note", ""),
                        )
                    else:
                        movement = Movement(
                            branch=form.cleaned_data["branch"],
                            kind=Movement.Kind.PRIJEM,
                            date_issued=form.cleaned_data["date_issued"],
                            dodavatel=form.cleaned_data["dodavatel"],
                            note=form.cleaned_data.get("note", ""),
                        )
                    try:
                        mv = apply_movement(
                            movement=movement, lines=lines, user=request.user
                        )
                    except ValidationError as exc:
                        _push_validation_error_to_formset(exc, formset)
                    else:
                        if is_planned:
                            messages.success(
                                request,
                                "Plánovaný příjem uložen — sklad se změní po"
                                " potvrzení příjezdu.",
                            )
                        else:
                            messages.success(
                                request,
                                f"Příjem byl uložen ({mv.lines.count()} pol.).",
                            )
                        return redirect("inventory:movement_saved", pk=mv.pk)
    else:
        form = PrijemForm(user=request.user)
        formset = MovementLineFormSet(prefix="lines")

    return render(
        request,
        "inventory/prijem_form.html",
        {
            "form": form,
            "formset": formset,
            "recent_movements": _recent_movements_for_form(
                request.user, Movement.Kind.PRIJEM
            ),
        },
    )


@require_http_methods(["GET", "POST"])
def prijem_confirm(request, pk: int):
    """Confirm arrival of a PLANNED príjem (objednávka) per 0059.

    All logged-in users. GET renders the planned lines with editable
    quantities (prefilled with the ordered amount), an actual-arrival date
    (default today), and an optional supplier picker. POST maps each line's
    posted quantity into `line_qty_by_id` and calls `confirm_planned_receipt`
    (a line set to 0 is dropped; negative stock surfaces here).
    """
    from datetime import date as _date

    movement = get_object_or_404(
        Movement.objects.select_related("branch", "dodavatel"), pk=pk
    )
    if movement.status != Movement.Status.PLANNED:
        messages.info(request, "Tento příjem už byl potvrzen nebo zrušen.")
        return redirect("inventory:movement_saved", pk=movement.pk)

    lines = list(movement.lines.select_related("product").order_by("id"))
    suppliers = Supplier.objects.filter(
        is_active=True, is_internal=False
    ).order_by("name")

    if request.method == "POST":
        line_qty_by_id: dict[int, Decimal] = {}
        errors: list[str] = []
        for line in lines:
            raw = (request.POST.get(f"qty_{line.pk}") or "").strip().replace(
                ",", "."
            )
            if raw == "":
                line_qty_by_id[line.pk] = line.quantity_kg
                continue
            try:
                line_qty_by_id[line.pk] = Decimal(raw)
            except (InvalidOperation, ValueError):
                errors.append(f"{line.product.name_cs}: neplatné množství: {raw}")

        as_of_raw = (request.POST.get("as_of") or "").strip()
        as_of = None
        if as_of_raw:
            try:
                as_of = _date.fromisoformat(as_of_raw)
            except ValueError:
                errors.append(f"Neplatné datum příjezdu: {as_of_raw}")

        supplier = None
        supplier_pk = (request.POST.get("supplier") or "").strip()
        if supplier_pk:
            supplier = suppliers.filter(pk=supplier_pk).first()

        if not errors:
            try:
                confirm_planned_receipt(
                    movement=movement,
                    line_qty_by_id=line_qty_by_id,
                    supplier=supplier,
                    as_of=as_of,
                    user=request.user,
                )
            except ValidationError as exc:
                errors.extend(
                    exc.messages if hasattr(exc, "messages") else [str(exc)]
                )
            else:
                messages.success(
                    request,
                    "Příjem potvrzen — stav skladu byl navýšen.",
                )
                return redirect("inventory:movement_saved", pk=movement.pk)

        for err in errors:
            messages.error(request, err)

    return render(
        request,
        "inventory/prijem_confirm.html",
        {
            "movement": movement,
            "lines": lines,
            "suppliers": suppliers,
            "today": _date.today(),
        },
    )


@require_POST
def prijem_plan_cancel(request, pk: int):
    """Cancel (hard-delete) a PLANNED príjem per 0059. It never touched
    stock, so a plain delete (cascading its lines) is safe. All logged-in
    users."""
    movement = get_object_or_404(Movement, pk=pk)
    if movement.status != Movement.Status.PLANNED:
        messages.error(request, "Zrušit lze pouze plánovaný příjem.")
        return redirect("inventory:movement_history")
    movement.delete()
    messages.success(request, "Plánovaný příjem zrušen.")
    return redirect(_safe_next(request, reverse("inventory:movement_history")))
