"""Seed the two real branches (TYN, SEZ) and the default Říčany customer.

Říčany is the internal default odběratel for every výdej per decision 0030;
it is modelled as a Customer row with is_default_recipient=True, not as a
Branch. The partial-unique constraint on Customer guarantees a single such
row.
"""

from django.db import migrations


BRANCHES = [
    {"code": "TYN", "name": "Týniště nad Orlicí"},
    {"code": "SEZ", "name": "Sezimovo Ústí"},
]


def seed_forwards(apps, schema_editor):
    Branch = apps.get_model("inventory", "Branch")
    Customer = apps.get_model("inventory", "Customer")

    for row in BRANCHES:
        Branch.objects.get_or_create(code=row["code"], defaults={"name": row["name"]})

    Customer.objects.get_or_create(
        is_default_recipient=True,
        defaults={
            "name": "Říčany",
            "address": "Říčany u Prahy",
        },
    )


def seed_reverse(apps, schema_editor):
    Branch = apps.get_model("inventory", "Branch")
    Customer = apps.get_model("inventory", "Customer")
    Branch.objects.filter(code__in=[b["code"] for b in BRANCHES]).delete()
    Customer.objects.filter(is_default_recipient=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
