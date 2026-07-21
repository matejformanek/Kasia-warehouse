"""Seed the internal "Neuveden" Supplier per decision 0085.

This is the default counterparty on a DONE příjem when the operator picks no
supplier ("— Neuveden —" blank option). It is `is_internal=True` — like the
Objednávka (0015) / Inventura (0008) placeholders it is hidden in the příjem
supplier picker and never triggers a dodák/e-mail (PRIJEM never does anyway).

Supplier-only: a příjem is always inbound, so there is no Customer counterpart.
"""

from django.db import migrations


_NAME = "Neuveden"
_ADDRESS = "dodavatel neuveden"


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
        ("inventory", "0023_emaillog_password_reset_category"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
