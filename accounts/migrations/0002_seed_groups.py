"""Seed the two role groups used across the app.

Permission assignments per group are deferred to the view-layer pass; this
migration only ensures the group rows exist so future code can attach
membership and per-screen permissions to them.
"""

from django.db import migrations


GROUPS = ["vlastnik", "obsluha"]


def seed_forwards(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


def seed_reverse(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GROUPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(seed_forwards, seed_reverse),
    ]
