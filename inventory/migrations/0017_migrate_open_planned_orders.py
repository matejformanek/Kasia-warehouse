"""Migrate open (PLANNED) PlannedOrder rows to PLANNED príjem Movements
(per 0059).

Each still-open objednávka becomes one PLANNED príjem Movement (status
"planned", kind "prijem") carrying the promised arrival date on expected_on,
plus a single MovementLine for its product/quantity. The source PlannedOrder is
then flipped to "cancelled" so it never double-counts. RECEIVED / CANCELLED
rows are left untouched (RECEIVED already point at a real Movement).

Uses historical model snapshots only — no service imports. Reverse is a no-op
(the created Movements are harmless PLANNED rows; we don't try to reconstruct
the original PlannedOrder state).
"""

from django.db import migrations


def forwards(apps, schema_editor):
    PlannedOrder = apps.get_model("inventory", "PlannedOrder")
    Movement = apps.get_model("inventory", "Movement")
    MovementLine = apps.get_model("inventory", "MovementLine")

    open_orders = PlannedOrder.objects.filter(state="planned").select_related(
        "product", "branch", "supplier", "created_by"
    )
    for order in open_orders:
        movement = Movement.objects.create(
            branch=order.branch,
            kind="prijem",
            status="planned",
            date_issued=order.created_at.date(),
            expected_on=order.expected_on,
            dodavatel=order.supplier,
            note="",
            created_by=order.created_by,
        )
        MovementLine.objects.create(
            movement=movement,
            product=order.product,
            quantity_kg=order.quantity_kg,
        )
        order.state = "cancelled"
        order.save(update_fields=["state"])


def reverse(apps, schema_editor):
    # No-op: we do not reconstruct the original PlannedOrder state.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0016_movement_status_expected_on"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
