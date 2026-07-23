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
    # Unlimited products (untracked „Voda“ per 0088, finished „hotový výrobek“
    # per 0095) have no Stock row and no non-negative check, on any movement
    # path — keyed on is_unlimited so a sellable finished good is never deducted
    # (a 0-kg get_or_create would trip the stock_non_negative CHECK on výdej).
    if line.product.is_unlimited:
        return
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


