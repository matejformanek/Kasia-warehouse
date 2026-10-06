"""Give every non-superuser, non-obsluha user the `vlastnik` group (per 0104).

Roles now fail closed: ``User.is_vlastnik`` requires the `vlastnik` group
instead of "anyone not in obsluha". Until now no account ever got that group
(``_sync_role`` only managed `obsluha`), so every owner-level account was
groupless. This migration preserves their effective rights exactly —
including inactive accounts, so a later reactivation doesn't produce a
role-less user. It promotes nobody: each touched user was already a vlastník
under the old fail-open rule.

Reverse is a no-op: the extra group is harmless to the old code.
"""

from django.db import migrations


def assign_vlastnik(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("accounts", "User")
    vlastnik, _ = Group.objects.get_or_create(name="vlastnik")
    for user in User.objects.filter(is_superuser=False).exclude(
        groups__name="obsluha"
    ):
        user.groups.add(vlastnik)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_seed_groups"),
    ]

    operations = [
        migrations.RunPython(assign_vlastnik, migrations.RunPython.noop),
    ]
