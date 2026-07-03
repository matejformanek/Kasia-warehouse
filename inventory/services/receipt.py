"""Planned receipt (objednavka) confirm."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    Movement,
    MovementLine,
    Supplier,
)
from .stock import _apply_line_to_stock

_ORDER_COUNTERPARTY_NAME = "Objednávka"
_ORDER_NOTE_PREFIX = "[OBJ] "


def _order_counterparty() -> Supplier:
    """The seeded internal supplier used on the príjem leg of a confirmed
    planned receipt that has no real supplier (mirror of
    `_adjustment_supplier`)."""
    return Supplier.objects.get(
        name=_ORDER_COUNTERPARTY_NAME, is_internal=True
    )


def confirm_planned_receipt(
    *,
    movement: Movement,
    line_qty_by_id: dict[int, Decimal],
    supplier: Supplier | None = None,
    as_of: date | None = None,
    user,
) -> Movement:
    """Confirm arrival of a PLANNED príjem (objednávka) per 0059.

    Reads the movement's existing PLANNED lines, applies the operator-edited
    quantities from `line_qty_by_id` (keyed by MovementLine pk), deletes any
    line set to 0, flips the movement to DONE with `date_issued = as_of or
    today`, sets a supplier (existing → `supplier` arg → internal
    "Objednávka" fallback), and then applies each remaining line to stock
    (negative stock is checked here, not at plan time). No dodák / e-mail
    (PRIJEM never issues one).

    This is a standalone service, NOT an `apply_movement` call — the lines
    already exist. Refuses a non-PLANNED movement.
    """
    if movement.status != Movement.Status.PLANNED:
        raise ValidationError(
            {"status": "Potvrdit lze pouze plánovaný příjem."}
        )
    if movement.kind != Movement.Kind.PRIJEM:
        raise ValidationError({"kind": "Plánovaný pohyb musí být příjem."})

    issue_date = as_of or date.today()

    with transaction.atomic():
        lines = list(movement.lines.select_related("product"))
        remaining: list[MovementLine] = []
        for line in lines:
            new_qty = line_qty_by_id.get(line.pk, line.quantity_kg)
            new_qty = Decimal(new_qty).quantize(Decimal("0.001"))
            if new_qty < 0:
                raise ValidationError(
                    {"quantity_kg": "Přijaté množství nemůže být záporné."}
                )
            if new_qty == 0:
                line.delete()
                continue
            if new_qty != line.quantity_kg:
                line.quantity_kg = new_qty
                line.full_clean()
                line.save(update_fields=["quantity_kg"])
            remaining.append(line)

        if not remaining:
            raise ValidationError(
                {"lines": "Příjem musí mít alespoň jednu položku s množstvím."}
            )

        movement.status = Movement.Status.DONE
        movement.date_issued = issue_date
        movement.expected_on = None
        movement.dodavatel = (
            movement.dodavatel or supplier or _order_counterparty()
        )
        movement.full_clean()
        movement.save(
            update_fields=["status", "date_issued", "expected_on", "dodavatel"]
        )

        for line in remaining:
            _apply_line_to_stock(line, direction=1)
        return movement


