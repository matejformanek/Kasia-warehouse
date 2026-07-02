"""HTMX-driven views for the operator-facing surface (Pass 3a).

Auth: LoginRequiredMiddleware redirects anonymous users to /login/;
views need no decorator unless they intentionally opt out.

Pass 3a screens:
- home — landing after login (placeholder until screen 02 in Pass 3c)
- prijem_create — screen 06
- vydej_create — screen 07 (with HTMX stock-cap warning)
- movement_saved — landing page after a successful create
- line_row_partial — HTMX add-row endpoint
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    BranchForm,
    CustomerForm,
    FeedbackForm,
    MixingPlanForm,
    MovementEditLineFormSet,
    MovementLineForm,
    MovementLineFormSet,
    PlannedTransferForm,
    PrijemEditForm,
    PrijemForm,
    ProductForm,
    RecipeComponentForm,
    RecipeComponentFormSet,
    SettingsForm,
    SettingsRecipientFormSet,
    SmtpTestForm,
    SupplierForm,
    ThresholdOverrideFormSet,
    VydejEditForm,
    VydejForm,
    XLSImportReviewHeaderForm,
    XLSImportReviewLineFormSet,
    XLSImportUploadForm,
    assert_no_future_date,
)
from .models import (
    Branch,
    Customer,
    DodaciList,
    DodaciListEmailLog,
    DodaciListNumberSequence,
    Feedback,
    MixingJob,
    Movement,
    MovementAudit,
    MovementLine,
    PlannedTransfer,
    Product,
    RecipeComponent,
    Settings,
    Stock,
    StockThresholdOverride,
    Supplier,
)
from .services import (
    _smtp_connection_from_settings,
    apply_movement,
    apply_stock_adjustment,
    cancel_mixing_job,
    cancel_planned_transfer,
    confirm_planned_receipt,
    create_mixture_from_review,
    edit_movement,
    execute_planned_transfer,
    finish_mixing_job,
    low_stock_rows,
    parse_recipe_xls,
    plan_mixing_job,
    record_completed_mixing_job,
    render_dodaci_list_pdf,
    render_recipe_pdf,
    reserved_kg,
    seed_branch_carriage_for_product,
    send_dodaci_list_email,
    start_mixing_job,
    threshold_for,
)


def _dl_failed_at_current_version(dodaci_list: DodaciList, logs) -> bool:
    """True iff there is ≥1 FAILED log at current_version AND no SENT log
    at current_version. Matches the dashboard's "K vyřešení" rule so the
    detail-screen banner drops out the moment a re-send succeeds.
    """
    at_cv = [log for log in logs if log.version == dodaci_list.current_version]
    if not at_cv:
        return False
    any_sent = any(log.status == DodaciListEmailLog.Status.SENT for log in at_cv)
    if any_sent:
        return False
    return any(log.status == DodaciListEmailLog.Status.FAILED for log in at_cv)


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
            Movement.objects.filter(branch=b, status=Movement.Status.DONE)
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
    # successfully at the current version. Uses the same rule as the
    # per-detail banner in `dodaci_list_detail` via
    # `_dl_failed_at_current_version`.
    failed_dodaky = []
    for dl in DodaciList.objects.prefetch_related("email_logs"):
        logs = list(dl.email_logs.all())
        if not _dl_failed_at_current_version(dl, logs):
            continue
        logs_at_current = [log for log in logs if log.version == dl.current_version]
        last_failed = max(
            (
                log
                for log in logs_at_current
                if log.status == DodaciListEmailLog.Status.FAILED
            ),
            key=lambda log: log.sent_at,
        )
        failed_dodaky.append({"dodaci_list": dl, "last_failed": last_failed})

    # Recently edited dodáky (current_version > 1), latest first, top 5.
    edited_dodaky = list(
        DodaciList.objects.select_related("branch", "odberatel")
        .filter(current_version__gt=1)
        .order_by("-id")[:5]
    )

    # "Dochází zboží" panel per 0043 + 0044 — reads the same
    # low_stock_rows() that feeds the daily summary e-mail.
    low_stock = low_stock_rows()
    # Per 0057: sink rows that already have an open objednávka to the
    # bottom. Presentation only — membership + the service deficit-DESC
    # sort are untouched, so this panel and the digest agree on contents.
    low_stock_display = [r for r in low_stock if r.ordered_kg is None] + [
        r for r in low_stock if r.ordered_kg is not None
    ]

    # KPI overview strip (decision 0054). All four are derivable from the
    # aggregates already computed above for the per-branch panels.
    kpi_products = sum(p["product_count"] for p in branch_panels)
    kpi_total_mass = sum((p["total_mass"] for p in branch_panels), Decimal("0.000"))

    return render(
        request,
        "inventory/home.html",
        {
            "branch_panels": branch_panels,
            "recent_dodaky": recent_dodaky,
            "failed_dodaky": failed_dodaky,
            "edited_dodaky": edited_dodaky,
            "low_stock_rows": low_stock_display,
            "can_order": request.user.is_vlastnik,
            "to_resolve_count": len(failed_dodaky) + len(edited_dodaky),
            "kpi_products": kpi_products,
            "kpi_total_mass": kpi_total_mass,
            "kpi_low_stock": len(low_stock),
            "kpi_branches": len(branches),
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

    # Per 0063: text search (`q`) is filtered client-side in the browser
    # (diacritic-insensitive, typo-tolerant, as-you-type) over the rendered
    # rows. The server only echoes the term back into the input. Date, branch,
    # and tab stay server-side and pre-narrow the (200-capped) set as before;
    # the "Nalezeno" / tab counts therefore reflect server totals, not the
    # client-typed text.
    search = (request.GET.get("q") or "").strip()

    # Per 0059: PLANNED príjmy (objednávky) are NOT history — they live only
    # in the "Plánované" tab. The other tabs are DONE-only (what happened).
    # The date range filters `date_issued` on the history tabs, but the
    # promised `expected_on` on Plánované (date_issued there is just "today").
    def _apply_date(qs, field):
        if df is not None:
            qs = qs.filter(**{f"{field}__gte": df})
        if dt is not None:
            qs = qs.filter(**{f"{field}__lte": dt})
        return qs

    done_base = _apply_date(
        base_qs.filter(status=Movement.Status.DONE), "date_issued"
    )
    planned_base = _apply_date(
        base_qs.filter(
            status=Movement.Status.PLANNED, kind=Movement.Kind.PRIJEM
        ),
        "expected_on",
    )

    inventura_filter = Q(note__startswith="[STAV] ")
    tab_counts = {
        "all": done_base.count(),
        "prijem": done_base.filter(kind=Movement.Kind.PRIJEM).count(),
        "vydej": done_base.filter(kind=Movement.Kind.VYDEJ).count(),
        "inventura": done_base.filter(inventura_filter).count(),
        "edited": done_base.filter(audit_entries__isnull=False).distinct().count(),
        "planned": planned_base.count(),
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

    if tab == "planned":
        # Worklist ordering: soonest arrival first.
        qs = planned_base.order_by("expected_on", "id")[:200]
    else:
        qs = done_base
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
        ("planned", "Plánované", tab_counts["planned"]),
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
    # Per 0063: the product search (`q`) is filtered client-side in the browser
    # over the rendered stock rows. The server only echoes the term back into
    # the input. KPIs are branch-wide (not search-scoped), so they are
    # unaffected.
    search = (request.GET.get("q") or "").strip()
    stocks = list(stocks_qs)
    # Threshold-aware status per 0043 + 0044. Replaces the old hardcoded
    # `< 1 kg` near-empty marker.
    stock_rows = []
    for s in stocks:
        threshold = threshold_for(s.product, branch)
        reserved = reserved_kg(s.product, branch)
        effective = (s.quantity - reserved).quantize(Decimal("0.001"))
        if effective <= 0:
            status = "prazdne"
        elif threshold is not None and effective < threshold:
            status = "dochazi"
        else:
            status = ""
        stock_rows.append(
            {
                "stock": s,
                "reserved": reserved,
                "effective": effective,
                "threshold": threshold,
                "status": status,
            }
        )

    recent_movements = list(
        Movement.objects.filter(branch=branch, status=Movement.Status.DONE)
        .select_related("odberatel", "dodavatel", "created_by")
        .prefetch_related("lines__product")
        .order_by("-date_issued", "-id")[:15]
    )

    # Per-branch KPI header (decision 0054). Computed branch-wide, not over
    # the search-filtered list, so the numbers stay stable while searching.
    from django.db.models import Sum

    kpi_products = Stock.objects.filter(branch=branch, quantity__gt=0).count()
    kpi_total_mass = Stock.objects.filter(branch=branch).aggregate(
        s=Sum("quantity")
    )["s"] or Decimal("0.000")
    kpi_low_stock = sum(
        1 for r in low_stock_rows() if r.branch.pk == branch.pk
    )

    return render(
        request,
        "inventory/branch_dashboard.html",
        {
            "branch": branch,
            "stocks": stocks,
            "stock_rows": stock_rows,
            "recent_movements": recent_movements,
            "search": search,
            "kpi_products": kpi_products,
            "kpi_total_mass": kpi_total_mass,
            "kpi_low_stock": kpi_low_stock,
        },
    )


# ---------------------------------------------------------------------------
# Příjem (screen 06)
# ---------------------------------------------------------------------------


_RECENT_MOVEMENTS_ON_FORM_LIMIT = 5


def _recent_movements_for_form(user, kind: str):
    """Last N movements of the given kind, scoped to obsluha's branch
    when applicable. Rendered under the create form so operators can
    eyeball what happened on this branch in the last few days without
    leaving the page."""
    qs = (
        Movement.objects.filter(kind=kind, status=Movement.Status.DONE)
        .select_related("branch", "dodavatel", "odberatel", "dodaci_list")
        .prefetch_related("lines__product")
        .order_by("-date_issued", "-id")
    )
    if user.is_obsluha and user.branch_id:
        qs = qs.filter(branch_id=user.branch_id)
    return list(qs[:_RECENT_MOVEMENTS_ON_FORM_LIMIT])


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

    # Embed the per-(branch, product) on-hand map so the výdej form can run
    # the live over-stock check purely in the browser — no htmx round-trip.
    # Basis is raw Stock.quantity (matches _compute_overdraw). Missing pairs
    # are absent here and treated as 0 by the JS. ~2 branches × ~12 products.
    stock_map: dict[str, dict[str, str]] = {}
    for s in Stock.objects.filter(branch__is_active=True).values(
        "branch_id", "product_id", "quantity"
    ):
        stock_map.setdefault(str(s["branch_id"]), {})[str(s["product_id"])] = (
            f'{s["quantity"]:.3f}'
        )

    # Per-branch inventura base URL, so the live over-stock block can offer a
    # vlastník a "fix the stock" jump for the flagged products (per 0060's
    # ?products=&next= contract, same as míchání). Only vlastník may open
    # inventura, so the blob is only emitted for them.
    branch_inventura: dict[str, str] = {}
    if getattr(request.user, "is_vlastnik", False):
        branch_inventura = {
            str(b.pk): reverse("inventory:inventura_edit", args=[b.code])
            for b in Branch.objects.filter(is_active=True)
        }

    return render(
        request,
        "inventory/vydej_form.html",
        {
            "form": form,
            "formset": formset,
            "overdraw_warnings": overdraw_warnings,
            "stock_map": stock_map,
            "branch_inventura": branch_inventura,
            "recent_movements": _recent_movements_for_form(
                request.user, Movement.Kind.VYDEJ
            ),
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
    show_stock_warn = request.GET.get("warn") == "1"
    return render(
        request,
        "inventory/_line_row.html",
        {
            "line_form": form,
            "index": index,
            "is_partial": True,
            "show_stock_warn": show_stock_warn,
        },
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

    # Per 0063: text search (`q`) is filtered client-side in the browser
    # (diacritic-insensitive, typo-tolerant, as-you-type). The server only
    # echoes the term back into the input so it round-trips in the URL and the
    # JS re-applies it on load. Structured filters (kind/status/state/branch)
    # stay server-side.
    search = (request.GET.get("q") or "").strip()

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

    # Reserved + threshold per row, per 0043 + 0044. Scope: the branch
    # in selected_branch (if any) — else aggregate across active branches.
    # The same `reserved_kg` helper that feeds the dashboard panel keeps
    # the numbers consistent.
    reserved_branches = (
        [selected_branch]
        if selected_branch is not None
        else list(Branch.objects.filter(is_active=True))
    )

    # Per 0053: a branch *carries* a product iff a Stock row exists for
    # that pair. Pre-fetch existing rows in scope so chips/thresholds
    # only consider branches that actually carry each product.
    carried_stocks_by_pair: dict[tuple[int, int], Decimal] = {
        (s.product_id, s.branch_id): s.quantity
        for s in Stock.objects.filter(
            product__in=products, branch__in=reserved_branches
        )
    }

    rows = []
    # Per /podpora/ feedback #4: each row carries the list of branches
    # currently under threshold; the template renders one chip per
    # branch but only when no single branch is in scope (the existing
    # per-row "dochází" badge already covers the single-branch case).
    for p in products:
        reserved = Decimal("0.000")
        effective_total = Decimal("0.000")
        threshold_min: Decimal | None = None
        is_low = False
        low_branches: list[Branch] = []
        for b in reserved_branches:
            on_hand = carried_stocks_by_pair.get((p.pk, b.pk))
            if on_hand is None:
                # Branch does not carry this product — skip.
                continue
            r = reserved_kg(p, b)
            reserved += r
            eff_b = on_hand - r
            effective_total += eff_b
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
                "has_recipe": p.pk in has_recipe,
            }
        )

    # Stock state per row (empty overrides low). Reused for the KPI strip,
    # the grouped tables and the ?state= filter.
    def _is_empty(r):
        return r["effective"] <= 0 and r["threshold"] is not None

    def _is_low(r):
        return r["is_low"] and not _is_empty(r)

    # KPI strip aggregates — computed over the whole current scope
    # (status/kind/branch), before the ?state= filter narrows the display.
    kpi_products = len(rows)
    kpi_empty = sum(1 for r in rows if _is_empty(r))
    kpi_low = sum(1 for r in rows if _is_low(r))
    kpi_total_kg = sum((r["total"] for r in rows), Decimal("0.000"))

    state_filter = (request.GET.get("state") or "").strip()
    if state_filter == "low":
        rows = [r for r in rows if _is_low(r)]
    elif state_filter == "empty":
        rows = [r for r in rows if _is_empty(r)]
    elif state_filter == "ok":
        rows = [r for r in rows if not _is_empty(r) and not _is_low(r)]

    # Grouped tables (per 0064) — the template renders only non-empty groups.
    empty_rows = [r for r in rows if _is_empty(r)]
    low_rows = [r for r in rows if _is_low(r)]
    ok_rows = [r for r in rows if not _is_empty(r) and not _is_low(r)]

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
            "current_version_unresolved": _dl_failed_at_current_version(
                dodaci_list, email_logs
            ),
        },
    )


@require_GET
def dodaci_list_pdf(request, cislo: str):
    dodaci_list = get_object_or_404(DodaciList, cislo=cislo)
    pdf_bytes = render_dodaci_list_pdf(dodaci_list)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{dodaci_list.cislo}.pdf"'
    return response


@require_GET
def recipe_pdf(request, pk: int):
    """Download a mixture's recipe sheet (ingredient amounts for the chosen
    batch size + mixing notes) as a PDF. The batch size comes from ``?qty=``
    (the "Spočítat dávku" box; defaults to 100 kg). 404 for non-mixtures or
    recipe-less mixtures."""
    product = get_object_or_404(Product, pk=pk)
    try:
        target_qty = Decimal(request.GET.get("qty", ""))
    except (InvalidOperation, ValueError):
        target_qty = None
    try:
        pdf_bytes = render_recipe_pdf(product, target_qty=target_qty)
    except ValueError as exc:
        raise Http404(str(exc)) from exc
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    slug = slugify(product.name_cs) or f"smes-{product.pk}"
    response["Content-Disposition"] = f'inline; filename="receptura-{slug}.pdf"'
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
    # Per 0059: PLANNED príjmy are edited/confirmed via prijem_confirm, not the
    # DONE-movement editor (which would apply status-aware stock logic).
    if movement.status == Movement.Status.PLANNED:
        return redirect("inventory:prijem_confirm", pk=movement.pk)
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
    """Pick a mixture + target qty → one immediate DONE míchání (per 0060).

    GET shows the form + (after HTMX preview swap) the derived
    consumption per component vs. on-hand stock.
    POST consumes the recipe inputs and adds the blend in one atomic
    action via record_completed_mixing_job() and lands on the job detail.
    On error the form re-renders with every typed value preserved.
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
    # Pre-select the směs when arriving from a recipe page (?mixture=<pk>);
    # keep the selection on POST validation errors.
    selected_mixture_id = (
        request.POST.get("mixture")
        if request.method == "POST"
        else request.GET.get("mixture")
    ) or ""
    # On POST these carry the operator's typed values back into the form so
    # a shortage (or any error) doesn't wipe the entry (per 0060, 3b). On GET
    # they also honour a `?branch=&target_qty=` round-trip from the inventura
    # "Upravit stav surovin" jump so the selection is restored on return.
    selected_branch_id = (
        request.POST.get("branch")
        if request.method == "POST"
        else request.GET.get("branch", "")
        or (str(default_branch.pk) if default_branch else "")
    ) or ""
    target_qty_value = (
        request.POST.get("target_qty", "")
        if request.method == "POST"
        else request.GET.get("target_qty", "")
    )
    actual_produced_value = (
        request.POST.get("actual_produced_qty", "") if request.method == "POST" else ""
    )
    note_value = request.POST.get("note", "") if request.method == "POST" else ""

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

        if branch is not None and mixture is not None and target_qty is not None:
            if (
                request.user.is_obsluha
                and request.user.branch_id != branch.pk
            ):
                error = "Nemáte oprávnění pro tuto pobočku."
            else:
                # "Skutečně vyrobeno" is an optional override; blank → target.
                try:
                    actual_produced_qty = Decimal(
                        request.POST.get("actual_produced_qty", "")
                    )
                except (InvalidOperation, ValueError):
                    actual_produced_qty = target_qty
                try:
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
                        f"Namícháno — {job.actual_produced_qty} kg {mixture.name_cs}.",
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
            "selected_mixture_id": str(selected_mixture_id),
            "selected_branch_id": str(selected_branch_id),
            "target_qty_value": target_qty_value,
            "actual_produced_value": actual_produced_value,
            "note_value": note_value,
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
    # "Upravit stav surovin" jump: per-branch inventura pre-filtered to this
    # blend's components (?products=…), with a `next=` back to the míchání
    # form carrying the current selection (per 0060, 3c).
    component_ids = ",".join(str(rc.component_product_id) for rc in recipe)
    michani_next = (
        reverse("inventory:mixing_job_create")
        + "?"
        + urlencode(
            {
                "branch": branch.pk,
                "mixture": mixture.pk,
                "target_qty": target_qty,
            }
        )
    )
    inventura_link = (
        reverse("inventory:inventura_edit", args=[branch.code])
        + "?"
        + urlencode({"products": component_ids, "next": michani_next})
    )
    return render(
        request,
        "inventory/_mixing_preview.html",
        {
            "rows": rows,
            "any_overdraw": any_overdraw,
            "target_qty": target_qty,
            "mixture": mixture,
            "inventura_link": inventura_link,
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
    from .models import SettingsRecipient
    recipient_qs = SettingsRecipient.objects.all().order_by(
        "-is_active", "sort_order", "id"
    )
    if request.method == "POST":
        form = SettingsForm(request.POST, request.FILES, instance=instance)
        recipient_formset = SettingsRecipientFormSet(
            request.POST, queryset=recipient_qs, prefix="recipient"
        )
        if form.is_valid() and recipient_formset.is_valid():
            form.save()
            recipient_formset.save()
            messages.success(request, "Nastavení uloženo.")
            return redirect("inventory:settings_edit")
    else:
        form = SettingsForm(instance=instance)
        recipient_formset = SettingsRecipientFormSet(
            queryset=recipient_qs, prefix="recipient"
        )

    smtp_test_form = SmtpTestForm(initial={"to_email": request.user.email})

    return render(
        request,
        "inventory/settings_form.html",
        {
            "form": form,
            "recipient_formset": recipient_formset,
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

    # Same code path as the real dodák send — per decision 0049 the
    # helper is the single SMTP-connection construction site.
    from django.core.mail import EmailMessage

    from_address = s.email_from_address or None
    from_name = s.email_from_name or "Kasia vera"
    sender = (
        f"{from_name} <{from_address}>" if from_address else None
    )

    try:
        connection = _smtp_connection_from_settings(s)
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
    ).order_by("component_product__name_cs")
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
                instances = recipe_formset.save(commit=False)
                for inst in instances:
                    inst.mixture_product = product
                    inst.save()
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


def _safe_next(request, default_url: str) -> str:
    """Return a safe internal `next` (POST first, then GET query) if present
    and same-site, else default."""
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default_url


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
    """Vlastník brings the current per-branch Stock of one product to new
    values — table editor: one row per active branch, one shared reason.

    Per [0041](../context/decisions/0041-manual-stock-adjustment.md), every
    delta goes through `apply_stock_adjustment` → `apply_movement` with the
    `[STAV]` prefix; never raw UPDATE. Zero-delta rows are skipped.
    """
    _require_vlastnik(request)
    product = get_object_or_404(Product, pk=pk)

    active_branches = list(
        Branch.objects.filter(is_active=True).order_by("code")
    )
    stocks_by_branch = {
        s.branch_id: s
        for s in Stock.objects.filter(product=product).select_related("branch")
    }

    def _row_for(branch: Branch, posted_value: str | None = None) -> dict:
        stock = stocks_by_branch.get(branch.pk)
        current = stock.quantity if stock else Decimal("0.000")
        reserved = reserved_kg(product, branch) if stock else Decimal("0.000")
        carried = stock is not None
        if posted_value is None:
            new_value = f"{current:.1f}"
        else:
            new_value = posted_value
        return {
            "branch": branch,
            "current": current,
            "reserved": reserved,
            "carried": carried,
            "field_name": f"qty_{branch.pk}",
            "new_value": new_value,
            "error": None,
        }

    rows = [_row_for(b) for b in active_branches]
    reason_value = ""
    reason_error: str | None = None
    non_field_error: str | None = None

    if request.method == "POST":
        reason_value = (request.POST.get("reason") or "").strip()
        # Re-build rows from posted values for re-render on validation errors.
        rows = [
            _row_for(b, request.POST.get(f"qty_{b.pk}", ""))
            for b in active_branches
        ]
        # Parse + collect (branch, new_qty, has_change) per row.
        any_change = False
        parsed: list[tuple[Branch, Decimal]] = []
        for row, branch in zip(rows, active_branches, strict=True):
            raw = (row["new_value"] or "").strip().replace(",", ".")
            if not row["carried"] and raw == "":
                # Nedrží row with no submitted value — user must use Přidat first.
                continue
            if raw == "":
                row["error"] = "Vyplňte hodnotu."
                continue
            try:
                new_qty = Decimal(raw)
            except (InvalidOperation, ValueError):
                row["error"] = "Neplatné číslo."
                continue
            if new_qty < 0:
                row["error"] = "Stav nemůže být záporný."
                continue
            new_qty = new_qty.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            if new_qty != row["current"].quantize(Decimal("0.1")):
                any_change = True
                parsed.append((branch, new_qty))

        if any_change and not reason_value:
            reason_error = "Důvod úpravy je povinný, když měníte hodnoty."
        if not any_change and reason_value:
            # benign — no rows changed; just show info on re-render
            non_field_error = "Žádná hodnota se nezměnila — nic se nezapsalo."

        any_row_error = any(r["error"] for r in rows)

        if not any_row_error and reason_error is None and any_change:
            written = 0
            for branch, new_qty in parsed:
                try:
                    mv = apply_stock_adjustment(
                        product=product,
                        branch=branch,
                        new_quantity=new_qty,
                        reason=reason_value,
                        user=request.user,
                    )
                except ValidationError as exc:
                    non_field_error = (
                        "; ".join(exc.messages)
                        if hasattr(exc, "messages") else str(exc)
                    )
                    break
                if mv is not None:
                    written += 1
            else:
                if written == 1:
                    messages.success(
                        request, "Stav upraven — zapsán 1 pohyb."
                    )
                else:
                    messages.success(
                        request,
                        f"Stav upraven — zapsáno {written} pohybů.",
                    )
                return redirect("inventory:product_detail", pk=product.pk)

        if not any_change and not any_row_error and reason_error is None:
            messages.info(request, "Stav je beze změny — nic se nezapsalo.")
            return redirect("inventory:product_detail", pk=product.pk)

    return render(
        request,
        "inventory/stock_adjust_form.html",
        {
            "product": product,
            "rows": rows,
            "reason_value": reason_value,
            "reason_error": reason_error,
            "non_field_error": non_field_error,
        },
    )


# ---------------------------------------------------------------------------
# Pass 5e — Bulk stock editor (inventura), per decision 0041 + 0057
#
# /katalog/inventura/<code>/ — vlastník picks a branch (or the special
# "dochazi" cross-branch low-stock filter per 0057), walks the rows inline,
# hits "Uložit". Each row carries an optional **Příjezd** date next to its
# new value:
#   - date EMPTY  → the value is the absolute new stock level; a non-zero
#     delta becomes one synthetic `[STAV]` Movement (apply_stock_adjustment),
#     sharing the one batch reason. Zero-delta rows are skipped.
#   - date SET    → the value is the ordered amount (kg); a PLANNED objednávka
#     (per 0057) is created with that expected arrival date. No stock change
#     now — it lands on confirmation from the Objednávky page.
# The reason is required only when at least one immediate adjustment is made.
# ---------------------------------------------------------------------------

_INVENTURA_LOW_CODE = "dochazi"
_INVENTURA_ALL_CODE = "vse"


def inventura_edit(request, code: str):
    from datetime import date

    _require_vlastnik(request)

    is_low = code.lower() == _INVENTURA_LOW_CODE
    is_all = code.lower() == _INVENTURA_ALL_CODE
    cross_branch = is_low or is_all
    all_branches = list(Branch.objects.filter(is_active=True).order_by("code"))

    branch = None
    if not cross_branch:
        branch = get_object_or_404(Branch, code=code.upper(), is_active=True)

    # Optional per-branch component pre-filter (per 0060): the míchání
    # "Upravit stav surovin" jump passes ?products=<pk,pk,…> to restrict the
    # editable rows to a blend's inputs. Ignored by is_low / is_all.
    product_filter_pks: set[int] | None = None
    raw_products = (request.GET.get("products") or "").strip()
    if raw_products and not cross_branch:
        parsed = set()
        for chunk in raw_products.split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                parsed.add(int(chunk))
        product_filter_pks = parsed or None

    def _orders_by_pair() -> dict:
        """All open (PLANNED) príjem lines grouped by (product_id, branch_id)
        — one query, used by the cross-branch views to show inline orders.
        Per 0059 an order is a PLANNED príjem Movement line (was PlannedOrder).
        """
        grouped: dict = {}
        for line in (
            MovementLine.objects.filter(
                movement__status=Movement.Status.PLANNED,
                movement__kind=Movement.Kind.PRIJEM,
            )
            .select_related("product", "movement", "movement__branch")
            .order_by("movement__expected_on", "movement_id", "id")
        ):
            grouped.setdefault(
                (line.product_id, line.movement.branch_id), []
            ).append(line)
        return grouped

    def _build_rows() -> list[dict]:
        """One dict per editable line, each carrying its own POST field
        names so the processing loop is mode-agnostic."""
        if is_low:
            grouped = _orders_by_pair()
            return [
                {
                    "product": r.product,
                    "branch": r.branch,
                    "current": r.on_hand,
                    "qty_field": f"qty_{r.product.pk}_{r.branch.pk}",
                    "eta_field": f"eta_{r.product.pk}_{r.branch.pk}",
                    "qty_value": f"{r.on_hand:.1f}",  # prefill current stock
                    "eta_value": "",
                    "orders": grouped.get((r.product.pk, r.branch.pk), []),
                }
                for r in low_stock_rows()
            ]
        if is_all:
            # Everything across all branches: every active product × every
            # active branch, prefilled with the current stock level.
            grouped = _orders_by_pair()
            products = list(Product.objects.filter(is_active=True).order_by("name_cs"))
            stock_map = {
                (s.product_id, s.branch_id): s.quantity
                for s in Stock.objects.all()
            }
            out = []
            for b in all_branches:
                for p in products:
                    cur = stock_map.get((p.pk, b.pk), Decimal("0.000"))
                    out.append(
                        {
                            "product": p,
                            "branch": b,
                            "current": cur,
                            "qty_field": f"qty_{p.pk}_{b.pk}",
                            "eta_field": f"eta_{p.pk}_{b.pk}",
                            "qty_value": f"{cur:.1f}",
                            "eta_value": "",
                            "orders": grouped.get((p.pk, b.pk), []),
                        }
                    )
            return out
        # Per-branch: every active product, prefilled with current stock.
        # A ?products= pre-filter (per 0060) narrows this to a blend's inputs.
        products_qs = Product.objects.filter(is_active=True)
        if product_filter_pks is not None:
            products_qs = products_qs.filter(pk__in=product_filter_pks)
        products = list(products_qs.order_by("name_cs"))
        stocks_by_product = {
            s.product_id: s.quantity
            for s in Stock.objects.filter(branch=branch).select_related("product")
        }
        return [
            {
                "product": p,
                "branch": branch,
                "current": stocks_by_product.get(p.pk, Decimal("0.000")),
                "qty_field": f"qty_{p.pk}",
                "eta_field": f"eta_{p.pk}",
                "qty_value": f"{stocks_by_product.get(p.pk, Decimal('0.000')):.1f}",
                "eta_value": "",
                "orders": [],
            }
            for p in products
        ]

    rows = _build_rows()

    if request.method == "POST":
        reason = (request.POST.get("reason") or "").strip()
        adjustments: list[tuple] = []  # (product, branch, new_qty)
        orders: list[tuple] = []  # (product, branch, qty, eta)
        errors: list[str] = []

        for row in rows:
            p = row["product"]
            b = row["branch"]
            label = f"{p.name_cs} ({b.code})"
            qty_raw = (request.POST.get(row["qty_field"]) or "").strip().replace(",", ".")
            eta_raw = (request.POST.get(row["eta_field"]) or "").strip()

            if eta_raw:
                # Date set → planned objednávka; value is the ordered amount.
                if not qty_raw:
                    errors.append(f"{label}: u objednávky vyplňte množství.")
                    continue
                try:
                    qty = Decimal(qty_raw)
                except (InvalidOperation, ValueError):
                    errors.append(f"{label}: neplatné množství: {qty_raw}")
                    continue
                try:
                    eta = date.fromisoformat(eta_raw)
                except ValueError:
                    errors.append(f"{label}: neplatné datum: {eta_raw}")
                    continue
                if qty <= 0:
                    errors.append(f"{label}: objednané množství musí být kladné.")
                    continue
                qty = qty.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                orders.append((p, b, qty, eta))
            else:
                # No date → absolute new stock level (immediate correction).
                if not qty_raw:
                    continue
                try:
                    new_qty = Decimal(qty_raw)
                except (InvalidOperation, ValueError):
                    errors.append(f"{label}: neplatné číslo: {qty_raw}")
                    continue
                if new_qty < 0:
                    errors.append(f"{label}: stav nemůže být záporný.")
                    continue
                new_qty = new_qty.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                if new_qty == row["current"].quantize(Decimal("0.1")):
                    continue
                adjustments.append((p, b, new_qty))

        if adjustments and not reason:
            errors.append("Důvod úpravy stavu je povinný, když měníte stav skladu.")

        adjusted = ordered = 0
        if not errors:
            for p, b, new_qty in adjustments:
                try:
                    mv = apply_stock_adjustment(
                        product=p,
                        branch=b,
                        new_quantity=new_qty,
                        reason=reason,
                        user=request.user,
                    )
                except ValidationError as exc:
                    errors.append(
                        f"{p.name_cs} ({b.code}): "
                        + ("; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
                    )
                    continue
                if mv is not None:
                    adjusted += 1
            # Per 0059: group dated rows by (branch, ETA) and create one
            # PLANNED príjem Movement per group (its lines share the header
            # arrival date). No stock touched until confirmation.
            groups: dict[tuple, list[tuple]] = {}
            for p, b, qty, eta in orders:
                groups.setdefault((b.pk, eta), []).append((p, b, qty))
            for (_branch_pk, eta), group_rows in groups.items():
                g_branch = group_rows[0][1]
                movement = Movement(
                    branch=g_branch,
                    kind=Movement.Kind.PRIJEM,
                    status=Movement.Status.PLANNED,
                    date_issued=date.today(),
                    expected_on=eta,
                    note="",
                )
                mv_lines = [
                    MovementLine(product=p, quantity_kg=qty)
                    for (p, _b, qty) in group_rows
                ]
                try:
                    apply_movement(
                        movement=movement, lines=mv_lines, user=request.user
                    )
                except ValidationError as exc:
                    errors.append(
                        f"{g_branch.code} (příjezd {eta.isoformat()}): "
                        + ("; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
                    )
                    continue
                ordered += len(group_rows)

        for err in errors:
            messages.error(request, err)
        if not errors:
            if adjusted or ordered:
                messages.success(
                    request,
                    f"Hotovo — upraveno stavů: {adjusted}, nových objednávek: {ordered}.",
                )
            else:
                messages.info(request, "Žádné změny — nic se nezapsalo.")
            if is_low:
                return redirect("inventory:home")
            if is_all:
                return redirect("inventory:catalogue_index")
            # Per-branch: honour a `next=` round-trip (e.g. back to the míchání
            # form per 0060), else land on the branch-filtered catalogue.
            return redirect(
                _safe_next(
                    request,
                    f"{reverse('inventory:catalogue_index')}?branch={branch.code}",
                )
            )
        # On error: re-render WITHOUT losing anything the user typed.
        # Repopulate every row's inputs from the POST data (the fresh rows
        # built above carry DB defaults only).
        for row in rows:
            row["qty_value"] = request.POST.get(row["qty_field"], row["qty_value"])
            row["eta_value"] = request.POST.get(row["eta_field"], "")
        reason_value = reason
    else:
        reason_value = ""

    # Distinct PLANNED-movement pks referenced by inline orders — the
    # out-of-form cancel forms are emitted once per movement (a planned
    # receipt may span several rows).
    cancelable_movement_pks = sorted(
        {o.movement_id for row in rows for o in row["orders"]}
    )

    return render(
        request,
        "inventory/inventura_edit.html",
        {
            "branch": branch,
            "is_low": is_low,
            "is_all": is_all,
            "cross_branch": cross_branch,
            "rows": rows,
            "all_branches": all_branches,
            "today": date.today(),
            "reason_value": reason_value,
            "cancelable_movement_pks": cancelable_movement_pks,
            # Round-trip back to the míchání form (per 0060); empty for a
            # plain inventura visit. Kept as a hidden field so it survives POST.
            "next_value": (
                request.POST.get("next") or request.GET.get("next") or ""
            ),
        },
    )


# ---------------------------------------------------------------------------
# PlannedTransfer + plánované míchání (Pass 6, per decision 0044).
#
# All authenticated users (Matej 2026-06-14 confirmation). No tier gate
# beyond LoginRequiredMiddleware.
# ---------------------------------------------------------------------------


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


def mixing_plan_create(request):
    """Create a PLANNED MixingJob — no stock consumed. Operator clicks
    "Spustit teď" on the detail page to transition to RUNNING."""
    if request.method == "POST":
        form = MixingPlanForm(request.POST, user=request.user)
        if form.is_valid():
            branch = form.cleaned_data["branch"]
            if (
                request.user.is_obsluha
                and request.user.branch_id != branch.pk
            ):
                form.add_error(
                    "branch", "Nemáte oprávnění pro tuto pobočku."
                )
            else:
                try:
                    job = plan_mixing_job(
                        branch=branch,
                        mixture=form.cleaned_data["mixture"],
                        target_qty=form.cleaned_data["target_qty"],
                        user=request.user,
                        planned_for=form.cleaned_data.get("planned_for"),
                        note=form.cleaned_data.get("note", ""),
                    )
                except ValidationError as exc:
                    form.add_error(
                        None,
                        "; ".join(exc.messages)
                        if hasattr(exc, "messages")
                        else str(exc),
                    )
                else:
                    messages.success(
                        request,
                        f"Plánovaná dávka {job.mixture.name_cs} "
                        f"{job.target_qty} kg vytvořena.",
                    )
                    return redirect("inventory:mixing_job_detail", pk=job.pk)
    else:
        form = MixingPlanForm(user=request.user)
    return render(
        request,
        "inventory/mixing_plan_form.html",
        {"form": form},
    )


@require_POST
def mixing_job_start(request, pk: int):
    """Transition a PLANNED MixingJob to RUNNING (consumes stock)."""
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
        start_mixing_job(job=job, user=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    messages.success(request, "Dávka spuštěna — stav skladu byl odečten.")
    return redirect("inventory:mixing_job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Podpora (in-app docs + feedback log, per decision 0046)
# ---------------------------------------------------------------------------


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
