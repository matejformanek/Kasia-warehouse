"""Seed the "Převod mezi pobočkami" Customer + Supplier pair per
decision 0044.

These are the counterparties on each leg of a `PlannedTransfer`
execution:
- the výdej at the source branch goes to the Customer
- the příjem at the target branch comes from the Supplier

Both are `is_internal=False` (Matej 2026-06-14): the existing
dodák auto-issue + e-mail hook (0007/0030/0031) must fire on the
výdej leg so the driver has the physical paper.

Distinct from the Míchárna pair (0007) and the Inventura pair
(0008) — three separate internal counterparty pairs, kept separate
so a future Historie filter can split each.
"""

from django.db import migrations


_NAME = "Převod mezi pobočkami"
_ADDRESS = "interní převod mezi pobočkami"


def seed_forwards(apps, schema_editor):
    Customer = apps.get_model("inventory", "Customer")
    Supplier = apps.get_model("inventory", "Supplier")

    Customer.objects.get_or_create(
        name=_NAME,
        is_internal=False,
        defaults={"address": _ADDRESS},
    )
    Supplier.objects.get_or_create(
        name=_NAME,
        is_internal=False,
        defaults={"address": _ADDRESS},
    )


def seed_reverse(apps, schema_editor):
    Customer = apps.get_model("inventory", "Customer")
    Supplier = apps.get_model("inventory", "Supplier")
    Customer.objects.filter(name=_NAME, is_internal=False).delete()
    Supplier.objects.filter(name=_NAME, is_internal=False).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0009_threshold_and_reservations"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
