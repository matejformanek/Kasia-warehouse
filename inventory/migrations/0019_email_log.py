# Generated 2026-07-07 — per decision
# context/decisions/0075-email-outbox-log.md.
#
# Single atomic migration (safe on Django 5.2): CreateModel EmailLog →
# RunPython copies every DodaciListEmailLog row into EmailLog (category derived
# from the old trigger_reason; version → dodaci_version; subject/body left
# empty — migrated dodák rows re-render from the live DodaciList on resend) →
# DeleteModel DodaciListEmailLog.
#
# Idempotency: the copy step skips when any EmailLog row already exists (mirrors
# migration 0012). created_at is auto_now_add, so it's back-set with a follow-up
# .update() after each create. Reverse is a non-destructive no-op (one-way is
# fine for an append-only log).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _copy_dodaci_logs(apps, schema_editor):
    DodaciListEmailLog = apps.get_model("inventory", "DodaciListEmailLog")
    EmailLog = apps.get_model("inventory", "EmailLog")
    if EmailLog.objects.exists():
        return  # Already migrated.
    for old in DodaciListEmailLog.objects.all().order_by("id"):
        reason = old.trigger_reason or ""
        if reason.startswith("oprava"):
            category = "dodaci_oprava"
        elif reason == "ruční opětovné odeslání":
            category = "dodaci_resend"
        else:
            category = "dodaci_vystaveni"
        new = EmailLog.objects.create(
            category=category,
            trigger_reason=reason,
            recipients=old.recipients,
            from_email="",
            subject="",
            body="",
            status=old.status,
            error_message=old.error_message,
            dodaci_list_id=old.dodaci_list_id,
            dodaci_version=old.version,
        )
        # created_at is auto_now_add — back-set the original send time.
        EmailLog.objects.filter(pk=new.pk).update(created_at=old.sent_at)


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0018_reorder_threshold_not_null"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailLog",
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
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="vytvořeno"),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("dodaci_vystaveni", "dodací list — vystavení"),
                            ("dodaci_oprava", "dodací list — oprava"),
                            ("dodaci_resend", "dodací list — opětovné odeslání"),
                            ("low_stock_alert", "upozornění — dochází zboží"),
                            ("smtp_test", "test SMTP"),
                        ],
                        max_length=32,
                        verbose_name="kategorie",
                    ),
                ),
                ("trigger_reason", models.TextField(verbose_name="důvod odeslání")),
                (
                    "recipients",
                    models.CharField(max_length=512, verbose_name="příjemci"),
                ),
                (
                    "from_email",
                    models.CharField(
                        blank=True, default="", max_length=255, verbose_name="odesílatel"
                    ),
                ),
                ("subject", models.CharField(max_length=255, verbose_name="předmět")),
                ("body", models.TextField(blank=True, default="", verbose_name="tělo")),
                (
                    "status",
                    models.CharField(
                        choices=[("sent", "odesláno"), ("failed", "selhalo")],
                        max_length=16,
                        verbose_name="stav",
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True, default="", verbose_name="chybová zpráva"
                    ),
                ),
                (
                    "dodaci_version",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="verze dodacího listu"
                    ),
                ),
                (
                    "dodaci_list",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="email_logs",
                        to="inventory.dodacilist",
                        verbose_name="dodací list",
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_email_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="odeslal",
                    ),
                ),
            ],
            options={
                "verbose_name": "záznam e-mailu",
                "verbose_name_plural": "záznamy e-mailů",
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.RunPython(_copy_dodaci_logs, _noop_reverse, elidable=False),
        migrations.DeleteModel(name="DodaciListEmailLog"),
    ]
