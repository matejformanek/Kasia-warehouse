"""Unified outbox log for every business e-mail the app sends (per 0075).

Absorbs the dodák-scoped ``DodaciListEmailLog`` (0007 / 0019): one row per send
attempt across all send paths — dodák (vystavení / oprava / ruční resend), the
event-driven low-stock alert (0074), and the SMTP test. Every row stores the
rendered subject + body so a non-dodák row can be re-sent faithfully; dodák rows
re-render from the live ``DodaciList`` instead (their subject/body may be empty
on migrated historical rows). Feeds the vlastník-gated „E-maily" outbox page and
the dodák detail's "Verze a odeslání" table (via ``related_name="email_logs"``).
"""

from django.conf import settings
from django.db import models

from .dodaci import DodaciList


class EmailLog(models.Model):
    """One send attempt for one app e-mail. Never edited or deleted — the log is
    append-only and kept indefinitely (right-sized for ~6 users, per 0075)."""

    class Category(models.TextChoices):
        DODACI_VYSTAVENI = "dodaci_vystaveni", "dodací list — vystavení"
        DODACI_OPRAVA = "dodaci_oprava", "dodací list — oprava"
        DODACI_RESEND = "dodaci_resend", "dodací list — opětovné odeslání"
        LOW_STOCK_ALERT = "low_stock_alert", "upozornění — dochází zboží"
        SMTP_TEST = "smtp_test", "test SMTP"

    class Status(models.TextChoices):
        SENT = "sent", "odesláno"
        FAILED = "failed", "selhalo"

    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    category = models.CharField(
        "kategorie",
        max_length=32,
        choices=Category.choices,
    )
    trigger_reason = models.TextField("důvod odeslání")
    recipients = models.CharField("příjemci", max_length=512)
    from_email = models.CharField("odesílatel", max_length=255, blank=True, default="")
    subject = models.CharField("předmět", max_length=255)
    body = models.TextField("tělo", blank=True, default="")
    status = models.CharField(
        "stav",
        max_length=16,
        choices=Status.choices,
    )
    error_message = models.TextField("chybová zpráva", blank=True, default="")
    dodaci_list = models.ForeignKey(
        DodaciList,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
        verbose_name="dodací list",
    )
    dodaci_version = models.PositiveIntegerField(
        "verze dodacího listu", null=True, blank=True
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_email_logs",
        verbose_name="odeslal",
    )

    class Meta:
        verbose_name = "záznam e-mailu"
        verbose_name_plural = "záznamy e-mailů"
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.get_category_display()} · {self.status} · {self.recipients}"
