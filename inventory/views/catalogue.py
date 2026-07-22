"""Catalogue: products, detail, branch-carry, XLS import."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.permissions import require_vlastnik

from ..forms import (
    ProductForm,
    RecipeComponentForm,
    RecipeComponentFormSet,
    ThresholdOverrideFormSet,
    XLSImportReviewHeaderForm,
    XLSImportReviewLineFormSet,
    XLSImportUploadForm,
)
from ..models import (
    Branch,
    Movement,
    Product,
    RecipeComponent,
    Stock,
    StockThresholdOverride,
)
from ..services import (
    create_mixture_from_review,
    parse_recipe_xls,
    reserved_kg,
    seed_branch_carriage_for_product,
    threshold_for,
)
from ._shared import _require_vlastnik, _safe_next


def _catalogue_rows(products, reserved_branches, carried_stocks_by_pair, has_recipe, totals):
    """One display row per product: total / reserved / effective / threshold /
    low-flag (+ the branches under threshold, per /podpora/ feedback #4). Only
    branches that carry the product (a Stock row exists, 0053) are counted.
    Shares ``reserved_kg`` / ``threshold_for`` with the dashboard panel."""
    rows = []
    for p in products:
        reserved = Decimal("0.000")
        effective_total = Decimal("0.000")
        threshold_min: Decimal | None = None
        is_low = False
        low_branches: list[Branch] = []
        empty_branches: list[Branch] = []
        for b in reserved_branches:
            on_hand = carried_stocks_by_pair.get((p.pk, b.pk))
            if on_hand is None:
                continue  # branch does not carry this product
            r = reserved_kg(p, b)
            reserved += r
            eff_b = on_hand - r
            effective_total += eff_b
            # Per 0091: the „Prázdný na" chip mirrors the group's own empty rule
            # (effective ≤ 0), independent of the threshold — so a genuinely-empty
            # product at the default threshold 0 still shows *where* it is empty
            # (low_branches / the „Dochází na" chip keeps its < nonzero-threshold
            # meaning for the low group).
            if eff_b <= 0:
                empty_branches.append(b)
            t = threshold_for(p, b)
            if t is not None:
                threshold_min = t if threshold_min is None else min(threshold_min, t)
                if eff_b < t:
                    is_low = True
                    low_branches.append(b)
        rows.append(
            {
                "product": p,
                "total": totals.get(p.pk, Decimal("0.000")),
                "reserved": reserved.quantize(Decimal("0.001")),
                "effective": effective_total.quantize(Decimal("0.001")),
                "threshold": threshold_min,
                "is_low": is_low,
                "low_branches": low_branches,
                "empty_branches": empty_branches,
                "has_recipe": p.pk in has_recipe,
            }
        )
    return rows


def _is_empty(r):
    # Per 0072: a product at effective ≤ 0 always groups as "Prázdné" —
    # the threshold no longer gates empty (it is now always set, default 0).
    return r["effective"] <= 0


def _is_low(r):
    return r["is_low"] and not _is_empty(r)


def catalogue_stock_groups(products, branches):
    """Display rows + stock-state groups + KPI aggregates for ``products``
    scoped to ``branches``. One source of truth shared by the Katalog
    (all-branches or a single ?branch=) and the obsluha Přehled
    (single-branch). Per 0064 (grouping) + 0072 (empty rule).

    Returns a dict: ``rows`` (one per product), ``empty_rows`` / ``low_rows``
    / ``ok_rows`` (the three state groups), and the KPI counts
    ``kpi_products`` / ``kpi_empty`` / ``kpi_low`` / ``kpi_total_kg``.

    Untracked products (per 0088, e.g. „Voda“) carry no Stock rows and are
    unlimited — drop them at the top so they never surface in the Katalog, the
    obsluha/vlastník Přehled, or the inventura „Dochází" roll-up (all three call
    this helper).
    """
    products = [p for p in products if p.is_stock_tracked]
    totals: dict[int, Decimal] = {}
    for s in Stock.objects.filter(product__in=products, branch__in=branches):
        totals[s.product_id] = totals.get(s.product_id, Decimal("0.000")) + s.quantity

    has_recipe = set(
        RecipeComponent.objects.filter(mixture_product__in=products)
        .values_list("mixture_product_id", flat=True)
        .distinct()
    )

    # Per 0053: a branch *carries* a product iff a Stock row exists for that
    # pair. Pre-fetch existing rows in scope so chips/thresholds only consider
    # branches that actually carry each product.
    carried_stocks_by_pair: dict[tuple[int, int], Decimal] = {
        (s.product_id, s.branch_id): s.quantity
        for s in Stock.objects.filter(product__in=products, branch__in=branches)
    }

    rows = _catalogue_rows(
        products, branches, carried_stocks_by_pair, has_recipe, totals
    )

    empty_rows = [r for r in rows if _is_empty(r)]
    low_rows = [r for r in rows if _is_low(r)]
    ok_rows = [r for r in rows if not _is_empty(r) and not _is_low(r)]

    return {
        "rows": rows,
        "empty_rows": empty_rows,
        "low_rows": low_rows,
        "ok_rows": ok_rows,
        "kpi_products": len(rows),
        "kpi_empty": len(empty_rows),
        "kpi_low": len(low_rows),
        "kpi_total_kg": sum((r["total"] for r in rows), Decimal("0.000")),
    }


@require_GET
def catalogue_index(request):
    """Browse the product catalogue. Filters: q (icontains on name),
    kind (raw_spice / mixture), status (active / archived / all).
    Defaults to active products only.
    """

    qs = Product.objects.all().order_by("name_cs")

    status = request.GET.get("status") or "active"
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "archived":
        qs = qs.filter(is_active=False)
    # "all" → no filter

    kind = request.GET.get("kind") or ""
    if kind in (Product.Kind.RAW_SPICE, Product.Kind.MIXTURE):
        qs = qs.filter(kind=kind)

    # Per 0063: text search (`q`) is filtered client-side in the browser
    # (diacritic-insensitive, typo-tolerant, as-you-type). The server only
    # echoes the term back into the input so it round-trips in the URL and the
    # JS re-applies it on load. Structured filters (kind/status/state/branch)
    # stay server-side.
    search = (request.GET.get("q") or "").strip()

    products = list(qs)

    # Branch filter — obsluha is forced to own branch; vlastník can
    # pick TYN / SEZ / all via ?branch=<code>. Scope: the selected branch
    # (if any) — else aggregate across active branches.
    filter_branch_code = ""
    selected_branch = None
    if request.user.is_obsluha and request.user.branch_id:
        selected_branch = request.user.branch
    else:
        filter_branch_code = (request.GET.get("branch") or "").strip().upper()
        if filter_branch_code:
            try:
                selected_branch = Branch.objects.get(code=filter_branch_code)
            except Branch.DoesNotExist:
                filter_branch_code = ""

    reserved_branches = (
        [selected_branch]
        if selected_branch is not None
        else list(Branch.objects.filter(is_active=True))
    )

    # Rows / groups come from the shared helper (same source as the obsluha
    # Přehled).
    groups = catalogue_stock_groups(products, reserved_branches)
    rows = groups["rows"]
    empty_rows = groups["empty_rows"]
    low_rows = groups["low_rows"]
    ok_rows = groups["ok_rows"]

    # ?state= narrows both the row count and the rendered groups.
    state_filter = (request.GET.get("state") or "").strip()
    if state_filter == "low":
        rows, empty_rows, ok_rows = low_rows, [], []
    elif state_filter == "empty":
        rows, low_rows, ok_rows = empty_rows, [], []
    elif state_filter == "ok":
        rows, empty_rows, low_rows = ok_rows, [], []

    # KPIs reflect the *displayed* selection — every server filter (kind /
    # status / branch / state) combined — so the top numbers always match
    # what's on screen (a Typ + Stav-skladu combo narrows them together, not
    # just Typ). Computed after the state narrowing from the final row set;
    # per 0084 the client (base.html apply()) then live-recomputes them from
    # the visible rows as the name filter is typed, restoring these values
    # when the box is cleared.
    kpi_products = len(rows)
    kpi_empty = len(empty_rows)
    kpi_low = len(low_rows)
    kpi_total_kg = sum((r["total"] for r in rows), Decimal("0.000"))

    return render(
        request,
        "inventory/catalogue_index.html",
        {
            "rows": rows,
            "count": len(rows),
            "empty_rows": empty_rows,
            "low_rows": low_rows,
            "ok_rows": ok_rows,
            "kpi_products": kpi_products,
            "kpi_empty": kpi_empty,
            "kpi_low": kpi_low,
            "kpi_total_kg": kpi_total_kg,
            "filter_q": search,
            "filter_kind": kind,
            "filter_status": status,
            "filter_branch_code": filter_branch_code,
            "filter_state": state_filter,
            "selected_branch": selected_branch,
            # Per-branch "low/empty on" chips only make sense in the
            # all-branches view (a single branch in scope needs no chip).
            "show_branch_chips": (
                selected_branch is None and not request.user.is_obsluha
            ),
            "branches": Branch.objects.filter(is_active=True).order_by("code"),
            "obsluha_branch": (
                request.user.branch if request.user.is_obsluha else None
            ),
        },
    )


@require_GET
def product_detail(request, pk: int):
    """Per-product detail with per-branch stock + recipe (for mixtures)
    + recent movements for this product."""
    product = get_object_or_404(Product, pk=pk)

    stock_qs = Stock.objects.filter(product=product).select_related("branch")
    if request.user.is_obsluha and request.user.branch_id:
        stock_qs = stock_qs.filter(branch_id=request.user.branch_id)
    stocks = list(stock_qs.order_by("branch__code"))
    total = sum((s.quantity for s in stocks), start=Decimal("0.000"))

    # Per-branch reserved/effective breakdown per 0043 + 0044. Per 0053
    # we iterate only branches that *carry* this product (Stock row
    # exists); the empty-state row in the template handles the no-row
    # case.
    branch_rows = []
    total_reserved = Decimal("0.000")
    total_effective = Decimal("0.000")
    for s in stocks:
        b = s.branch
        on_hand = s.quantity
        reserved = reserved_kg(product, b)
        effective = (on_hand - reserved).quantize(Decimal("0.001"))
        threshold = threshold_for(product, b)
        branch_rows.append(
            {
                "branch": b,
                "on_hand": on_hand,
                "reserved": reserved,
                "effective": effective,
                "threshold": threshold,
                "is_low": (
                    threshold is not None and effective < threshold
                ),
            }
        )
        total_reserved += reserved
        total_effective += effective

    recipe = []
    if product.kind == Product.Kind.MIXTURE:
        recipe = list(
            RecipeComponent.objects.filter(mixture_product=product)
            .select_related("component_product")
            .order_by("position", "id")
        )

    used_in = []
    if product.kind == Product.Kind.RAW_SPICE:
        used_in = list(
            RecipeComponent.objects.filter(component_product=product)
            .select_related("mixture_product")
            .order_by("mixture_product__name_cs")
        )

    recent_movements_qs = (
        Movement.objects.filter(
            lines__product=product, status=Movement.Status.DONE
        )
        .select_related("branch", "odberatel", "dodavatel", "created_by")
        .prefetch_related("lines__product")
        .distinct()
    )
    if request.user.is_obsluha and request.user.branch_id:
        recent_movements_qs = recent_movements_qs.filter(
            branch_id=request.user.branch_id
        )
    recent_movements = list(recent_movements_qs.order_by("-date_issued", "-id")[:20])

    # Overall stock state for the detail-page "Stav" chip (rail fact tile).
    if total <= 0:
        stock_state = "empty"
    elif any(r["is_low"] for r in branch_rows):
        stock_state = "low"
    else:
        stock_state = "ok"

    # Per 0089: seed the "Spočítat dávku" scaler from the mixture's default
    # batch when set (> 0). A dot string ("337.0") — the scaler input is
    # type=text/inputmode=decimal and its JS .replace(",",".")s, so a dot is
    # safe (never floatformat, per frontend-and-templates.md). None ⇒ template
    # falls back to "10". Quantize inline (not `from .inventura import _kg1` —
    # inventura already imports this module, so that would be a circular import).
    default_batch_1dp = None
    if product.default_batch_kg > 0:
        default_batch_1dp = str(
            product.default_batch_kg.quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        )

    return render(
        request,
        "inventory/product_detail.html",
        {
            "product": product,
            "stocks": stocks,
            "total_quantity": total,
            "total_reserved": total_reserved,
            "total_effective": total_effective,
            "stock_state": stock_state,
            "branch_rows": branch_rows,
            "recipe": recipe,
            "used_in": used_in,
            "recent_movements": recent_movements,
            "default_batch_1dp": default_batch_1dp,
        },
    )


# ---------------------------------------------------------------------------
# Seznam dodacích listů (screen 08)
# ---------------------------------------------------------------------------



def product_create(request):
    """Create a new product (surovina or směs). All authenticated users.

    Recipe is not editable here; for a new mixture, create it first
    then edit it to add components. Keeps the create form small.
    """
    can_edit_threshold = request.user.is_vlastnik
    if request.method == "POST":
        form = ProductForm(request.POST, can_edit_threshold=can_edit_threshold)
        if form.is_valid():
            product = form.save()
            # Per 0053, seed a 0-kg Stock row for every active branch so
            # the new product is "carried everywhere" by default. Vlastník
            # narrows the carry list via the Pobočky controls on edit.
            seed_branch_carriage_for_product(product)
            messages.success(request, f"Produkt {product.name_cs} přidán.")
            if (
                product.kind == Product.Kind.MIXTURE
                and request.user.is_vlastnik
            ):
                # Steer the vlastník straight into recipe editing.
                return redirect("inventory:product_edit", pk=product.pk)
            return redirect("inventory:product_detail", pk=product.pk)
    else:
        form = ProductForm(can_edit_threshold=can_edit_threshold)
    return render(
        request,
        "inventory/product_form.html",
        {
            "form": form,
            "mode": "create",
            "recipe_formset": None,
            "threshold_formset": None,
            "can_edit_threshold": can_edit_threshold,
        },
    )


def product_edit(request, pk: int):
    """Edit product fields. For směsi + vlastník, recipe inline edit too.

    The kind field is locked once the product is referenced by Stock
    or as a recipe component — flipping surovina↔směs would orphan
    those references.
    """
    product = get_object_or_404(Product, pk=pk)
    is_mixture = product.kind == Product.Kind.MIXTURE
    can_edit_recipe = is_mixture and request.user.is_vlastnik
    can_edit_threshold = request.user.is_vlastnik

    kind_locked = (
        Stock.objects.filter(product=product).exists()
        or RecipeComponent.objects.filter(
            Q(mixture_product=product) | Q(component_product=product)
        ).exists()
    )

    recipe_qs = RecipeComponent.objects.filter(
        mixture_product=product
    ).order_by("position", "id")
    override_qs = StockThresholdOverride.objects.filter(
        product=product
    ).order_by("branch__code")

    if request.method == "POST":
        form = ProductForm(
            request.POST,
            instance=product,
            lock_kind=kind_locked,
            can_edit_threshold=can_edit_threshold,
        )

        recipe_formset = None
        if can_edit_recipe:
            recipe_formset = RecipeComponentFormSet(
                request.POST,
                queryset=recipe_qs,
                prefix="recipe",
                form_kwargs={"mixture": product},
            )

        threshold_formset = None
        if can_edit_threshold:
            threshold_formset = ThresholdOverrideFormSet(
                request.POST,
                queryset=override_qs,
                prefix="threshold",
            )

        forms_valid = form.is_valid()
        if recipe_formset is not None:
            forms_valid = recipe_formset.is_valid() and forms_valid
        if threshold_formset is not None:
            forms_valid = threshold_formset.is_valid() and forms_valid

        if forms_valid:
            form.save()
            if recipe_formset is not None:
                # Populates deleted_objects and attaches cleaned data; its
                # return value (new+changed only) is deliberately unused —
                # position normalization must cover UNCHANGED rows too, or a
                # partial reorder would collide with untouched positions.
                recipe_formset.save(commit=False)
                deleted_forms = set(recipe_formset.deleted_forms)
                survivors = [
                    f
                    for f in recipe_formset.forms
                    if f not in deleted_forms
                    and f.cleaned_data.get("component_product")
                ]
                # Per 0092: dense 0..n-1 in submitted (JS DOM) order; a
                # missing position falls back to the form's own index.
                survivors.sort(
                    key=lambda f: (
                        f.cleaned_data.get("position")
                        if f.cleaned_data.get("position") is not None
                        else recipe_formset.forms.index(f),
                        recipe_formset.forms.index(f),
                    )
                )
                for i, f in enumerate(survivors):
                    f.instance.position = i
                    f.instance.mixture_product = product
                    f.instance.save()
                for deleted in recipe_formset.deleted_objects:
                    deleted.delete()
            if threshold_formset is not None:
                instances = threshold_formset.save(commit=False)
                for inst in instances:
                    inst.product = product
                    inst.save()
                for deleted in threshold_formset.deleted_objects:
                    deleted.delete()
            messages.success(request, "Změny uloženy.")
            return redirect("inventory:product_detail", pk=product.pk)
    else:
        form = ProductForm(
            instance=product,
            lock_kind=kind_locked,
            can_edit_threshold=can_edit_threshold,
        )
        recipe_formset = (
            RecipeComponentFormSet(
                queryset=recipe_qs,
                prefix="recipe",
                form_kwargs={"mixture": product},
            )
            if can_edit_recipe
            else None
        )
        threshold_formset = (
            ThresholdOverrideFormSet(
                queryset=override_qs, prefix="threshold"
            )
            if can_edit_threshold
            else None
        )

    new_recipe_row = (
        RecipeComponentForm(mixture=product) if can_edit_recipe else None
    )

    # Per 0053: "drží / nedrží" controls. Row existence in Stock is the
    # carry flag. Visible read-only to obsluha; buttons are vlastník-only.
    carry_stocks_by_branch_id = {
        s.branch_id: s
        for s in Stock.objects.filter(product=product).select_related("branch")
    }
    carry_rows = []
    for b in Branch.objects.filter(is_active=True).order_by("code"):
        s = carry_stocks_by_branch_id.get(b.pk)
        carry_rows.append(
            {
                "branch": b,
                "carried": s is not None,
                "quantity": s.quantity if s is not None else Decimal("0.000"),
                "reserved": (
                    reserved_kg(product, b) if s is not None else Decimal("0.000")
                ),
            }
        )

    return render(
        request,
        "inventory/product_form.html",
        {
            "form": form,
            "mode": "edit",
            "target": product,
            "recipe_formset": recipe_formset,
            "new_recipe_row": new_recipe_row,
            "threshold_formset": threshold_formset,
            "kind_locked": kind_locked,
            "can_edit_recipe": can_edit_recipe,
            "can_edit_threshold": can_edit_threshold,
            "carry_rows": carry_rows,
        },
    )


@require_POST
def product_archive(request, pk: int):
    """Soft-archive a product. Vlastník-only per 0040."""
    require_vlastnik(request, "Pouze vlastník může archivovat produkty.")
    product = get_object_or_404(Product, pk=pk)
    product.is_active = False
    product.save(update_fields=["is_active"])
    messages.success(request, f"Produkt {product.name_cs} archivován.")
    return redirect("inventory:catalogue_index")


@require_POST
def product_reactivate(request, pk: int):
    """Re-activate an archived product. Vlastník-only per 0040."""
    require_vlastnik(request, "Pouze vlastník může aktivovat produkty.")
    product = get_object_or_404(Product, pk=pk)
    if Product.objects.filter(
        name_cs__iexact=product.name_cs, is_active=True
    ).exclude(pk=product.pk).exists():
        messages.error(
            request,
            "Aktivní produkt se stejným názvem už existuje — "
            "přejmenuj jednoho z nich než aktivuješ.",
        )
        return redirect("inventory:product_detail", pk=product.pk)
    product.is_active = True
    product.save(update_fields=["is_active"])
    messages.success(request, f"Produkt {product.name_cs} aktivován.")
    return redirect("inventory:product_detail", pk=product.pk)



@require_POST
def product_branch_add(request, product_id: int, branch_id: int):
    """Mark a branch as carrying this product by creating a 0-kg Stock
    row. Vlastník-only per 0053. Idempotent — second call is a no-op.
    """
    _require_vlastnik(request)
    product = get_object_or_404(Product, pk=product_id)
    branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
    _, created = Stock.objects.get_or_create(
        product=product,
        branch=branch,
        defaults={"quantity": Decimal("0.000")},
    )
    if created:
        messages.success(
            request,
            f"Pobočka {branch.code} nyní drží {product.name_cs}.",
        )
    else:
        messages.info(
            request,
            f"Pobočka {branch.code} už produkt {product.name_cs} drží.",
        )
    return redirect(_safe_next(
        request, reverse("inventory:product_edit", args=[product.pk])
    ))


@require_POST
def product_branch_remove(request, product_id: int, branch_id: int):
    """Stop carrying this product on this branch by deleting the Stock
    row. Vlastník-only per 0053. Destructive on non-zero on-hand — the
    UI warns; the server has no precondition.
    """
    _require_vlastnik(request)
    product = get_object_or_404(Product, pk=product_id)
    branch = get_object_or_404(Branch, pk=branch_id)
    Stock.objects.filter(product=product, branch=branch).delete()
    messages.success(
        request,
        f"Pobočka {branch.code} už nedrží {product.name_cs}.",
    )
    return redirect(_safe_next(
        request, reverse("inventory:product_edit", args=[product.pk])
    ))


# ---------------------------------------------------------------------------
# Pass 5c — Branch CRUD (per decision 0040, vlastník-only)
# ---------------------------------------------------------------------------



@require_http_methods(["GET", "POST"])
def xls_import_upload(request):
    """Upload a recipe XLS, then render the editable review page.

    GET → render the upload form.
    POST → parse the file; on success render the review page bound to the
    parsed shape (header form + line formset). On parse failure, surface a
    Czech error on the upload form.

    Vlastník-only. Per decision 0048.
    """
    _require_vlastnik(request)

    parsed = None
    if request.method == "POST":
        upload = XLSImportUploadForm(request.POST, request.FILES)
        if upload.is_valid():
            uploaded = upload.cleaned_data["xls_file"]
            try:
                parsed = parse_recipe_xls(uploaded, uploaded.name)
            except (ValueError, ValidationError) as exc:
                upload.add_error("xls_file", str(exc))
                parsed = None
    else:
        upload = XLSImportUploadForm()

    if parsed is None:
        return render(
            request, "inventory/xls_import_upload.html", {"form": upload}
        )

    # Pre-fetch active raw spices once and dedupe by casefold so "KRUPIČKA"
    # / "Krupička" / "krupička" all resolve to the same row.
    existing_by_key = {
        p.name_cs.casefold(): p
        for p in Product.objects.filter(
            kind=Product.Kind.RAW_SPICE, is_active=True,
        )
    }
    header = XLSImportReviewHeaderForm(
        initial={
            "name_cs": parsed.mixture_name,
            "notes": parsed.notes,
            "total_kg": parsed.total_kg,
        }
    )
    lines_initial = []
    for line in parsed.lines:
        existing = existing_by_key.get(line.name_cs.casefold())
        lines_initial.append(
            {
                "name_cs": line.name_cs,
                "qty_kg": line.qty_kg,
                "existing_product_id": existing.pk if existing else None,
            }
        )
    formset = XLSImportReviewLineFormSet(initial=lines_initial)
    return render(
        request,
        "inventory/xls_import_review.html",
        {
            "header": header,
            "formset": formset,
            "warnings": parsed.warnings,
            "total_kg": parsed.total_kg,
        },
    )


@require_POST
def xls_import_confirm(request):
    """Commit the operator-reviewed import as a single atomic write."""
    _require_vlastnik(request)
    header = XLSImportReviewHeaderForm(request.POST)
    formset = XLSImportReviewLineFormSet(request.POST)

    def _render_review_with_errors(status=400):
        return render(
            request,
            "inventory/xls_import_review.html",
            {
                "header": header,
                "formset": formset,
                "warnings": [],
                "total_kg": header.data.get("total_kg") or "",
            },
            status=status,
        )

    if not (header.is_valid() and formset.is_valid()):
        return _render_review_with_errors()

    line_data = [
        f.cleaned_data
        for f in formset.forms
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    ]
    if not line_data:
        formset._non_form_errors = formset.error_class(
            ["Receptura musí mít alespoň jednu surovinu."]
        )
        return _render_review_with_errors()

    try:
        product = create_mixture_from_review(
            header_data=header.cleaned_data,
            line_data=line_data,
            user=request.user,
        )
    except ValidationError as exc:
        formset._non_form_errors = formset.error_class(exc.messages)
        return _render_review_with_errors()

    messages.success(
        request,
        f'Směs „{product.name_cs}" vytvořena včetně receptury.',
    )
    return redirect("inventory:product_detail", pk=product.pk)
