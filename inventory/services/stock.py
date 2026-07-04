"""Stock mutation primitive."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ..models import (
    MovementLine,
    Stock,
)


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


