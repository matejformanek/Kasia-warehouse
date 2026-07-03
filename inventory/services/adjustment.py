"""Manual stock adjustment / inventura."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from ..models import (
    Branch,
    Customer,
    Movement,
    MovementLine,
    Product,
    Stock,
    Supplier,
)
from . import counterparties
from .movement import apply_movement, build_movement

_ADJUSTMENT_NOTE_PREFIX = "[STAV] "


def _adjustment_supplier() -> Supplier:
    return counterparties.supplier("adjustment")


def _adjustment_customer() -> Customer:
    return counterparties.customer("adjustment")


def apply_stock_adjustment(
    *,
    product: Product,
    branch: Branch,
    new_quantity: Decimal,
    reason: str,
    user,
    as_of: date | None = None,
) -> Movement | None:
    """Bring `Stock(product, branch).quantity` to `new_quantity` by
    writing one synthetic Movement.

    Per [0041](../context/decisions/0041-manual-stock-adjustment.md):
    every Stock delta goes through `apply_movement`, never raw
    UPDATE. The delta determines the kind:
        delta > 0 → prijem from internal "Inventura / ruční úprava"
        delta < 0 → vydej to   internal "Inventura / ruční úprava"
        delta = 0 → noop (returns None)
    The Movement's note is `"[STAV] " + reason` so it shows up
    cleanly in Historie and can be filtered out by a future
    inventura-tab.

    The internal counterparty has `is_internal=True` so the dodák
    hook in apply_movement is skipped (no PDF, no e-mail).
    """
    from decimal import Decimal as _D
    if not reason or not reason.strip():
        raise ValidationError(
            {"reason": "Důvod ruční úpravy stavu je povinný."}
        )

    new_quantity = _D(new_quantity)
    if new_quantity < 0:
        raise ValidationError(
            {"new_quantity": "Stav nemůže být záporný."}
        )

    current = Stock.objects.filter(product=product, branch=branch).first()
    current_qty = current.quantity if current else _D("0.000")
    delta = new_quantity - current_qty
    if delta == 0:
        return None

    issue_date = as_of or date.today()
    clean_reason = reason.strip()
    note = f"{_ADJUSTMENT_NOTE_PREFIX}{clean_reason}"

    if delta > 0:
        # Stock up: synthetic prijem from internal supplier.
        movement = build_movement(
            branch=branch,
            kind=Movement.Kind.PRIJEM,
            counterparty=_adjustment_supplier(),
            date_issued=issue_date,
            note=note,
            created_by=user,
        )
    else:
        # Stock down: synthetic vydej to internal customer.
        movement = build_movement(
            branch=branch,
            kind=Movement.Kind.VYDEJ,
            counterparty=_adjustment_customer(),
            date_issued=issue_date,
            note=note,
            created_by=user,
        )

    line = MovementLine(product=product, quantity_kg=abs(delta))
    return apply_movement(movement=movement, lines=[line], user=user)


# ---------------------------------------------------------------------------
# Reorder threshold + reservations + low-stock summary
# (per decisions 0043 + 0044 + 0045)
# ---------------------------------------------------------------------------


