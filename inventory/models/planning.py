"""Planned work: PlannedTransfer + PlannedOrder."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q

from .catalogue import Branch, Product, Supplier
from .movement import Movement


class PlannedTransfer(models.Model):
    """One scheduled transfer of a product from one branch to another.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    PLANNED rows count as reserved at `source_branch`. Execution writes
    a pair of Movements via `execute_planned_transfer`: a výdej at the
    source (to the seeded "Převod mezi pobočkami" Customer) and a
    příjem at the target (from the seeded "Převod mezi pobočkami"
    Supplier). The counterparty pair is `is_internal=False` so the
    existing dodák auto-issue + e-mail hooks fire on the výdej leg —
    the dodák is the physical paper for the driver.
    """

    class State(models.TextChoices):
        PLANNED = "planned", "naplánováno"
        DONE = "done", "provedeno"
        CANCELLED = "cancelled", "zrušeno"

    source_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="outgoing_planned_transfers",
        verbose_name="zdrojová pobočka",
    )
    target_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="incoming_planned_transfers",
        verbose_name="cílová pobočka",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="planned_transfers",
        verbose_name="produkt",
    )
    quantity_kg = models.DecimalField(
        "množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    scheduled_for = models.DateField("plánováno na")
    state = models.CharField(
        "stav",
        max_length=16,
        choices=State.choices,
        default=State.PLANNED,
    )
    notes = models.TextField("poznámka", blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_planned_transfers",
        verbose_name="vytvořil",
    )
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)

    class Meta:
        verbose_name = "plánovaný převod"
        verbose_name_plural = "plánované převody"
        ordering = ("-scheduled_for", "-id")
        constraints = [
            CheckConstraint(
                condition=~Q(source_branch=models.F("target_branch")),
                name="planned_transfer_different_branches",
            ),
            CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name="planned_transfer_qty_positive",
            ),
        ]

    def clean(self) -> None:
        if (
            self.source_branch_id
            and self.target_branch_id
            and self.source_branch_id == self.target_branch_id
        ):
            raise ValidationError(
                {"target_branch": "Cílová pobočka se musí lišit od zdrojové."}
            )

    def __str__(self) -> str:
        return (
            f"{self.product} {self.quantity_kg} kg: "
            f"{self.source_branch.code} → {self.target_branch.code} "
            f"({self.scheduled_for.isoformat()})"
        )


# ---------------------------------------------------------------------------
# Planned inbound order (per decision 0057)
# ---------------------------------------------------------------------------


class PlannedOrder(models.Model):
    """One ordered inbound delivery of a product to a branch ("objednávka").

    RETIRED, read-only historical (see
    [0059](../context/decisions/0059-merge-objednavka-into-prijem.md)): planned
    inbound is now a `Movement` with `status=planned`. This model is no longer
    written by the operator surface; open rows were migrated to PLANNED
    Movements (migration 0017). Kept for the 0057 audit trail; the admin has no
    add permission.

    Per [0057](../context/decisions/0057-planned-orders-objednavky.md):
    PLANNED orders show as "objednáno" badges on the low-stock panel but
    do NOT change effective stock (informational, like reservations per
    0044). Confirming arrival writes one příjem via `apply_movement` and
    flips state to RECEIVED; `received_qty` records what actually arrived
    (may differ from the ordered `quantity_kg`). If `supplier` is set the
    příjem is a real receipt from that supplier; otherwise it uses the
    seeded internal "Objednávka" counterparty.
    """

    class State(models.TextChoices):
        PLANNED = "planned", "objednáno"
        RECEIVED = "received", "přijato"
        CANCELLED = "cancelled", "zrušeno"

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="planned_orders",
        verbose_name="produkt",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="planned_orders",
        verbose_name="pobočka",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planned_orders",
        verbose_name="dodavatel",
    )
    quantity_kg = models.DecimalField(
        "objednané množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    received_qty = models.DecimalField(
        "přijaté množství (kg)",
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
    )
    expected_on = models.DateField("očekávaný příjezd")
    state = models.CharField(
        "stav",
        max_length=16,
        choices=State.choices,
        default=State.PLANNED,
    )
    notes = models.TextField("poznámka", blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_planned_orders",
        verbose_name="vytvořil",
    )
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    received_movement = models.ForeignKey(
        Movement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="from_planned_order",
        verbose_name="příjem (přijetí)",
        help_text=(
            "Set by `receive_planned_order` on confirm — the one PRIJEM"
            " Movement that added the received kg to stock. NULL while"
            " the order is still PLANNED or was CANCELLED."
        ),
    )

    class Meta:
        verbose_name = "objednávka"
        verbose_name_plural = "objednávky"
        ordering = ("-expected_on", "-id")
        constraints = [
            CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name="planned_order_qty_positive",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.product} {self.quantity_kg} kg → "
            f"{self.branch.code} ({self.expected_on.isoformat()})"
        )


# ---------------------------------------------------------------------------
# In-app feedback log (per decision 0046)
# ---------------------------------------------------------------------------


