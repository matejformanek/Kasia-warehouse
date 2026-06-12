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
    MovementEditLineFormSet,
    MovementLineForm,
    MovementLineFormSet,
    PrijemEditForm,
    PrijemForm,
    VydejEditForm,
    VydejForm,
    assert_no_future_date,
)
from .models import (
    Branch,
    DodaciList,
    DodaciListEmailLog,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    Stock,
)
from .services import apply_movement, edit_movement, render_dodaci_list_pdf, send_dodaci_list_email


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

    Obsluha users are strictly scoped to their own branch; vlastník
    users see both and can filter by branch via `?branch=<pk>`.
    Other filters: kind (`prijem` / `vydej`), `date_from`, `date_to`,
    `edited` (1 to show only movements with audit rows), `q` (free
    text icontains across counterparty name + line product name +
    note).
    """
    from datetime import date as _date

    qs = (
        Movement.objects.select_related(
            "branch", "odberatel", "dodavatel", "created_by"
        )
        .prefetch_related("lines__product", "audit_entries")
    )

    # Branch scoping — obsluha forced to own branch.
    if request.user.is_obsluha and request.user.branch_id:
        qs = qs.filter(branch_id=request.user.branch_id)
        branch_locked = request.user.branch
    else:
        branch_locked = None
        branch_filter = request.GET.get("branch") or ""
        if branch_filter:
            qs = qs.filter(branch_id=branch_filter)

    kind = request.GET.get("kind") or ""
    if kind in (Movement.Kind.PRIJEM, Movement.Kind.VYDEJ):
        qs = qs.filter(kind=kind)

    date_from = request.GET.get("date_from") or ""
    date_to = request.GET.get("date_to") or ""

    def _parse(s: str):
        try:
            return _date.fromisoformat(s)
        except ValueError:
            return None

    df, dt = _parse(date_from), _parse(date_to)
    if df is not None:
        qs = qs.filter(date_issued__gte=df)
    if dt is not None:
        qs = qs.filter(date_issued__lte=dt)

    if request.GET.get("edited") == "1":
        # "movement has any audit row" → join + distinct.
        qs = qs.filter(audit_entries__isnull=False).distinct()

    search = (request.GET.get("q") or "").strip()
    if search:
        qs = qs.filter(
            Q(odberatel__name__icontains=search)
            | Q(dodavatel__name__icontains=search)
            | Q(lines__product__name_cs__icontains=search)
            | Q(note__icontains=search)
        ).distinct()

    qs = qs.order_by("-date_issued", "-id")[:200]
    movements = list(qs)

    branches = list(Branch.objects.filter(is_active=True).order_by("code"))

    return render(
        request,
        "inventory/movement_history.html",
        {
            "movements": movements,
            "count": len(movements),
            "branches": branches,
            "branch_locked": branch_locked,
            "filter_branch": request.GET.get("branch") or "",
            "filter_kind": kind,
            "filter_date_from": date_from,
            "filter_date_to": date_to,
            "filter_edited": request.GET.get("edited") == "1",
            "filter_q": search,
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
