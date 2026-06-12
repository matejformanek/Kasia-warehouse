"""Seed the internal "Inventura / ruční úprava" Customer + Supplier pair
per decision 0041.

These are the counterparties on the synthetic Movement that records a
manual Stock adjustment from /katalog/<id>/upravit-stav/:
- positive delta (stock UP) → prijem with Supplier "Inventura / ruční úprava"
- negative delta (stock DOWN) → vydej with Customer "Inventura / ruční úprava"

Kept distinct from the Míchárna pair (0007) so a future Historie filter
can split "manual stock adjustments" from "míchání-job consume/produce".
"""

from django.db import migrations


_NAME = "Inventura / ruční úprava"
_ADDRESS = "interní úprava stavu"


def seed_forwards(apps, schema_editor):
    Customer = apps.get_model("inventory", "Customer")
    Supplier = apps.get_model("inventory", "Supplier")

    Customer.objects.get_or_create(
        name=_NAME,
        is_internal=True,
        defaults={"address": _ADDRESS},
    )
    Supplier.objects.get_or_create(
        name=_NAME,
        is_internal=True,
        defaults={"address": _ADDRESS},
    )


def seed_reverse(apps, schema_editor):
    Customer = apps.get_model("inventory", "Customer")
    Supplier = apps.get_model("inventory", "Supplier")
    Customer.objects.filter(name=_NAME, is_internal=True).delete()
    Supplier.objects.filter(name=_NAME, is_internal=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_seed_micharna"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
