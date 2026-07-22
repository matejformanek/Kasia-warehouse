"""Výdej (screen 07): create + the server-side overdraw pre-check."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from ...forms import (
    MovementLineFormSet,
    VydejForm,
)
from ...models import (
    Branch,
    DodaciList,
    Movement,
    MovementLine,
    Product,
    Stock,
)
from ...services import apply_movement
from ._shared import (
    _build_lines,
    _push_validation_error_to_formset,
    _recent_movements_for_form,
)


@require_http_methods(["GET", "POST"])
def vydej_create(request):
    overdraw_warnings: list[dict] = []
    if request.method == "POST":
        form = VydejForm(request.POST, user=request.user)
        formset = MovementLineFormSet(request.POST, prefix="lines")
        if form.is_valid() and formset.is_valid():
            lines = _build_lines(formset)
            if not lines:
                formset._non_form_errors = formset.error_class(
                    ["Pohyb musí mít alespoň jednu položku."]
                )
            else:
                branch = form.cleaned_data["branch"]
                overdraw_warnings = _compute_overdraw(branch, lines)
                if overdraw_warnings:
                    # Pre-check refusal: re-render with structured
                    # warning card per decision 0042. No service call.
                    pass
                else:
                    # Per 0086: výdej is always dated today (no date field).
                    movement = Movement(
                        branch=branch,
                        kind=Movement.Kind.VYDEJ,
                        date_issued=date.today(),
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
                        dl = DodaciList.objects.filter(movement=mv).first()
                        messages.success(
                            request,
                            f"Výdej byl uložen ({mv.lines.count()} pol.) — "
                            f"dodací list {dl.cislo if dl else ''}.",
                        )
                        if dl is not None:
                            return redirect(
                                "inventory:dodaci_list_detail", cislo=dl.cislo
                            )
                        return redirect("inventory:movement_saved", pk=mv.pk)
    else:
        form = VydejForm(user=request.user)
        formset = MovementLineFormSet(prefix="lines")

    # Embed the per-(branch, product) on-hand map so the výdej form can run
    # the live over-stock check purely in the browser — no htmx round-trip.
    # Basis is raw Stock.quantity (matches _compute_overdraw). Missing pairs
    # are absent here and treated as 0 by the JS. ~2 branches × ~12 products.
    stock_map: dict[str, dict[str, str]] = {}
    for s in Stock.objects.filter(
        branch__is_active=True, product__is_stock_tracked=True
    ).values("branch_id", "product_id", "quantity"):
        stock_map.setdefault(str(s["branch_id"]), {})[str(s["product_id"])] = (
            f'{s["quantity"]:.3f}'
        )

    # Per-branch inventura base URL, so the live over-stock block can offer a
    # "fix the stock" jump for the flagged products (per 0060's ?products=&next=
    # contract, same as míchání). Emitted for a vlastník (all active branches)
    # and — per 0073 — for an obsluha on their OWN branch only (they may run
    # inventura there). Obsluha's link therefore always targets their own branch.
    user = request.user
    branch_inventura: dict[str, str] = {}
    inventura_fix_url: str | None = None
    if getattr(user, "is_vlastnik", False):
        branch_inventura = {
            str(b.pk): reverse("inventory:inventura_edit", args=[b.code])
            for b in Branch.objects.filter(is_active=True)
        }
    elif getattr(user, "is_obsluha", False) and user.branch_id:
        own = reverse("inventory:inventura_edit", args=[user.branch.code])
        branch_inventura = {str(user.branch_id): own}
        inventura_fix_url = own

    return render(
        request,
        "inventory/vydej_form.html",
        {
            "form": form,
            "formset": formset,
            "overdraw_warnings": overdraw_warnings,
            "stock_map": stock_map,
            "branch_inventura": branch_inventura,
            "inventura_fix_url": inventura_fix_url,
            "recent_movements": _recent_movements_for_form(
                request.user, Movement.Kind.VYDEJ
            ),
        },
    )


def _compute_overdraw(branch: Branch, lines: list[MovementLine]) -> list[dict]:
    """Per decision 0042 — return all insufficient-stock lines for a
    výdej, so the operator can be prompted to correct the count with
    a direct link instead of just refused.

    For each line where requested > current stock at this branch,
    yields a dict:
        {product, branch, requested, current, shortfall}
    The list is empty when every line fits.

    Aggregates multiple lines of the same product within the same
    submission (a výdej can have two rows for the same product with
    different šarže) so the warning matches actual cumulative draw.
    """
    if not lines:
        return []
    requested_by_product: dict[int, Decimal] = {}
    products_by_id: dict[int, Product] = {}
    for ln in lines:
        if ln.product is None or ln.quantity_kg in (None, ""):
            continue
        # Untracked products (per 0088) are unlimited — never a shortfall.
        if not ln.product.is_stock_tracked:
            continue
        requested_by_product[ln.product.pk] = (
            requested_by_product.get(ln.product.pk, Decimal("0.000"))
            + Decimal(ln.quantity_kg)
        )
        products_by_id[ln.product.pk] = ln.product

    stocks = {
        s.product_id: s.quantity
        for s in Stock.objects.filter(
            branch=branch, product_id__in=requested_by_product.keys()
        )
    }

    warnings: list[dict] = []
    for product_id, requested in requested_by_product.items():
        current = stocks.get(product_id, Decimal("0.000"))
        if requested > current:
            warnings.append(
                {
                    "product": products_by_id[product_id],
                    "branch": branch,
                    "requested": requested,
                    "current": current,
                    "shortfall": requested - current,
                }
            )
    # Stable ordering by product name for predictable UI.
    warnings.sort(key=lambda w: w["product"].name_cs)
    return warnings
