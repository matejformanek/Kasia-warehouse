"""Dodaci list: number sequence, dodaci list, email log."""

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint

from .catalogue import Branch, Customer
from .movement import Movement


class DodaciListNumberSequence(models.Model):
    """Per-(branch, year) monotonic counter for dodák čísla per 0008. One row
    per (branch, year); allocated under SELECT … FOR UPDATE in services."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="number_sequences",
        verbose_name="pobočka",
    )
    year = models.PositiveSmallIntegerField("rok")
    last_counter = models.PositiveIntegerField("poslední pořadí", default=0)

    class Meta:
        verbose_name = "číselná řada dodacích listů"
        verbose_name_plural = "číselné řady dodacích listů"
        ordering = ("branch__code", "year")
        constraints = [
            UniqueConstraint(
                fields=["branch", "year"],
                name="unique_branch_year_sequence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.branch.code} {self.year}: {self.last_counter}"


class DodaciList(models.Model):
    """One issued dodací list per výdej Movement. Číslo is the per-(branch,
    year) sequence rendered as TYN-2026-0042 per 0008; current_version is
    the monotonic internal counter per 0007 (initial issue = 1, each
    correction increments by one); odberatel is a live FK per 0036."""

    movement = models.OneToOneField(
        Movement,
        on_delete=models.PROTECT,
        related_name="dodaci_list",
        verbose_name="pohyb",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="dodaci_lists",
        verbose_name="pobočka",
    )
    odberatel = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="dodaci_lists",
        verbose_name="odběratel",
    )
    date_issued = models.DateField("datum vystavení")
    year_issued = models.PositiveSmallIntegerField("rok vystavení")
    counter = models.PositiveIntegerField("pořadí")
    cislo = models.CharField("číslo", max_length=24, unique=True)
    current_version = models.PositiveIntegerField("aktuální verze", default=1)
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_dodaci_lists",
        verbose_name="vytvořil",
    )

    class Meta:
        verbose_name = "dodací list"
        verbose_name_plural = "dodací listy"
        ordering = ("-date_issued", "-id")
        constraints = [
            UniqueConstraint(
                fields=["branch", "year_issued", "counter"],
                name="unique_dodaci_list_branch_year_counter",
            ),
            CheckConstraint(
                condition=Q(counter__gte=1),
                name="dodaci_list_counter_positive",
            ),
            CheckConstraint(
                condition=Q(current_version__gte=1),
                name="dodaci_list_version_positive",
            ),
        ]

    @property
    def is_edited(self) -> bool:
        """True iff the dodák has been re-issued at least once (per 0007)."""
        return self.current_version > 1

    @property
    def total_quantity_kg(self):
        """Sum of all line quantities — feeds screen 08's "hrubý objem" column."""
        return sum(
            (line.quantity_kg for line in self.movement.lines.all()),
            start=0,
        )

    def __str__(self) -> str:
        return self.cislo


class DodaciListEmailLog(models.Model):
    """One row per send attempt for one dodák version. Per 0007 + 0019:
    every send (successful or failed) writes a row. Screen 09's "verze a
    odeslání" audit table reads these rows ordered by sent_at."""

    class Status(models.TextChoices):
        SENT = "sent", "odesláno"
        FAILED = "failed", "selhalo"

    dodaci_list = models.ForeignKey(
        DodaciList,
        on_delete=models.CASCADE,
        related_name="email_logs",
        verbose_name="dodací list",
    )
    version = models.PositiveIntegerField("verze")
    sent_at = models.DateTimeField("odesláno v", auto_now_add=True)
    recipients = models.CharField("příjemci", max_length=512)
    trigger_reason = models.TextField("důvod odeslání")
    status = models.CharField(
        "stav",
        max_length=16,
        choices=Status.choices,
    )
    error_message = models.TextField("chybová zpráva", blank=True, default="")

    class Meta:
        verbose_name = "záznam odeslání dodacího listu"
        verbose_name_plural = "záznamy odeslání dodacích listů"
        ordering = ("dodaci_list_id", "sent_at", "id")
        constraints = [
            CheckConstraint(
                condition=Q(version__gte=1),
                name="email_log_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.dodaci_list.cislo} v{self.version} · {self.status}"


# ---------------------------------------------------------------------------
# Settings singleton (per 0037)
# ---------------------------------------------------------------------------


