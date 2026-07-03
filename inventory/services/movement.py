"""Movement apply/edit — the core stock write path."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    DodaciList,
    Movement,
    MovementAudit,
    MovementLine,
)
from .dodaci_list import (
    _create_dodaci_list_for_movement,
    render_dodaci_list_pdf,
    send_dodaci_list_email,
)
from .email import _assert_recipients_set
from .stock import _apply_line_to_stock

_MOVEMENT_AUDITABLE_FIELDS = ("kind", "branch", "date_issued", "odberatel", "dodavatel", "note")
_LINE_AUDITABLE_FIELDS = ("product", "quantity_kg", "sarze", "expiry", "note")


def build_movement(
    *,
    branch,
    kind: str,
    counterparty,
    date_issued,
    note: str = "",
    transfer=None,
    created_by=None,
) -> Movement:
    """Construct an (unsaved) Movement, routing the counterparty to the correct
    field for its kind (výdej → odberatel, příjem → dodavatel — mirroring the
    model's counterparty CheckConstraint). Single construction point for the
    system-generated movements (mixing, transfer, adjustment); callers pass the
    lines and hand it to ``apply_movement``.
    """
    kwargs: dict[str, Any] = {
        "branch": branch,
        "kind": kind,
        "date_issued": date_issued,
        "note": note,
    }
    if kind == Movement.Kind.VYDEJ:
        kwargs["odberatel"] = counterparty
    else:
        kwargs["dodavatel"] = counterparty
    if transfer is not None:
        kwargs["transfer"] = transfer
    if created_by is not None:
        kwargs["created_by"] = created_by
    return Movement(**kwargs)


def _render(value: Any) -> str:
    """String-render a field value for the audit log. Empty for None."""
    if value is None:
        return ""
    return str(value)


def _line_summary(line: MovementLine) -> str:
    """Human-readable one-line snapshot of a MovementLine for line_added /
    line_removed audit entries."""
    parts = [f"{line.product} {line.quantity_kg} kg"]
    if line.sarze:
        parts.append(f"šarže {line.sarze}")
    if line.expiry:
        parts.append(f"exp {line.expiry.isoformat()}")
    if line.note:
        parts.append(line.note)
    return " · ".join(parts)



def apply_movement(
    *,
    movement: Movement,
    lines: list[MovementLine],
    user,
) -> Movement:
    """Create a Movement + its lines atomically and mutate Stock.

    No MovementAudit rows are written — the Movement row itself (with
    created_at / created_by) is the creation record.
    """
    if not lines:
        raise ValidationError({"lines": "Pohyb musí mít alespoň jednu položku."})

    # Per 0059: a PLANNED (objednávka) príjem records the lines but does NOT
    # touch stock — it is informational until arrival is confirmed via
    # `confirm_planned_receipt`. No recipients / dodák / e-mail either.
    # Negative-stock is not checked at plan time; that happens on confirm.
    if movement.status == Movement.Status.PLANNED:
        if movement.kind != Movement.Kind.PRIJEM:
            raise ValidationError(
                {"status": "Plánovat lze pouze příjem."}
            )
        with transaction.atomic():
            movement.created_by = user
            movement.full_clean()
            movement.save()
            for line in lines:
                line.movement = movement
                line.full_clean()
                line.save()
            return movement

    direction = 1 if movement.kind == Movement.Kind.PRIJEM else -1

    # Internal-counterparty pohyby (e.g. míchání-job consume per
    # decision 0039) bypass the dodák PDF + e-mail path entirely.
    # apply_movement still writes the Movement + decrements stock; the
    # operator-facing surface treats these rows like any other movement
    # except they aren't paired with a DodaciList.
    is_internal_vydej = (
        movement.kind == Movement.Kind.VYDEJ
        and movement.odberatel is not None
        and movement.odberatel.is_internal
    )

    if movement.kind == Movement.Kind.VYDEJ and not is_internal_vydej:
        _assert_recipients_set()

    with transaction.atomic():
        movement.created_by = user
        movement.full_clean()
        movement.save()
        for line in lines:
            line.movement = movement
            line.full_clean()
            line.save()
            _apply_line_to_stock(line, direction=direction)

        if movement.kind == Movement.Kind.VYDEJ and not is_internal_vydej:
            dodaci_list = _create_dodaci_list_for_movement(movement)
            pdf_bytes = render_dodaci_list_pdf(dodaci_list)
            transaction.on_commit(
                lambda dl=dodaci_list, pdf=pdf_bytes: send_dodaci_list_email(
                    dodaci_list=dl,
                    trigger_reason="vystavení",
                    pdf_bytes=pdf,
                )
            )

        return movement


def edit_movement(
    *,
    movement: Movement,
    changes: dict[str, Any],
    line_changes: list[dict[str, Any]],
    reason: str,
    user,
) -> Movement:
    """Edit an existing Movement atomically.

    `changes` is a flat dict of Movement-level field → new value (only
    fields that actually change). `line_changes` is a list of per-line
    operations:

        {"op": "update", "line_id": int, "fields": {field: new_value, ...}}
        {"op": "add", "fields": {"product": prod, "quantity_kg": Dec, ...}}
        {"op": "remove", "line_id": int}

    Writes one MovementAudit row per *changed* movement field, per
    *changed* line field, and per add / remove event. Recomputes Stock
    deltas; rolls back the whole edit if stock would go negative.
    """
    if not reason or not reason.strip():
        raise ValidationError({"reason": "Důvod úpravy je povinný."})
    if "kind" in changes:
        raise ValidationError({"kind": "Druh pohybu nelze změnit úpravou; vytvořte nový pohyb."})

    direction = 1 if movement.kind == Movement.Kind.PRIJEM else -1

    with transaction.atomic():
        audit_rows: list[MovementAudit] = []

        # ---- Movement-level field changes ------------------------------------
        for field, new_value in changes.items():
            if field not in _MOVEMENT_AUDITABLE_FIELDS:
                raise ValidationError({field: f"Pole '{field}' nelze upravit."})
            old_value = getattr(movement, field)
            if old_value == new_value:
                continue
            audit_rows.append(
                MovementAudit(
                    movement=movement,
                    edited_by=user,
                    reason=reason,
                    target_kind=MovementAudit.TargetKind.MOVEMENT,
                    line_id=None,
                    event=MovementAudit.Event.FIELD_CHANGED,
                    field=field,
                    old_value=_render(old_value),
                    new_value=_render(new_value),
                )
            )
            setattr(movement, field, new_value)

        if any(c for c in changes if c in _MOVEMENT_AUDITABLE_FIELDS):
            movement.full_clean()
            movement.save()

        # ---- Per-line changes ------------------------------------------------
        for op in line_changes:
            action = op.get("op")
            if action == "update":
                line = MovementLine.objects.select_related("movement", "product").get(
                    pk=op["line_id"], movement=movement
                )
                fields = op.get("fields", {})
                # Snapshot the stock-relevant pair before mutating.
                old_product = line.product
                old_quantity = line.quantity_kg

                changed_any = False
                stock_relevant_change = False
                for field, new_value in fields.items():
                    if field not in _LINE_AUDITABLE_FIELDS:
                        raise ValidationError({field: f"Pole položky '{field}' nelze upravit."})
                    old_value = getattr(line, field)
                    if old_value == new_value:
                        continue
                    changed_any = True
                    if field in ("quantity_kg", "product"):
                        stock_relevant_change = True
                    audit_rows.append(
                        MovementAudit(
                            movement=movement,
                            edited_by=user,
                            reason=reason,
                            target_kind=MovementAudit.TargetKind.LINE,
                            line_id=line.pk,
                            event=MovementAudit.Event.FIELD_CHANGED,
                            field=field,
                            old_value=_render(old_value),
                            new_value=_render(new_value),
                        )
                    )
                    setattr(line, field, new_value)

                if not changed_any:
                    continue

                if stock_relevant_change:
                    reverse_line = MovementLine(
                        movement=movement,
                        product=old_product,
                        quantity_kg=old_quantity,
                    )
                    _apply_line_to_stock(reverse_line, direction=-direction)
                    line.full_clean()
                    line.save()
                    _apply_line_to_stock(line, direction=direction)
                else:
                    line.full_clean()
                    line.save()

            elif action == "add":
                fields = op.get("fields", {})
                line = MovementLine(movement=movement, **fields)
                line.full_clean()
                line.save()
                _apply_line_to_stock(line, direction=direction)
                audit_rows.append(
                    MovementAudit(
                        movement=movement,
                        edited_by=user,
                        reason=reason,
                        target_kind=MovementAudit.TargetKind.LINE,
                        line_id=line.pk,
                        event=MovementAudit.Event.LINE_ADDED,
                        field="",
                        old_value="",
                        new_value=_line_summary(line),
                    )
                )

            elif action == "remove":
                line = MovementLine.objects.select_related("movement", "product").get(
                    pk=op["line_id"], movement=movement
                )
                summary = _line_summary(line)
                _apply_line_to_stock(line, direction=-direction)
                line_pk = line.pk
                line.delete()
                audit_rows.append(
                    MovementAudit(
                        movement=movement,
                        edited_by=user,
                        reason=reason,
                        target_kind=MovementAudit.TargetKind.LINE,
                        line_id=line_pk,
                        event=MovementAudit.Event.LINE_REMOVED,
                        field="",
                        old_value=summary,
                        new_value="",
                    )
                )

            else:
                raise ValidationError({"op": f"Neznámá operace položky: {action!r}."})

        MovementAudit.objects.bulk_create(audit_rows)

        # Per decision 0007: a movement edit on a posted dodák bumps the
        # internal version counter, re-renders the PDF against current
        # data + template, and re-sends with an [OPRAVA] subject. The
        # send itself runs on commit so a rollback of the outer atomic
        # block (e.g. a stock overdraw later) skips the e-mail entirely.
        dodaci_list = DodaciList.objects.filter(movement=movement).first()
        if dodaci_list is not None:
            _assert_recipients_set()
            dodaci_list.current_version += 1
            dodaci_list.save(update_fields=["current_version"])
            pdf_bytes = render_dodaci_list_pdf(dodaci_list)
            transaction.on_commit(
                lambda dl=dodaci_list, pdf=pdf_bytes, r=reason: send_dodaci_list_email(
                    dodaci_list=dl,
                    trigger_reason=f"oprava: {r}",
                    pdf_bytes=pdf,
                )
            )

        return movement


# ---------------------------------------------------------------------------
# Dodací list services (per 0007 / 0008 / 0017 / 0019 / 0031 / 0036 / 0037)
# ---------------------------------------------------------------------------


