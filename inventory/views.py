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
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    BranchForm,
    CustomerForm,
    MovementEditLineFormSet,
    MovementLineForm,
    MovementLineFormSet,
    PrijemEditForm,
    PrijemForm,
    ProductForm,
    RecipeComponentForm,
    RecipeComponentFormSet,
    SettingsForm,
    SmtpTestForm,
    StockAdjustmentForm,
    SupplierForm,
    VydejEditForm,
    VydejForm,
    assert_no_future_date,
)
from .models import (
    Branch,
    Customer,
    DodaciList,
    DodaciListEmailLog,
    DodaciListNumberSequence,
    MixingJob,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    RecipeComponent,
    Settings,
    Stock,
    Supplier,
)
from .services import (
    apply_movement,
    apply_stock_adjustment,
    cancel_mixing_job,
    edit_movement,
    finish_mixing_job,
    record_completed_mixing_job,
    render_dodaci_list_pdf,
    send_dodaci_list_email,
    start_mixing_job,
)


@require_GET
def home(request):
    """Post-login landing.

    Role routing per screens/02 + screens/03:
    - Branch staff (`obsluha` group, has `user.branch` FK) redirect
      to `/pobocka/<branch.code>/` (screen 03).
    - Everyone else (vlastník / superuser / unassigned) lands on
      the owner dashboard below (screen 02).
    """
    if request.user.is_obsluha and request.user.branch_id:
        return redirect(
            "inventory:branch_dashboard", code=request.user.branch.code
        )

    from django.db.models import Sum

    branches = list(Branch.objects.filter(is_active=True).order_by("code"))
    branch_panels = []
    for b in branches:
        stocks = list(
            Stock.objects.filter(branch=b, quantity__gt=0)
            .select_related("product")
            .order_by("-quantity")
        )
        total_mass = (
            Stock.objects.filter(branch=b).aggregate(s=Sum("quantity"))["s"]
            or Decimal("0.000")
        )
        recent_movements = list(
            Movement.objects.filter(branch=b)
            .select_related("odberatel", "dodavatel", "created_by")
            .prefetch_related("lines__product")
            .order_by("-date_issued", "-id")[:5]
        )
        branch_panels.append(
            {
                "branch": b,
                "product_count": len(stocks),
                "total_mass": total_mass,
                "top_stocks": stocks[:5],
                "recent_movements": recent_movements,
            }
        )

    recent_dodaky = list(
        DodaciList.objects.select_related("branch", "odberatel")
        .order_by("-date_issued", "-id")[:10]
    )

    # K vyřešení: failed sends whose dodák hasn't yet been re-sent
    # successfully at the current version. The query: dodáky that
    # have ≥1 FAILED log at the current version and 0 SENT logs at
    # the current version.
    failed_dodaky = []
    for dl in DodaciList.objects.prefetch_related("email_logs"):
        logs_at_current = [
            log for log in dl.email_logs.all() if log.version == dl.current_version
        ]
        if not logs_at_current:
            continue
        any_sent = any(
            log.status == DodaciListEmailLog.Status.SENT for log in logs_at_current
        )
        any_failed = any(
            log.status == DodaciListEmailLog.Status.FAILED for log in logs_at_current
        )
        if any_failed and not any_sent:
            last_failed = max(
                (
                    log
                    for log in logs_at_current
                    if log.status == DodaciListEmailLog.Status.FAILED
                ),
                key=lambda log: log.sent_at,
            )
            failed_dodaky.append(
                {"dodaci_list": dl, "last_failed": last_failed}
            )

    # Recently edited dodáky (current_version > 1), latest first, top 5.
    edited_dodaky = list(
        DodaciList.objects.select_related("branch", "odberatel")
        .filter(current_version__gt=1)
        .order_by("-id")[:5]
    )

    return render(
        request,
        "inventory/home.html",
        {
            "branch_panels": branch_panels,
            "recent_dodaky": recent_dodaky,
            "failed_dodaky": failed_dodaky,
            "edited_dodaky": edited_dodaky,
            "to_resolve_count": len(failed_dodaky) + len(edited_dodaky),
        },
    )


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
# Movement history (screen 10)
# ---------------------------------------------------------------------------


@require_GET
def movement_history(request):
    """Chronological filterable record of every movement.

    Layout (per Pass 5g redesign):
    - **Tab chips** at top: Vše / Příjmy / Výdeje / Inventura / Editováno.
      `?tab=<name>` is the shorthand the chips use; counts per tab
      are computed against the same branch-scoped + date/q-filtered
      base qs so the chip badges always tell the truth for the
      current view.
    - **Filter card** below tabs: branch (vlastník only — obsluha is
      auto-scoped), date from/to, free-text q.
    - **Table** at the bottom — same as before, capped at 200.

    Legacy `?kind=` and `?edited=` URL params still work for
    bookmarked links; new `?tab=` is the operator-facing shorthand.
    """
    from datetime import date as _date

    base_qs = (
        Movement.objects.select_related(
            "branch", "odberatel", "dodavatel", "created_by"
        )
        .prefetch_related("lines__product", "audit_entries")
    )

    # Branch scoping — obsluha forced to own branch.
    if request.user.is_obsluha and request.user.branch_id:
        base_qs = base_qs.filter(branch_id=request.user.branch_id)
        branch_locked = request.user.branch
    else:
        branch_locked = None
        branch_filter = request.GET.get("branch") or ""
        if branch_filter:
            base_qs = base_qs.filter(branch_id=branch_filter)

    date_from = request.GET.get("date_from") or ""
    date_to = request.GET.get("date_to") or ""

    def _parse(s: str):
        try:
            return _date.fromisoformat(s)
        except ValueError:
            return None

    df, dt = _parse(date_from), _parse(date_to)
    if df is not None:
        base_qs = base_qs.filter(date_issued__gte=df)
    if dt is not None:
        base_qs = base_qs.filter(date_issued__lte=dt)

    search = (request.GET.get("q") or "").strip()
    if search:
        base_qs = base_qs.filter(
            Q(odberatel__name__icontains=search)
            | Q(dodavatel__name__icontains=search)
            | Q(lines__product__name_cs__icontains=search)
            | Q(note__icontains=search)
        ).distinct()

    # Compute counts per tab against base (post-branch + post-date + post-q
    # so the chips reflect the current filter context).
    inventura_filter = Q(note__startswith="[STAV] ")
    tab_counts = {
        "all": base_qs.count(),
        "prijem": base_qs.filter(kind=Movement.Kind.PRIJEM).count(),
        "vydej": base_qs.filter(kind=Movement.Kind.VYDEJ).count(),
        "inventura": base_qs.filter(inventura_filter).count(),
        "edited": base_qs.filter(audit_entries__isnull=False).distinct().count(),
    }

    # Resolve the active tab. Legacy `?kind=` / `?edited=1` map onto
    # the new tab system so bookmarked links keep their behaviour.
    tab = request.GET.get("tab") or ""
    legacy_kind = request.GET.get("kind") or ""
    legacy_edited = request.GET.get("edited") == "1"
    if not tab:
        if legacy_kind in (Movement.Kind.PRIJEM, Movement.Kind.VYDEJ):
            tab = legacy_kind
        elif legacy_edited:
            tab = "edited"
        else:
            tab = "all"

    qs = base_qs
    if tab == Movement.Kind.PRIJEM:
        qs = qs.filter(kind=Movement.Kind.PRIJEM)
    elif tab == Movement.Kind.VYDEJ:
        qs = qs.filter(kind=Movement.Kind.VYDEJ)
    elif tab == "inventura":
        qs = qs.filter(inventura_filter)
    elif tab == "edited":
        qs = qs.filter(audit_entries__isnull=False).distinct()
    # tab == "all" → no extra filter.

    qs = qs.order_by("-date_issued", "-id")[:200]
    movements = list(qs)

    branches = list(Branch.objects.filter(is_active=True).order_by("code"))

    tabs = [
        ("all", "Vše", tab_counts["all"]),
        (Movement.Kind.PRIJEM, "Příjmy", tab_counts["prijem"]),
        (Movement.Kind.VYDEJ, "Výdeje", tab_counts["vydej"]),
        ("inventura", "Inventura / úprava stavu", tab_counts["inventura"]),
        ("edited", "Editováno", tab_counts["edited"]),
    ]

    return render(
        request,
        "inventory/movement_history.html",
        {
            "movements": movements,
            "count": len(movements),
            "branches": branches,
            "branch_locked": branch_locked,
            "filter_branch": request.GET.get("branch") or "",
            "filter_kind": legacy_kind,  # back-compat for any external link
            "filter_date_from": date_from,
            "filter_date_to": date_to,
            "filter_edited": legacy_edited,
            "filter_q": search,
            "active_tab": tab,
            "tabs": tabs,
        },
    )


# ---------------------------------------------------------------------------
# Branch dashboard (screen 03)
# ---------------------------------------------------------------------------


@require_GET
def branch_dashboard(request, code: str):
    """Per-branch dashboard. Vlastník / superuser users may open any
    branch; obsluha users are scoped to their own branch (403 on the
    other branch).
    """
    branch = get_object_or_404(Branch, code=code)

    if request.user.is_obsluha:
        if request.user.branch_id != branch.pk:
            return HttpResponse(
                "Nemáte oprávnění zobrazit tuto pobočku.",
                content_type="text/plain; charset=utf-8",
                status=403,
            )

    stocks_qs = (
        Stock.objects.filter(branch=branch)
        .select_related("product")
        .order_by("product__name_cs")
    )
    search = (request.GET.get("q") or "").strip()
    if search:
        stocks_qs = stocks_qs.filter(product__name_cs__icontains=search)
    stocks = list(stocks_qs)
    recent_movements = list(
        Movement.objects.filter(branch=branch)
        .select_related("odberatel", "dodavatel", "created_by")
        .prefetch_related("lines__product")
        .order_by("-date_issued", "-id")[:15]
    )
    return render(
        request,
        "inventory/branch_dashboard.html",
        {
            "branch": branch,
            "stocks": stocks,
            "recent_movements": recent_movements,
            "search": search,
        },
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
    overdraw_warnings: list[dict] = []
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
                    branch = form.cleaned_data["branch"]
                    overdraw_warnings = _compute_overdraw(branch, lines)
                    if overdraw_warnings:
                        # Pre-check refusal: re-render with structured
                        # warning card per decision 0042. No service call.
                        pass
                    else:
                        movement = Movement(
                            branch=branch,
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

    return render(
        request,
        "inventory/vydej_form.html",
        {
            "form": form,
            "formset": formset,
            "overdraw_warnings": overdraw_warnings,
        },
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


# ---------------------------------------------------------------------------
# Catalogue (screens 04 / 05 — read-only browse)
# ---------------------------------------------------------------------------


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

    search = (request.GET.get("q") or "").strip()
    if search:
        qs = qs.filter(name_cs__icontains=search)

    products = list(qs)

    # Per-product stock (in branch scope for obsluha, across both
    # branches for vlastník) + recipe presence, zipped into one row
    # struct so the template doesn't need custom filters to index a
    # dict by primary key.
    stock_qs = Stock.objects.filter(product__in=products).select_related("branch")

    # Branch filter — obsluha is forced to own branch; vlastník can
    # pick TYN / SEZ / all via ?branch=<code>.
    filter_branch_code = ""
    selected_branch = None
    if request.user.is_obsluha and request.user.branch_id:
        stock_qs = stock_qs.filter(branch_id=request.user.branch_id)
        selected_branch = request.user.branch
    else:
        filter_branch_code = (request.GET.get("branch") or "").strip().upper()
        if filter_branch_code:
            try:
                selected_branch = Branch.objects.get(code=filter_branch_code)
                stock_qs = stock_qs.filter(branch=selected_branch)
            except Branch.DoesNotExist:
                filter_branch_code = ""

    totals: dict[int, Decimal] = {}
    for s in stock_qs:
        totals[s.product_id] = totals.get(s.product_id, Decimal("0.000")) + s.quantity

    has_recipe = set(
        RecipeComponent.objects.filter(mixture_product__in=products)
        .values_list("mixture_product_id", flat=True)
        .distinct()
    )

    rows = [
        {
            "product": p,
            "total": totals.get(p.pk, Decimal("0.000")),
            "has_recipe": p.pk in has_recipe,
        }
        for p in products
    ]

    return render(
        request,
        "inventory/catalogue_index.html",
        {
            "rows": rows,
            "count": len(rows),
            "filter_q": search,
            "filter_kind": kind,
            "filter_status": status,
            "filter_branch_code": filter_branch_code,
            "selected_branch": selected_branch,
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

    recipe = []
    if product.kind == Product.Kind.MIXTURE:
        recipe = list(
            RecipeComponent.objects.filter(mixture_product=product)
            .select_related("component_product")
            .order_by("component_product__name_cs")
        )

    used_in = []
    if product.kind == Product.Kind.RAW_SPICE:
        used_in = list(
            RecipeComponent.objects.filter(component_product=product)
            .select_related("mixture_product")
            .order_by("mixture_product__name_cs")
        )

    recent_movements_qs = (
        Movement.objects.filter(lines__product=product)
        .select_related("branch", "odberatel", "dodavatel", "created_by")
        .prefetch_related("lines__product")
        .distinct()
    )
    if request.user.is_obsluha and request.user.branch_id:
        recent_movements_qs = recent_movements_qs.filter(
            branch_id=request.user.branch_id
        )
    recent_movements = list(recent_movements_qs.order_by("-date_issued", "-id")[:20])

    return render(
        request,
        "inventory/product_detail.html",
        {
            "product": product,
            "stocks": stocks,
            "total_quantity": total,
            "recipe": recipe,
            "used_in": used_in,
            "recent_movements": recent_movements,
        },
    )


# ---------------------------------------------------------------------------
# Seznam dodacích listů (screen 08)
# ---------------------------------------------------------------------------


@require_GET
def dodaci_list_index(request):
    qs = DodaciList.objects.select_related("branch", "odberatel", "created_by")
    branch_id = request.GET.get("branch") or ""
    year = request.GET.get("year") or ""
    edited_only = request.GET.get("edited") == "1"

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
        },
    )


@require_GET
def dodaci_list_pdf(request, cislo: str):
    dodaci_list = get_object_or_404(DodaciList, cislo=cislo)
    pdf_bytes = render_dodaci_list_pdf(dodaci_list)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{dodaci_list.cislo}.pdf"'
    return response


@require_POST
def dodaci_list_resend(request, cislo: str):
    dodaci_list = get_object_or_404(DodaciList, cislo=cislo)
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


_MOVEMENT_EDITABLE_FIELDS = ("branch", "date_issued", "dodavatel", "odberatel", "note")
_LINE_EDITABLE_FIELDS = ("product", "quantity_kg", "sarze", "expiry", "note")


@require_http_methods(["GET", "POST"])
def movement_edit(request, pk: int):
    movement = get_object_or_404(
        Movement.objects.select_related("branch", "odberatel", "dodavatel"),
        pk=pk,
    )
    existing_lines = list(
        movement.lines.select_related("product").order_by("id")
    )

    form_cls, line_field_for_kind = _form_for_kind(movement.kind)

    if request.method == "POST":
        form = form_cls(request.POST)
        formset = MovementEditLineFormSet(request.POST, prefix="lines")
        if form.is_valid() and formset.is_valid():
            try:
                assert_no_future_date(form.cleaned_data["date_issued"])
            except ValidationError as exc:
                form.add_error("date_issued", exc)
            else:
                changes = _movement_field_changes(movement, form, line_field_for_kind)
                line_changes = _line_changes(existing_lines, formset)
                if not changes and not line_changes:
                    messages.info(request, "Beze změn — uložení přeskočeno.")
                    return redirect("inventory:movement_edit", pk=pk)
                try:
                    edit_movement(
                        movement=movement,
                        changes=changes,
                        line_changes=line_changes,
                        reason=form.cleaned_data["reason"],
                        user=request.user,
                    )
                except ValidationError as exc:
                    _push_validation_error_to_formset(exc, formset)
                else:
                    messages.success(request, "Úprava uložena.")
                    return redirect("inventory:movement_edit", pk=pk)
    else:
        initial_lines = [
            {
                "line_id": line.pk,
                "product": line.product,
                "quantity_kg": line.quantity_kg,
                "sarze": line.sarze,
                "expiry": line.expiry,
                "note": line.note,
            }
            for line in existing_lines
        ]
        form_initial = {
            "branch": movement.branch_id,
            "date_issued": movement.date_issued,
            "note": movement.note,
        }
        if movement.kind == Movement.Kind.VYDEJ:
            form_initial["odberatel"] = movement.odberatel_id
        else:
            form_initial["dodavatel"] = movement.dodavatel_id
        form = form_cls(initial=form_initial)
        formset = MovementEditLineFormSet(
            initial=initial_lines, prefix="lines"
        )

    audit_rows = list(
        MovementAudit.objects.filter(movement=movement)
        .select_related("edited_by")
        .order_by("-edited_at", "-id")
    )
    return render(
        request,
        "inventory/movement_edit.html",
        {
            "movement": movement,
            "form": form,
            "formset": formset,
            "existing_lines": existing_lines,
            "audit_rows": audit_rows,
            "dodaci_list": DodaciList.objects.filter(movement=movement).first(),
            "is_vydej": movement.kind == Movement.Kind.VYDEJ,
        },
    )


def _form_for_kind(kind: str):
    if kind == Movement.Kind.VYDEJ:
        return VydejEditForm, "odberatel"
    return PrijemEditForm, "dodavatel"


def _movement_field_changes(movement: Movement, form, counterparty_field: str) -> dict:
    """Diff form.cleaned_data against the live Movement, returning the
    changes dict expected by edit_movement (Movement-level fields only)."""
    changes: dict = {}
    if form.cleaned_data["branch"] != movement.branch:
        changes["branch"] = form.cleaned_data["branch"]
    if form.cleaned_data["date_issued"] != movement.date_issued:
        changes["date_issued"] = form.cleaned_data["date_issued"]
    if form.cleaned_data.get("note", "") != (movement.note or ""):
        changes["note"] = form.cleaned_data.get("note", "")
    new_cp = form.cleaned_data[counterparty_field]
    old_cp = getattr(movement, counterparty_field)
    if new_cp != old_cp:
        changes[counterparty_field] = new_cp
    return changes


def _line_changes(existing_lines: list[MovementLine], formset) -> list[dict]:
    by_id = {line.pk: line for line in existing_lines}
    ops: list[dict] = []
    seen: set[int] = set()
    for line_form in formset:
        data = line_form.cleaned_data
        if not data:
            continue
        line_id = data.get("line_id")
        if data.get("DELETE"):
            if line_id and line_id in by_id:
                ops.append({"op": "remove", "line_id": line_id})
            continue
        if line_id and line_id in by_id:
            seen.add(line_id)
            existing = by_id[line_id]
            field_diff: dict = {}
            for field in _LINE_EDITABLE_FIELDS:
                new = data.get(field)
                if field in ("sarze", "note"):
                    new = new or ""
                old = getattr(existing, field)
                if old != new:
                    field_diff[field] = new
            if field_diff:
                ops.append({"op": "update", "line_id": line_id, "fields": field_diff})
        else:
            # New line — require product + quantity.
            if data.get("product") is None or data.get("quantity_kg") in (None, ""):
                continue
            ops.append(
                {
                    "op": "add",
                    "fields": {
                        "product": data["product"],
                        "quantity_kg": data["quantity_kg"],
                        "sarze": data.get("sarze", "") or "",
                        "expiry": data.get("expiry"),
                        "note": data.get("note", "") or "",
                    },
                }
            )
    return ops


# ---------------------------------------------------------------------------
# Mixing job (screen 15, per 0039)
# ---------------------------------------------------------------------------


@require_GET
def mixing_job_index(request):
    """Recent mixing jobs, branch-scoped for obsluha."""
    qs = (
        MixingJob.objects.select_related(
            "branch", "mixture", "created_by"
        ).order_by("-started_at", "-id")
    )
    if request.user.is_obsluha and request.user.branch_id:
        qs = qs.filter(branch_id=request.user.branch_id)
    jobs = list(qs[:100])
    return render(
        request,
        "inventory/mixing_job_index.html",
        {"jobs": jobs, "count": len(jobs)},
    )


@require_http_methods(["GET", "POST"])
def mixing_job_create(request):
    """Pick a mixture + target qty → start (default) or one-shot record.

    GET shows the form + (after HTMX preview swap) the derived
    consumption per component vs. on-hand stock.
    POST starts (or records-completed if mode=record) and lands on
    the job detail / branch dashboard.
    """
    mixtures = list(
        Product.objects.filter(
            kind=Product.Kind.MIXTURE,
            is_active=True,
            recipe_components__isnull=False,
        )
        .distinct()
        .order_by("name_cs")
    )
    branches = list(Branch.objects.filter(is_active=True).order_by("code"))
    default_branch = (
        request.user.branch
        if request.user.branch_id
        else (branches[0] if branches else None)
    )

    error: str | None = None
    if request.method == "POST":
        try:
            branch_id = int(request.POST.get("branch", "") or 0)
            branch = Branch.objects.get(pk=branch_id)
        except (ValueError, Branch.DoesNotExist):
            error = "Vyberte pobočku."
            branch = None
        try:
            mixture_id = int(request.POST.get("mixture", "") or 0)
            mixture = Product.objects.get(pk=mixture_id, kind=Product.Kind.MIXTURE)
        except (ValueError, Product.DoesNotExist):
            error = error or "Vyberte směs."
            mixture = None
        try:
            target_qty = Decimal(request.POST.get("target_qty", ""))
        except (InvalidOperation, ValueError):
            error = error or "Cílové množství musí být číslo."
            target_qty = None
        note = request.POST.get("note", "").strip()
        mode = request.POST.get("mode", "start")

        if branch is not None and mixture is not None and target_qty is not None:
            if (
                request.user.is_obsluha
                and request.user.branch_id != branch.pk
            ):
                error = "Nemáte oprávnění pro tuto pobočku."
            else:
                try:
                    if mode == "record":
                        try:
                            actual_produced_qty = Decimal(
                                request.POST.get("actual_produced_qty", "")
                            )
                        except (InvalidOperation, ValueError):
                            actual_produced_qty = target_qty
                        job = record_completed_mixing_job(
                            branch=branch,
                            mixture=mixture,
                            target_qty=target_qty,
                            actual_produced_qty=actual_produced_qty,
                            user=request.user,
                            note=note,
                        )
                        messages.success(
                            request,
                            f"Dávka zaznamenána ({job.actual_produced_qty} kg).",
                        )
                    else:
                        job = start_mixing_job(
                            branch=branch,
                            mixture=mixture,
                            target_qty=target_qty,
                            user=request.user,
                            note=note,
                        )
                        messages.success(
                            request,
                            "Dávka zahájena — pokračujte k dokončení po smíchání.",
                        )
                    return redirect("inventory:mixing_job_detail", pk=job.pk)
                except ValidationError as exc:
                    error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)

    return render(
        request,
        "inventory/mixing_job_create.html",
        {
            "mixtures": mixtures,
            "branches": branches,
            "default_branch": default_branch,
            "is_branch_locked": bool(
                request.user.is_obsluha and request.user.branch_id
            ),
            "error": error,
        },
    )


@require_GET
def mixing_preview_partial(request):
    """HTMX: given branch + mixture + target_qty, return the derived
    consumption table + stock-availability flags."""
    try:
        branch_id = int(request.GET.get("branch", "") or 0)
        branch = Branch.objects.get(pk=branch_id)
    except (ValueError, Branch.DoesNotExist):
        return HttpResponse("")
    try:
        mixture_id = int(request.GET.get("mixture", "") or 0)
        mixture = Product.objects.get(pk=mixture_id, kind=Product.Kind.MIXTURE)
    except (ValueError, Product.DoesNotExist):
        return HttpResponse("")
    try:
        target_qty = Decimal(request.GET.get("target_qty", ""))
        if target_qty <= 0:
            return HttpResponse("")
    except (InvalidOperation, ValueError):
        return HttpResponse("")

    recipe = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
        .select_related("component_product")
        .order_by("component_product__name_cs")
    )
    stock_by_product = {
        s.product_id: s.quantity
        for s in Stock.objects.filter(
            product__in=[rc.component_product_id for rc in recipe],
            branch=branch,
        )
    }
    rows = []
    any_overdraw = False
    for rc in recipe:
        derived = (target_qty * rc.ratio).quantize(Decimal("0.001"))
        on_hand = stock_by_product.get(rc.component_product_id, Decimal("0.000"))
        over = derived > on_hand
        if over:
            any_overdraw = True
        rows.append(
            {
                "component": rc.component_product,
                "ratio": rc.ratio,
                "derived": derived,
                "on_hand": on_hand,
                "over": over,
            }
        )
    return render(
        request,
        "inventory/_mixing_preview.html",
        {
            "rows": rows,
            "any_overdraw": any_overdraw,
            "target_qty": target_qty,
            "mixture": mixture,
        },
    )


@require_GET
def mixing_job_detail(request, pk: int):
    job = get_object_or_404(
        MixingJob.objects.select_related(
            "branch", "mixture", "created_by", "consume_movement", "produce_movement"
        ),
        pk=pk,
    )
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění zobrazit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    lines = list(
        job.lines.select_related("component_product").order_by(
            "component_product__name_cs"
        )
    )
    return render(
        request,
        "inventory/mixing_job_detail.html",
        {"job": job, "lines": lines},
    )


@require_http_methods(["POST"])
def mixing_job_finish(request, pk: int):
    job = get_object_or_404(MixingJob, pk=pk)
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění upravit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    try:
        actual_produced_qty = Decimal(request.POST.get("actual_produced_qty", ""))
    except (InvalidOperation, ValueError):
        messages.error(request, "Skutečné vyrobené množství musí být číslo.")
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    line_actuals: dict[int, Decimal] = {}
    for jl in job.lines.all():
        raw = request.POST.get(f"line-{jl.pk}-actual_qty")
        if raw is None or raw == "":
            continue
        try:
            line_actuals[jl.pk] = Decimal(raw)
        except (InvalidOperation, ValueError):
            messages.error(
                request, f"Spotřeba {jl.component_product} musí být číslo."
            )
            return redirect("inventory:mixing_job_detail", pk=job.pk)
    try:
        finish_mixing_job(
            mixing_job=job,
            actual_produced_qty=actual_produced_qty,
            line_actuals=line_actuals,
            user=request.user,
        )
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    messages.success(request, "Dávka dokončena.")
    return redirect("inventory:mixing_job_detail", pk=job.pk)


@require_http_methods(["POST"])
def mixing_job_cancel(request, pk: int):
    job = get_object_or_404(MixingJob, pk=pk)
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění upravit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "Důvod zrušení je povinný.")
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    try:
        cancel_mixing_job(mixing_job=job, reason=reason, user=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    messages.success(request, "Dávka zrušena.")
    return redirect("inventory:mixing_job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Screen 14 — Nastavení (operator-facing Settings UI)
# ---------------------------------------------------------------------------


def _require_vlastnik(request) -> None:
    if not request.user.is_vlastnik:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Nemáte oprávnění upravovat nastavení.")


def _branch_counters_summary() -> list[dict]:
    """For the read-only 'Číslování' subsection. One entry per branch
    with the latest counter (or None) for the current year."""
    from datetime import date as _date

    year = _date.today().year
    rows = []
    for b in Branch.objects.filter(is_active=True).order_by("code"):
        seq = DodaciListNumberSequence.objects.filter(
            branch=b, year=year
        ).first()
        last = seq.last_counter if seq else 0
        rows.append(
            {
                "branch": b,
                "year": year,
                "last_counter": last,
                "preview": (
                    f"{b.code}-{year}-{last:04d}" if last else f"{b.code}-{year}-—"
                ),
            }
        )
    return rows


def settings_edit(request):
    _require_vlastnik(request)
    instance = Settings.load()
    if request.method == "POST":
        form = SettingsForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Nastavení uloženo.")
            return redirect("inventory:settings_edit")
    else:
        form = SettingsForm(instance=instance)

    smtp_test_form = SmtpTestForm(initial={"to_email": request.user.email})

    return render(
        request,
        "inventory/settings_form.html",
        {
            "form": form,
            "settings": instance,
            "smtp_test_form": smtp_test_form,
            "branch_counters": _branch_counters_summary(),
            "branches": Branch.objects.filter(is_active=True).order_by("code"),
        },
    )


@require_POST
def settings_test_smtp(request):
    _require_vlastnik(request)
    form = SmtpTestForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Neplatná e-mailová adresa.")
        return redirect("inventory:settings_edit")

    to_email = form.cleaned_data["to_email"]
    s = Settings.load()

    # Use the live Settings values, falling back to the env-driven Django
    # defaults if a field is blank. This way the test reflects what a real
    # dodák send will do.
    from django.core.mail import EmailMessage, get_connection

    from_address = s.email_from_address or None
    from_name = s.email_from_name or "Kasia vera"
    sender = (
        f"{from_name} <{from_address}>" if from_address else None
    )

    try:
        connection = get_connection(
            host=s.smtp_host or None,
            port=s.smtp_port or None,
            username=s.smtp_user or None,
            password=s.smtp_password or None,
            use_tls=s.smtp_use_tls,
            timeout=10,
        )
        msg = EmailMessage(
            subject="Test e-mailu — Kasia vera",
            body=(
                "Toto je testovací e-mail z aplikace Kasia vera — sklad. "
                "Pokud čtete tento text, SMTP nastavení funguje."
            ),
            from_email=sender,
            to=[to_email],
            connection=connection,
        )
        msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — surface any SMTP error to operator
        messages.error(
            request,
            f"Test e-mailu selhal: {exc}",
        )
        return redirect("inventory:settings_edit")

    messages.success(request, f"Testovací e-mail odeslán na {to_email}.")
    return redirect("inventory:settings_edit")


# ---------------------------------------------------------------------------
# Pass 5 — Supplier CRUD (per decision 0040)
#
# Tier: all authenticated users (vlastník + obsluha).
# Routes: /dodavatele/, /dodavatele/novy/, /dodavatele/<pk>/upravit/,
#         /dodavatele/<pk>/archivovat/, /dodavatele/<pk>/aktivovat/.
# ---------------------------------------------------------------------------


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


def product_create(request):
    """Create a new product (surovina or směs). All authenticated users.

    Recipe is not editable here; for a new mixture, create it first
    then edit it to add components. Keeps the create form small.
    """
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Produkt {product.name_cs} přidán.")
            if (
                product.kind == Product.Kind.MIXTURE
                and request.user.is_vlastnik
            ):
                # Steer the vlastník straight into recipe editing.
                return redirect("inventory:product_edit", pk=product.pk)
            return redirect("inventory:product_detail", pk=product.pk)
    else:
        form = ProductForm()
    return render(
        request,
        "inventory/product_form.html",
        {"form": form, "mode": "create", "recipe_formset": None},
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

    kind_locked = (
        Stock.objects.filter(product=product).exists()
        or RecipeComponent.objects.filter(
            Q(mixture_product=product) | Q(component_product=product)
        ).exists()
    )

    recipe_qs = RecipeComponent.objects.filter(
        mixture_product=product
    ).order_by("component_product__name_cs")

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product, lock_kind=kind_locked)

        recipe_formset = None
        if can_edit_recipe:
            recipe_formset = RecipeComponentFormSet(
                request.POST,
                queryset=recipe_qs,
                prefix="recipe",
                form_kwargs={"mixture": product},
            )

        forms_valid = form.is_valid()
        if recipe_formset is not None:
            forms_valid = recipe_formset.is_valid() and forms_valid

        if forms_valid:
            form.save()
            if recipe_formset is not None:
                instances = recipe_formset.save(commit=False)
                for inst in instances:
                    inst.mixture_product = product
                    inst.save()
                for deleted in recipe_formset.deleted_objects:
                    deleted.delete()
            messages.success(request, "Změny uloženy.")
            return redirect("inventory:product_detail", pk=product.pk)
    else:
        form = ProductForm(instance=product, lock_kind=kind_locked)
        recipe_formset = (
            RecipeComponentFormSet(
                queryset=recipe_qs,
                prefix="recipe",
                form_kwargs={"mixture": product},
            )
            if can_edit_recipe
            else None
        )

    new_recipe_row = (
        RecipeComponentForm(mixture=product) if can_edit_recipe else None
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
            "kind_locked": kind_locked,
            "can_edit_recipe": can_edit_recipe,
        },
    )


@require_POST
def product_archive(request, pk: int):
    """Soft-archive a product. Vlastník-only per 0040."""
    if not request.user.is_vlastnik:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Pouze vlastník může archivovat produkty.")
    product = get_object_or_404(Product, pk=pk)
    product.is_active = False
    product.save(update_fields=["is_active"])
    messages.success(request, f"Produkt {product.name_cs} archivován.")
    return redirect("inventory:catalogue_index")


@require_POST
def product_reactivate(request, pk: int):
    """Re-activate an archived product. Vlastník-only per 0040."""
    if not request.user.is_vlastnik:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Pouze vlastník může aktivovat produkty.")
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


# ---------------------------------------------------------------------------
# Pass 5c — Branch CRUD (per decision 0040, vlastník-only)
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


def stock_adjust_edit(request, pk: int):
    """Vlastník brings the current Stock(product, branch) to a new value.
    Writes one synthetic Movement; never touches Stock.quantity directly.
    """
    _require_vlastnik(request)
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        form = StockAdjustmentForm(request.POST, product=product)
        if form.is_valid():
            try:
                mv = apply_stock_adjustment(
                    product=product,
                    branch=form.cleaned_data["branch"],
                    new_quantity=form.cleaned_data["new_quantity"],
                    reason=form.cleaned_data["reason"],
                    user=request.user,
                )
            except ValidationError as exc:
                form.add_error(
                    None,
                    "; ".join(exc.messages)
                    if hasattr(exc, "messages")
                    else str(exc),
                )
            else:
                if mv is None:
                    messages.info(request, "Stav je beze změny — nic se nezapsalo.")
                else:
                    messages.success(
                        request,
                        f"Stav upraven (#{mv.pk}). Pohyb najdete v Historii.",
                    )
                return redirect("inventory:product_detail", pk=product.pk)
    else:
        # Pre-fill branch + current quantity for whichever branch the
        # operator most recently looked at; default to first active branch.
        current_stocks = list(
            Stock.objects.filter(product=product)
            .select_related("branch")
            .order_by("branch__code")
        )
        default_branch = (
            current_stocks[0].branch
            if current_stocks
            else Branch.objects.filter(is_active=True).first()
        )
        default_qty = (
            current_stocks[0].quantity
            if current_stocks
            else Decimal("0.000")
        )
        form = StockAdjustmentForm(
            product=product,
            initial={
                "branch": default_branch.pk if default_branch else None,
                "new_quantity": default_qty,
            },
        )

    # Current per-branch stock summary for context on the form page.
    stocks_by_branch = {
        s.branch_id: s.quantity
        for s in Stock.objects.filter(product=product).select_related("branch")
    }
    branch_rows = [
        {
            "branch": b,
            "quantity": stocks_by_branch.get(b.pk, Decimal("0.000")),
        }
        for b in Branch.objects.filter(is_active=True).order_by("code")
    ]

    return render(
        request,
        "inventory/stock_adjust_form.html",
        {
            "product": product,
            "form": form,
            "branch_rows": branch_rows,
        },
    )


# ---------------------------------------------------------------------------
# Pass 5e — Bulk stock editor (inventura), per decision 0041
#
# /katalog/inventura/<code>/ — vlastník picks a branch, walks through every
# product, edits the quantities inline, hits "Uložit všechny změny". Each
# non-zero delta becomes one synthetic Movement (apply_stock_adjustment),
# sharing the same batch reason. Zero-delta rows are skipped.
# ---------------------------------------------------------------------------


def inventura_edit(request, code: str):
    _require_vlastnik(request)
    branch = get_object_or_404(Branch, code=code.upper(), is_active=True)

    products = list(
        Product.objects.filter(is_active=True).order_by("name_cs")
    )
    stocks_by_product = {
        s.product_id: s.quantity
        for s in Stock.objects.filter(branch=branch).select_related("product")
    }

    if request.method == "POST":
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(
                request, "Důvod úpravy (popis inventury) je povinný."
            )
        else:
            written = 0
            errors: list[str] = []
            for p in products:
                raw = request.POST.get(f"qty_{p.pk}", "").strip()
                if not raw:
                    continue
                try:
                    new_qty = Decimal(raw)
                except (InvalidOperation, ValueError):
                    errors.append(
                        f"{p.name_cs}: neplatné číslo: {raw}"
                    )
                    continue
                current = stocks_by_product.get(p.pk, Decimal("0.000"))
                if new_qty == current:
                    continue
                try:
                    mv = apply_stock_adjustment(
                        product=p,
                        branch=branch,
                        new_quantity=new_qty,
                        reason=reason,
                        user=request.user,
                    )
                except ValidationError as exc:
                    errors.append(
                        f"{p.name_cs}: "
                        + ("; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
                    )
                    continue
                if mv is not None:
                    written += 1
            if errors:
                for err in errors:
                    messages.error(request, err)
            if written:
                messages.success(
                    request,
                    f"Inventura: zaevidováno {written} pohyb"
                    f"{'' if written == 1 else 'y' if 2 <= written <= 4 else 'ů'} "
                    f"na pobočce {branch.code}.",
                )
            elif not errors:
                messages.info(request, "Žádné změny — nic se nezapsalo.")
            if not errors:
                return redirect(
                    f"/katalog/?branch={branch.code}"
                )

    rows = [
        {
            "product": p,
            "current": stocks_by_product.get(p.pk, Decimal("0.000")),
        }
        for p in products
    ]
    return render(
        request,
        "inventory/inventura_edit.html",
        {
            "branch": branch,
            "rows": rows,
            "all_branches": Branch.objects.filter(is_active=True).order_by("code"),
        },
    )
