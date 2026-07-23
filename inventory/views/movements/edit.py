"""Movement edit (screen 11) + its field/line diff helpers."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ...forms import (
    MovementEditLineFormSet,
    PrijemEditForm,
    VydejEditForm,
    assert_no_future_date,
)
from ...models import (
    DodaciList,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
)
from ...services import counterparties, edit_movement
from ._shared import _push_validation_error_to_formset

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
    is_vydej = movement.kind == Movement.Kind.VYDEJ

    if request.method == "POST":
        form = form_cls(request.POST)
        # Per 0095: příjem-edit excludes finished products; výdej-edit keeps them.
        formset = MovementEditLineFormSet(
            request.POST, prefix="lines",
            form_kwargs={"exclude_finished": not is_vydej},
        )
        if form.is_valid() and formset.is_valid():
            # Per 0086: výdej is dateless (field popped from VydejEditForm) — no
            # date to validate. Príjem edit still guards against a future date.
            date_error = None
            if not is_vydej:
                try:
                    assert_no_future_date(form.cleaned_data["date_issued"])
                except ValidationError as exc:
                    date_error = exc
            if date_error is not None:
                form.add_error("date_issued", date_error)
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
            initial=initial_lines, prefix="lines",
            form_kwargs={"exclude_finished": not is_vydej},
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
            "is_vydej": is_vydej,
            # Per 0095: finished-product pks so the per-row unit label shows „ks"
            # (and the qty input goes integer-only). Only výdej can carry them.
            "finished_product_ids": list(
                Product.objects.filter(
                    is_active=True, kind=Product.Kind.HOTOVY_VYROBEK
                ).values_list("pk", flat=True)
            ),
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
    # Per 0086: výdej edit has no date_issued field (popped) — skip it.
    if "date_issued" in form.cleaned_data:
        if form.cleaned_data["date_issued"] != movement.date_issued:
            changes["date_issued"] = form.cleaned_data["date_issued"]
    if form.cleaned_data.get("note", "") != (movement.note or ""):
        changes["note"] = form.cleaned_data.get("note", "")
    new_cp = form.cleaned_data[counterparty_field]
    # Per 0085: a blank dodavatel on příjem edit means "Neuveden", never NULL
    # (the DB constraint requires a supplier on PRIJEM).
    if counterparty_field == "dodavatel" and new_cp is None:
        new_cp = counterparties.supplier("unknown_supplier")
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
