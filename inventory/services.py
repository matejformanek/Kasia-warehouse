"""Stock-mutation + audit service for Movement create / edit.

The functions below are the single write path for Movement, MovementLine,
Stock, and MovementAudit. Admin (and future views) call them inside an
atomic block; signals are deliberately avoided so the call graph stays
visible.

See plan: context/state.md § Next item 2 (Pass 1 of 2).
Schema invariants: decisions 0021 + 0035 (audit shape), 0030 (kind enum),
0028 (mass-only), 0001 (šarže optional), 0003 (NUMERIC(10,3)).

Note: select_for_update() is a silent no-op on SQLite. Real concurrency
safety arrives once every code path runs against Postgres. Acceptable
for MVP at ~6 users (per .claude/rules/right-sized-for-small-business.md).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Movement, MovementAudit, MovementLine, Stock

_MOVEMENT_AUDITABLE_FIELDS = ("kind", "branch", "date_issued", "odberatel", "dodavatel", "note")
_LINE_AUDITABLE_FIELDS = ("product", "quantity_kg", "sarze", "expiry", "note")


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


def _apply_line_to_stock(line: MovementLine, *, direction: int) -> None:
    """Mutate the (product, branch) Stock row by `direction * line.quantity_kg`.
    Raises ValidationError if the resulting quantity would go negative."""
    stock, _ = Stock.objects.select_for_update().get_or_create(
        product=line.product,
        branch_id=line.movement.branch_id,
        defaults={"quantity": Decimal("0.000")},
    )
    stock.quantity = stock.quantity + Decimal(direction) * line.quantity_kg
    try:
        # Nested savepoint so a failed CHECK CONSTRAINT rolls back to here,
        # not the whole outer transaction — letting us convert to a friendly
        # ValidationError without leaving the outer atomic block broken.
        with transaction.atomic():
            stock.save()
    except IntegrityError as exc:
        raise ValidationError(
            {
                "quantity_kg": (
                    f"Skladová zásoba by klesla pod nulu "
                    f"(produkt: {line.product}, pobočka: {line.movement.branch.code})."
                )
            }
        ) from exc


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

    direction = 1 if movement.kind == Movement.Kind.PRIJEM else -1

    with transaction.atomic():
        movement.created_by = user
        movement.full_clean()
        movement.save()
        for line in lines:
            line.movement = movement
            line.full_clean()
            line.save()
            _apply_line_to_stock(line, direction=direction)
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

        # TODO Pass 2 — if movement is linked to a posted DodaciList, trigger
        # PDF re-render + [OPRAVA] e-mail per decision 0007.

        return movement
