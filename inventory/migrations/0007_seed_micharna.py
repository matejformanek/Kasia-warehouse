"""Seed the internal "Míchárna" Customer + Supplier per decision 0039.

These are the counterparties on mixing-job consume + produce Movements:
- Customer "Míchárna" (is_internal=True) — odběratel on the vydej
  Movement that records the consumption of source spices.
- Supplier "Míchárna" (is_internal=True) — dodavatel on the prijem
  Movement that records the produced mixture lands on stock.

apply_movement's dodák hook checks `odberatel.is_internal` and skips
the PDF + e-mail path for these rows.
"""

from django.db import migrations


def seed_forwards(apps, schema_editor):
    Customer = apps.get_model("inventory", "Customer")
    Supplier = apps.get_model("inventory", "Supplier")

    Customer.objects.get_or_create(
        name="Míchárna",
        is_internal=True,
        defaults={"address": "interní výroba směsí"},
    )
    Supplier.objects.get_or_create(
        name="Míchárna",
        is_internal=True,
        defaults={"address": "interní výroba směsí"},
    )


def seed_reverse(apps, schema_editor):
    Customer = apps.get_model("inventory", "Customer")
    Supplier = apps.get_model("inventory", "Supplier")
    Customer.objects.filter(name="Míchárna", is_internal=True).delete()
    Supplier.objects.filter(name="Míchárna", is_internal=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_mixing_job"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
