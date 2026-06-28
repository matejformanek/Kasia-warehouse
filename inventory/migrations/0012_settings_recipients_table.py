# Generated 2026-06-28 — per decision
# context/decisions/0052-n-list-recipients-supersedes-0031.md.
#
# Single atomic migration: CreateModel SettingsRecipient → RunPython
# copies the old Settings.recipient_petr / recipient_karolina values
# into rows on the new table → RemoveField on both old columns.
#
# Idempotency: skips a row if the source email is blank or if any
# SettingsRecipient row already exists. Safe to apply, roll back, and
# re-apply (the create-step would refuse a duplicate if any row exists).

import django.db.models.functions.text
from django.db import migrations, models


def _copy_recipients_into_table(apps, schema_editor):
    Settings = apps.get_model("inventory", "Settings")
    SettingsRecipient = apps.get_model("inventory", "SettingsRecipient")
    if SettingsRecipient.objects.exists():
        return  # Already migrated.
    try:
        s = Settings.objects.get(singleton_key="singleton")
    except Settings.DoesNotExist:
        return
    rows = []
    if (s.recipient_petr or "").strip():
        rows.append(
            SettingsRecipient(
                email=s.recipient_petr.strip(),
                label="Petr",
                is_active=True,
                is_low_stock_recipient=True,  # preserves 0045's "Petr only" intent
                sort_order=0,
            )
        )
    if (s.recipient_karolina or "").strip():
        rows.append(
            SettingsRecipient(
                email=s.recipient_karolina.strip(),
                label="Karolína",
                is_active=True,
                is_low_stock_recipient=False,
                sort_order=1,
            )
        )
    if rows:
        SettingsRecipient.objects.bulk_create(rows)


def _noop_reverse(apps, schema_editor):
    # Reversal is intentionally non-destructive: we don't re-populate the
    # dropped columns. Use a backup if rollback is required.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0011_feedback"),
    ]

    operations = [
        migrations.CreateModel(
            name="SettingsRecipient",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254, verbose_name="e-mail")),
                (
                    "label",
                    models.CharField(blank=True, max_length=64, verbose_name="popisek"),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="aktivní")),
                (
                    "is_low_stock_recipient",
                    models.BooleanField(
                        default=False, verbose_name="dostává souhrn dochází zboží"
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(default=0, verbose_name="pořadí"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "příjemce nastavení",
                "verbose_name_plural": "příjemci nastavení",
                "ordering": ["-is_active", "sort_order", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("email"),
                        name="recipient_email_unique_ci",
                    )
                ],
            },
        ),
        migrations.RunPython(
            _copy_recipients_into_table, _noop_reverse, elidable=False
        ),
        migrations.RemoveField(
            model_name="settings",
            name="recipient_karolina",
        ),
        migrations.RemoveField(
            model_name="settings",
            name="recipient_petr",
        ),
    ]
