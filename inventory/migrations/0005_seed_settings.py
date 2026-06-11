"""Seed the Settings singleton row.

Per decision 0037, the row is enforced single via singleton_key + unique
constraint. Defaults come from screens/14-nastaveni.md (Matej-ratified
on 2026-06-03). Recipient e-mails (Petr, Karolína) are left empty
intentionally — an operator fills them on first run; apply_movement
for vydej refuses to send until they are non-empty per 0031.
"""

from django.db import migrations


def seed_forwards(apps, schema_editor):
    Settings = apps.get_model("inventory", "Settings")
    Settings.objects.get_or_create(singleton_key="singleton")


def seed_reverse(apps, schema_editor):
    Settings = apps.get_model("inventory", "Settings")
    Settings.objects.filter(singleton_key="singleton").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_dodaci_list_and_settings"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
