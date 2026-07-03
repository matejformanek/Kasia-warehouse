"""Ciselniky: suppliers, customers, branches CRUD."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..forms import (
    BranchForm,
    CustomerForm,
    SupplierForm,
)
from ..models import (
    Branch,
    Customer,
    DodaciList,
    Stock,
    Supplier,
)
from ._shared import _require_vlastnik


@require_GET
def supplier_index(request):
    """List dodavatelů with filter: active / archived / all."""
    status = request.GET.get("status") or "active"
    qs = Supplier.objects.exclude(is_internal=True).order_by("name")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "archived":
        qs = qs.filter(is_active=False)
    return render(
        request,
        "inventory/supplier_index.html",
        {"suppliers": list(qs), "filter_status": status},
    )


def supplier_create(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            sup = form.save()
            messages.success(request, f"Dodavatel {sup.name} přidán.")
            return redirect("inventory:supplier_index")
    else:
        form = SupplierForm(initial={"is_active": True})
    return render(
        request,
        "inventory/supplier_form.html",
        {"form": form, "mode": "create"},
    )


def supplier_edit(request, pk: int):
    sup = get_object_or_404(Supplier, pk=pk)
    if sup.is_internal:
        messages.error(
            request, "Interní dodavatele nelze upravovat z této obrazovky."
        )
        return redirect("inventory:supplier_index")
    if request.method == "POST":
        form = SupplierForm(request.POST, instance=sup)
        if form.is_valid():
            form.save()
            messages.success(request, "Změny uloženy.")
            return redirect("inventory:supplier_index")
    else:
        form = SupplierForm(instance=sup)
    return render(
        request,
        "inventory/supplier_form.html",
        {"form": form, "mode": "edit", "target": sup},
    )


@require_POST
def supplier_archive(request, pk: int):
    sup = get_object_or_404(Supplier, pk=pk)
    if sup.is_internal:
        messages.error(request, "Interní dodavatele nelze archivovat.")
        return redirect("inventory:supplier_index")
    sup.is_active = False
    sup.save(update_fields=["is_active"])
    messages.success(request, f"Dodavatel {sup.name} archivován.")
    return redirect("inventory:supplier_index")


@require_POST
def supplier_reactivate(request, pk: int):
    sup = get_object_or_404(Supplier, pk=pk)
    sup.is_active = True
    sup.save(update_fields=["is_active"])
    messages.success(request, f"Dodavatel {sup.name} aktivován.")
    return redirect("inventory:supplier_index")


# ---------------------------------------------------------------------------
# Pass 5 — Customer CRUD (per decision 0040)
#
# Tier: all authenticated users. `is_default_recipient` flag stays admin-only.
# Routes: /odberatele/ + analogous to supplier.
# ---------------------------------------------------------------------------


@require_GET
def customer_index(request):
    status = request.GET.get("status") or "active"
    qs = Customer.objects.exclude(is_internal=True).order_by("name")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "archived":
        qs = qs.filter(is_active=False)
    return render(
        request,
        "inventory/customer_index.html",
        {"customers": list(qs), "filter_status": status},
    )


def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            cust = form.save()
            messages.success(request, f"Odběratel {cust.name} přidán.")
            return redirect("inventory:customer_index")
    else:
        form = CustomerForm(initial={"is_active": True})
    return render(
        request,
        "inventory/customer_form.html",
        {"form": form, "mode": "create"},
    )


def customer_edit(request, pk: int):
    cust = get_object_or_404(Customer, pk=pk)
    if cust.is_internal:
        messages.error(
            request, "Interní odběratele nelze upravovat z této obrazovky."
        )
        return redirect("inventory:customer_index")
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=cust)
        if form.is_valid():
            form.save()
            messages.success(request, "Změny uloženy.")
            return redirect("inventory:customer_index")
    else:
        form = CustomerForm(instance=cust)
    return render(
        request,
        "inventory/customer_form.html",
        {"form": form, "mode": "edit", "target": cust},
    )


@require_POST
def customer_archive(request, pk: int):
    cust = get_object_or_404(Customer, pk=pk)
    if cust.is_internal:
        messages.error(request, "Interní odběratele nelze archivovat.")
        return redirect("inventory:customer_index")
    if cust.is_default_recipient:
        messages.error(
            request,
            "Výchozího odběratele (Říčany) nelze archivovat — "
            "změna v administraci.",
        )
        return redirect("inventory:customer_index")
    cust.is_active = False
    cust.save(update_fields=["is_active"])
    messages.success(request, f"Odběratel {cust.name} archivován.")
    return redirect("inventory:customer_index")


@require_POST
def customer_reactivate(request, pk: int):
    cust = get_object_or_404(Customer, pk=pk)
    cust.is_active = True
    cust.save(update_fields=["is_active"])
    messages.success(request, f"Odběratel {cust.name} aktivován.")
    return redirect("inventory:customer_index")


# ---------------------------------------------------------------------------
# Pass 5b — Product + Recipe CRUD (per decision 0040)
#
# Tier:
# - Product fields (name, kind, notes): all authenticated may create/edit.
# - Product archive: vlastník-only (affects stock semantics).
# - Recipe (RecipeComponent) edit on směs: vlastník-only.
# ---------------------------------------------------------------------------



def _branch_code_locked(branch: Branch) -> bool:
    """A branch's `code` is part of the dodák číslo `<CODE>-<YEAR>-<NNNN>`
    per [0008](../context/decisions/0008-dodaci-list-numbering.md).
    Once any dodák has been issued from this branch, the code is
    immutable."""
    return DodaciList.objects.filter(branch=branch).exists()


@require_GET
def branch_index(request):
    _require_vlastnik(request)
    status = request.GET.get("status") or "active"
    qs = Branch.objects.order_by("code")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "archived":
        qs = qs.filter(is_active=False)
    branches = list(qs)
    # Annotate each row with whether the code is locked + last dodák counter.
    rows = []
    for b in branches:
        rows.append(
            {
                "branch": b,
                "code_locked": _branch_code_locked(b),
                "dodak_count": DodaciList.objects.filter(branch=b).count(),
            }
        )
    return render(
        request,
        "inventory/branch_index.html",
        {"rows": rows, "filter_status": status},
    )


def branch_create(request):
    _require_vlastnik(request)
    if request.method == "POST":
        form = BranchForm(request.POST)
        if form.is_valid():
            branch = form.save()
            messages.success(
                request, f"Pobočka {branch.code} — {branch.name} přidána."
            )
            return redirect("inventory:branch_index")
    else:
        form = BranchForm(initial={"is_active": True})
    return render(
        request,
        "inventory/branch_form.html",
        {"form": form, "mode": "create", "code_locked": False},
    )


def branch_edit(request, code: str):
    _require_vlastnik(request)
    branch = get_object_or_404(Branch, code=code.upper())
    code_locked = _branch_code_locked(branch)
    if request.method == "POST":
        form = BranchForm(request.POST, instance=branch, code_locked=code_locked)
        if form.is_valid():
            form.save()
            messages.success(request, "Změny uloženy.")
            return redirect("inventory:branch_index")
    else:
        form = BranchForm(instance=branch, code_locked=code_locked)
    return render(
        request,
        "inventory/branch_form.html",
        {
            "form": form,
            "mode": "edit",
            "target": branch,
            "code_locked": code_locked,
            "dodak_count": DodaciList.objects.filter(branch=branch).count(),
        },
    )


@require_POST
def branch_archive(request, code: str):
    _require_vlastnik(request)
    branch = get_object_or_404(Branch, code=code.upper())
    if branch.is_active:
        # Refuse archive if branch still has stock or active users.
        from accounts.models import User as UserModel

        has_stock = Stock.objects.filter(branch=branch, quantity__gt=0).exists()
        has_users = UserModel.objects.filter(branch=branch, is_active=True).exists()
        if has_stock or has_users:
            reasons = []
            if has_stock:
                reasons.append("pobočka má nenulové zásoby")
            if has_users:
                reasons.append("pobočka má aktivní uživatele")
            messages.error(
                request,
                f"Pobočku nelze archivovat — {' a '.join(reasons)}.",
            )
            return redirect("inventory:branch_index")
        branch.is_active = False
        branch.save(update_fields=["is_active"])
        messages.success(request, f"Pobočka {branch.code} archivována.")
    return redirect("inventory:branch_index")


@require_POST
def branch_reactivate(request, code: str):
    _require_vlastnik(request)
    branch = get_object_or_404(Branch, code=code.upper())
    branch.is_active = True
    branch.save(update_fields=["is_active"])
    messages.success(request, f"Pobočka {branch.code} aktivována.")
    return redirect("inventory:branch_index")


# ---------------------------------------------------------------------------
# Pass 5d — Manual stock adjustment (per decision 0041, vlastník-only)
# ---------------------------------------------------------------------------


