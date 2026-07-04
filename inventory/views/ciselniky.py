"""Ciselniky: suppliers, customers, branches CRUD.

Supplier + Customer use the reusable ``_crud`` class-based views (near-identical
archivable masters). Branch stays function-based — its ``code`` URL kwarg,
vlastník gating, and stock/active-user archive guard don't fit the generic
mixin (decision 0068).
"""

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
from ._crud import (
    ArchivableArchiveView,
    ArchivableCreateView,
    ArchivableEditView,
    ArchivableIndexView,
    ArchivableReactivateView,
)
from ._shared import _require_vlastnik

# --- Supplier CRUD (all authenticated users) -------------------------------

supplier_index = ArchivableIndexView.as_view(
    model=Supplier,
    template="inventory/supplier_index.html",
    context_list_name="suppliers",
)
supplier_create = ArchivableCreateView.as_view(
    model=Supplier,
    form_class=SupplierForm,
    template="inventory/supplier_form.html",
    index_url="inventory:supplier_index",
    created_msg="Dodavatel {obj.name} přidán.",
)
supplier_edit = ArchivableEditView.as_view(
    model=Supplier,
    form_class=SupplierForm,
    template="inventory/supplier_form.html",
    index_url="inventory:supplier_index",
    internal_block_msg="Interní dodavatele nelze upravovat z této obrazovky.",
)
supplier_archive = ArchivableArchiveView.as_view(
    model=Supplier,
    index_url="inventory:supplier_index",
    archived_msg="Dodavatel {obj.name} archivován.",
    internal_block_msg="Interní dodavatele nelze archivovat.",
)
supplier_reactivate = ArchivableReactivateView.as_view(
    model=Supplier,
    index_url="inventory:supplier_index",
    reactivated_msg="Dodavatel {obj.name} aktivován.",
)


# --- Customer CRUD (all authenticated users) -------------------------------
#
# Tier: all authenticated users. `is_default_recipient` flag stays admin-only;
# the default recipient (Říčany) cannot be archived from here.


class CustomerArchiveView(ArchivableArchiveView):
    def blocked(self, obj) -> str | None:
        err = super().blocked(obj)
        if err:
            return err
        if obj.is_default_recipient:
            return (
                "Výchozího odběratele (Říčany) nelze archivovat — "
                "změna v administraci."
            )
        return None


customer_index = ArchivableIndexView.as_view(
    model=Customer,
    template="inventory/customer_index.html",
    context_list_name="customers",
)
customer_create = ArchivableCreateView.as_view(
    model=Customer,
    form_class=CustomerForm,
    template="inventory/customer_form.html",
    index_url="inventory:customer_index",
    created_msg="Odběratel {obj.name} přidán.",
)
customer_edit = ArchivableEditView.as_view(
    model=Customer,
    form_class=CustomerForm,
    template="inventory/customer_form.html",
    index_url="inventory:customer_index",
    internal_block_msg="Interní odběratele nelze upravovat z této obrazovky.",
)
customer_archive = CustomerArchiveView.as_view(
    model=Customer,
    index_url="inventory:customer_index",
    archived_msg="Odběratel {obj.name} archivován.",
    internal_block_msg="Interní odběratele nelze archivovat.",
)
customer_reactivate = ArchivableReactivateView.as_view(
    model=Customer,
    index_url="inventory:customer_index",
    reactivated_msg="Odběratel {obj.name} aktivován.",
)


# ---------------------------------------------------------------------------
# Branch CRUD (per decision 0040, vlastník-only) — function-based
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
