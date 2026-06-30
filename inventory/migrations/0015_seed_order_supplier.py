"""Seed the internal "Objednávka" Supplier per decision 0057.

This is the counterparty on the příjem leg of a `PlannedOrder`
confirmation when the order has no real supplier set. It is
`is_internal=True` — like the Inventura pair (0008), it is hidden in
the příjem supplier picker and never triggers a dodák/e-mail (PRIJEM
never does anyway).

Supplier-only: a PlannedOrder is always inbound, so there is no Customer
counterpart (unlike the Míchárna / Inventura / Převod pairs).
"""

from django.db import migrations


_NAME = "Objednávka"
_ADDRESS = "interní přijatá objednávka"


def seed_forwards(apps, schema_editor):
    Supplier = apps.get_model("inventory", "Supplier")
    Supplier.objects.get_or_create(
        name=_NAME,
        is_internal=True,
        defaults={"address": _ADDRESS},
    )


def seed_reverse(apps, schema_editor):
    Supplier = apps.get_model("inventory", "Supplier")
    Supplier.objects.filter(name=_NAME, is_internal=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0014_plannedorder"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
