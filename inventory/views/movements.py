"""Movements: history, prijem, vydej, edit + line helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from ..forms import (
    MovementEditLineFormSet,
    MovementLineForm,
    MovementLineFormSet,
    PrijemEditForm,
    PrijemForm,
    VydejEditForm,
    VydejForm,
    assert_no_future_date,
)
from ..models import (
    Branch,
    DodaciList,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    Stock,
    Supplier,
)
from ..services import (
    apply_movement,
    confirm_planned_receipt,
    edit_movement,
)
from ._shared import _safe_next


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
    planned_count = planned_base.count()
    tab_counts = {
        # "Vše" now unions DONE + PLANNED (per 0066) — planned surfaces here too.
        "all": done_base.count() + planned_count,
        "prijem": done_base.filter(kind=Movement.Kind.PRIJEM).count(),
        "vydej": done_base.filter(kind=Movement.Kind.VYDEJ).count(),
        "inventura": done_base.filter(inventura_filter).count(),
        "edited": done_base.filter(audit_entries__isnull=False).distinct().count(),
        "planned": planned_count,
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
        items = list(planned_base.order_by("expected_on", "id"))
    elif tab == "all":
        # Per 0066: upcoming planned first (soonest arrival), then done history.
        items = list(planned_base.order_by("expected_on", "id")) + list(
            done_base.order_by("-date_issued", "-id")
        )
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
        items = list(qs.order_by("-date_issued", "-id"))

    # Paginate at 50 rows/page (per 0066), replacing the old 200 cap.
    paginator = Paginator(items, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    movements = list(page_obj.object_list)

    # Per-movement total kg for the "Množství" column. Lines are already
    # prefetched, so this sums in Python without extra queries.
    for mv in movements:
        mv.total_kg = sum(
            (line.quantity_kg for line in mv.lines.all()), Decimal("0.000")
        )

    # Query string (minus page) so pagination links keep the current filters.
    page_params = {"tab": tab}
    if request.GET.get("branch"):
        page_params["branch"] = request.GET.get("branch")
    if date_from:
        page_params["date_from"] = date_from
    if date_to:
        page_params["date_to"] = date_to
    if search:
        page_params["q"] = search
    page_querystring = urlencode(page_params)

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
            "count": paginator.count,
            "page_obj": page_obj,
            "page_querystring": page_querystring,
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


