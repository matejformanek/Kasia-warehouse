"""Per decision 0053: Stock row existence IS the "branch carries product"
flag. Seed a 0-kg Stock row for every (active product × active branch)
pair so prod's current "every product is visible on every branch"
behavior is preserved as explicit, editable carry-state.

Forward is idempotent — re-running won't duplicate rows.
Reverse is a no-op: rolling back must not delete user-curated Stock
state. The worst case is a few leftover 0-kg rows that the Pobočky
controls can clean up.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import migrations


def seed_forwards(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    Branch = apps.get_model("inventory", "Branch")
    Stock = apps.get_model("inventory", "Stock")

    branches = list(Branch.objects.filter(is_active=True))
    if not branches:
        return

    for product in Product.objects.filter(is_active=True):
        existing = set(
            Stock.objects.filter(product=product).values_list(
                "branch_id", flat=True
            )
        )
        for branch in branches:
            if branch.pk in existing:
                continue
            Stock.objects.create(
                product=product, branch=branch, quantity=Decimal("0.000")
            )


def seed_reverse(apps, schema_editor):
    # No-op on rollback — do not destroy user-curated carry state.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0012_settings_recipients_table"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
