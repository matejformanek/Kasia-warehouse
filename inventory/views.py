"""HTMX-driven views for the operator-facing surface (Pass 3a).

Auth: LoginRequiredMiddleware redirects anonymous users to /login/;
views need no decorator unless they intentionally opt out.

Pass 3a screens:
- home — landing after login (placeholder until screen 02 in Pass 3c)
- prijem_create — screen 06
- vydej_create — screen 07 (with HTMX stock-cap warning)
- movement_saved — landing page after a successful create
- line_row_partial — HTMX add-row endpoint
- stock_warn_partial — HTMX live stock-cap check for výdej
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .forms import (
    MovementLineForm,
    MovementLineFormSet,
    PrijemForm,
    VydejForm,
    assert_no_future_date,
)
from .models import DodaciList, Movement, MovementLine, Product, Stock
from .services import apply_movement


@require_GET
def home(request):
    """Post-login landing. Pass 3c will replace with the dashboard."""
    return render(request, "inventory/home.html")


@require_GET
def movement_saved(request, pk: int):
    """Confirmation page after a successful create."""
    movement = get_object_or_404(
        Movement.objects.select_related("branch", "odberatel", "dodavatel"),
        pk=pk,
    )
    dodaci_list = DodaciList.objects.filter(movement=movement).first()
    return render(
        request,
        "inventory/movement_saved.html",
        {"movement": movement, "dodaci_list": dodaci_list},
    )


# ---------------------------------------------------------------------------
# Příjem (screen 06)
# ---------------------------------------------------------------------------


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
        {"form": form, "formset": formset},
    )


# ---------------------------------------------------------------------------
# Výdej (screen 07)
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def vydej_create(request):
    if request.method == "POST":
        form = VydejForm(request.POST, user=request.user)
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
                    movement = Movement(
                        branch=form.cleaned_data["branch"],
                        kind=Movement.Kind.VYDEJ,
                        date_issued=form.cleaned_data["date_issued"],
                        odberatel=form.cleaned_data["odberatel"],
                        note=form.cleaned_data.get("note", ""),
                    )
                    try:
                        mv = apply_movement(
                            movement=movement, lines=lines, user=request.user
                        )
                    except ValidationError as exc:
                        _push_validation_error_to_formset(exc, formset)
                    else:
                        messages.success(
                            request,
                            f"Výdej byl uložen ({mv.lines.count()} pol.).",
                        )
                        return redirect("inventory:movement_saved", pk=mv.pk)
    else:
        form = VydejForm(user=request.user)
        formset = MovementLineFormSet(prefix="lines")

    return render(
        request,
        "inventory/vydej_form.html",
        {"form": form, "formset": formset},
    )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@require_GET
def line_row_partial(request):
    """Render one empty MovementLineForm row. The caller passes the
    new index via ?index=N so the prefix matches the formset."""
    try:
        index = int(request.GET.get("index", 0))
    except ValueError:
        index = 0
    form = MovementLineForm(prefix=f"lines-{index}")
    return render(
        request,
        "inventory/_line_row.html",
        {"line_form": form, "index": index, "is_partial": True},
    )


@require_GET
def stock_warn_partial(request):
    """Live stock-cap check for výdej.

    Query params: branch (id), product (id), qty (decimal).
    Returns a small HTML fragment with the warning, or empty if OK.
    """
    branch_id = request.GET.get("branch")
    product_id = request.GET.get("product")
    qty_raw = request.GET.get("qty", "")

    if not branch_id or not product_id or not qty_raw:
        return HttpResponse("")

    try:
        qty = Decimal(qty_raw)
    except (InvalidOperation, ValueError):
        return HttpResponse("")

    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        return HttpResponse("")

    stock = Stock.objects.filter(branch_id=branch_id, product_id=product_id).first()
    on_hand = stock.quantity if stock else Decimal("0.000")
    over = qty > on_hand
    return render(
        request,
        "inventory/_stock_warn.html",
        {"on_hand": on_hand, "qty": qty, "over": over, "product": product},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_lines(formset) -> list[MovementLine]:
    lines: list[MovementLine] = []
    for line_form in formset:
        data = line_form.cleaned_data
        if not data or data.get("DELETE"):
            continue
        if data.get("product") is None or data.get("quantity_kg") in (None, ""):
            continue
        lines.append(
            MovementLine(
                product=data["product"],
                quantity_kg=data["quantity_kg"],
                sarze=data.get("sarze", "") or "",
                expiry=data.get("expiry"),
                note=data.get("note", "") or "",
            )
        )
    return lines


def _push_validation_error_to_formset(exc: ValidationError, formset) -> None:
    """Surface a service-layer ValidationError as a non-form error so
    the operator sees it above the line table."""
    msgs: list[str] = []
    if hasattr(exc, "message_dict"):
        for field, field_msgs in exc.message_dict.items():
            for msg in field_msgs:
                msgs.append(f"{field}: {msg}")
    else:
        msgs.extend(exc.messages)
    formset._non_form_errors = formset.error_class(msgs)
