"""Planned inter-branch transfer execute/cancel."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    Customer,
    Movement,
    MovementLine,
    PlannedTransfer,
    Supplier,
)
from . import counterparties
from .movement import apply_movement, build_movement


def _transfer_customer() -> Customer:
    return counterparties.customer("transfer")


def _transfer_supplier() -> Supplier:
    return counterparties.supplier("transfer")


def execute_planned_transfer(
    transfer: PlannedTransfer,
    *,
    executed_by,
    as_of: date | None = None,
) -> tuple[Movement, Movement]:
    """Run the výdej leg at source + the příjem leg at target atomically.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    counterparty pair is `is_internal=False` so the existing dodák
    auto-issue + e-mail hook fires on the výdej leg — the dodák is the
    physical paper for the driver. Both Movements get a back-FK to
    `transfer` so the audit trail can reconstruct the pairing.

    Refuses if `transfer.state != PLANNED`.
    """
    if transfer.state != PlannedTransfer.State.PLANNED:
        raise ValidationError(
            {"state": "Provést lze pouze plánovaný převod."}
        )

    issue_date = as_of or transfer.scheduled_for or date.today()

    with transaction.atomic():
        # Source-leg výdej.
        vydej = build_movement(
            branch=transfer.source_branch,
            kind=Movement.Kind.VYDEJ,
            counterparty=_transfer_customer(),
            date_issued=issue_date,
            note=(
                f"Převod {transfer.product.name_cs} "
                f"{transfer.quantity_kg} kg → "
                f"{transfer.target_branch.code} "
                f"(plán #{transfer.pk})."
            ),
            transfer=transfer,
        )
        vydej_line = MovementLine(
            product=transfer.product,
            quantity_kg=transfer.quantity_kg,
        )
        apply_movement(movement=vydej, lines=[vydej_line], user=executed_by)

        # Target-leg příjem.
        prijem = build_movement(
            branch=transfer.target_branch,
            kind=Movement.Kind.PRIJEM,
            counterparty=_transfer_supplier(),
            date_issued=issue_date,
            note=(
                f"Převod {transfer.product.name_cs} "
                f"{transfer.quantity_kg} kg ← "
                f"{transfer.source_branch.code} "
                f"(plán #{transfer.pk})."
            ),
            transfer=transfer,
        )
        prijem_line = MovementLine(
            product=transfer.product,
            quantity_kg=transfer.quantity_kg,
        )
        apply_movement(movement=prijem, lines=[prijem_line], user=executed_by)

        transfer.state = PlannedTransfer.State.DONE
        transfer.save(update_fields=["state"])
        return vydej, prijem


def cancel_planned_transfer(
    transfer: PlannedTransfer,
    *,
    cancelled_by,
) -> None:
    """Mark a PLANNED transfer as CANCELLED. No stock touched.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    all authenticated users may cancel (Matej 2026-06-14 confirmation —
    symmetric with create). No tier gate beyond LoginRequiredMiddleware.
    The `cancelled_by` parameter is accepted for symmetry / future
    audit; not persisted in MVP.
    """
    if transfer.state != PlannedTransfer.State.PLANNED:
        raise ValidationError(
            {"state": "Zrušit lze pouze plánovaný převod."}
        )
    transfer.state = PlannedTransfer.State.CANCELLED
    transfer.save(update_fields=["state"])


# ---------------------------------------------------------------------------
# Planned príjem (objednávka) confirm + query helpers (per 0059)
#
# Per 0059 a planned inbound is a Movement with status=PLANNED (created via
# the normal príjem form / apply_movement). The standalone PlannedOrder
# create/receive/cancel services of 0057 are retired; PlannedOrder is kept
# read-only. `_order_counterparty` + the constants below survive as the
# confirm-time fallback supplier.
# ---------------------------------------------------------------------------


