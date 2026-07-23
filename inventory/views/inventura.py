"""Stock adjustment + inventura editor."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ..models import (
    Branch,
    Movement,
    MovementLine,
    Product,
    Stock,
)
from ..services import (
    apply_movement,
    apply_stock_adjustment,
    low_stock_rows,
    reserved_kg,
)
from ._shared import _require_vlastnik, _safe_next
from .catalogue import catalogue_stock_groups


def _kg1(x: Decimal) -> Decimal:
    """Round a kg quantity to 1 dp with ROUND_HALF_UP — the single source of
    truth for display / prefill / data-current / server no-op compare, so they
    never disagree at ``.x5`` values (per 0061; `floatformat:1` is HALF_UP,
    while Decimal's default HALF_EVEN made 45.45 prefill as 45.4 → phantom edit).
    """
    return x.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


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
            new_value = str(_kg1(current))
        else:
            new_value = posted_value
        return {
            "branch": branch,
            "current": current,
            "current_1dp": _kg1(current),
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
            if new_qty != _kg1(row["current"]):
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

    is_low = code.lower() == _INVENTURA_LOW_CODE
    is_all = code.lower() == _INVENTURA_ALL_CODE
    cross_branch = is_low or is_all
    all_branches = list(Branch.objects.filter(is_active=True).order_by("code"))

    # Per 0073: vlastník may run any inventura (per-branch, "Vše", "Dochází").
    # Obsluha may run inventura ONLY for their own branch — no cross-branch
    # roll-ups, no other branch (403). The single-branch "Dochází" toggle is a
    # client-side row filter, not a separate view, so it stays available.
    if not request.user.is_vlastnik:
        own_code = (
            request.user.branch.code
            if request.user.is_obsluha and request.user.branch_id
            else None
        )
        if own_code is None or cross_branch or code.upper() != own_code:
            raise PermissionDenied("Nemáte oprávnění k této inventuře.")

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
                    "current_1dp": _kg1(r.on_hand),
                    "qty_field": f"qty_{r.product.pk}_{r.branch.pk}",
                    "eta_field": f"eta_{r.product.pk}_{r.branch.pk}",
                    "qty_value": str(_kg1(r.on_hand)),  # prefill current stock
                    "eta_value": "",
                    "orders": grouped.get((r.product.pk, r.branch.pk), []),
                    "below_threshold": False,
                }
                for r in low_stock_rows()
            ]
        if is_all:
            # Everything across all branches: every active product × every
            # active branch, prefilled with the current stock level.
            grouped = _orders_by_pair()
            # Untracked „Voda“ (0088) has no Stock; finished „hotový výrobek“
            # (0095) is unlimited + not counted — both excluded from inventura.
            products = list(
                Product.objects.filter(is_active=True, is_stock_tracked=True)
                .exclude(kind=Product.Kind.HOTOVY_VYROBEK)
                .order_by("name_cs")
            )
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
                            "current_1dp": _kg1(cur),
                            "qty_field": f"qty_{p.pk}_{b.pk}",
                            "eta_field": f"eta_{p.pk}_{b.pk}",
                            "qty_value": str(_kg1(cur)),
                            "eta_value": "",
                            "orders": grouped.get((p.pk, b.pk), []),
                            "below_threshold": False,
                        }
                    )
            return out
        # Per-branch: every active product, prefilled with current stock.
        # A ?products= pre-filter (per 0060) narrows this to a blend's inputs.
        # Per 0088 / 0095: exclude untracked Voda + finished „hotový výrobek“.
        products_qs = Product.objects.filter(
            is_active=True, is_stock_tracked=True
        ).exclude(kind=Product.Kind.HOTOVY_VYROBEK)
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
                "current_1dp": _kg1(stocks_by_product.get(p.pk, Decimal("0.000"))),
                "qty_field": f"qty_{p.pk}",
                "eta_field": f"eta_{p.pk}",
                "qty_value": str(_kg1(stocks_by_product.get(p.pk, Decimal("0.000")))),
                "eta_value": "",
                "orders": [],
                "below_threshold": p.pk in low_pks,
            }
            for p in products
        ]

    # Single-branch "Dochází" toggle (client-side filter): mark each CRITICAL
    # row at this branch — i.e. everything the Katalog would put in Prázdné OR
    # Dochází (per 0080). We reuse `catalogue_stock_groups` (the ONE source of
    # truth for the empty/low grouping, per 0072) rather than `low_stock_rows()`
    # alone: the latter is bare `effective < threshold`, which would MISS a
    # genuinely-empty product whose threshold is 0 (now the default per 0072).
    # Guarded to single-branch mode (branch set).
    low_pks: set[int] = set()
    if not cross_branch:
        _groups = catalogue_stock_groups(
            list(Product.objects.filter(is_active=True)), [branch]
        )
        low_pks = {
            r["product"].pk
            for r in (_groups["empty_rows"] + _groups["low_rows"])
        }

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
                if new_qty == _kg1(row["current"]):
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
            "show_low_toggle": not cross_branch,
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


