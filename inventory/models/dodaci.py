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
    correction increments by one); odberatel is a live FK per 0036.

    send_state (per 0096) gates the *first* e-mail: a dodák is created at výdej
    in WAITING and nothing is sent until the operator clicks "Odeslat"; once
    SENT, later movement edits revert to 0007's auto-reissue + [OPRAVA]."""

    class SendState(models.TextChoices):
        WAITING = "waiting", "čeká na odeslání"
        SENT = "sent", "odesláno"

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
    send_state = models.CharField(
        "stav odeslání",
        max_length=16,
        choices=SendState.choices,
        default=SendState.WAITING,
    )
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
        """True iff the dodák has been re-issued at least once (per 0007). Note
        (per 0096): a WAITING draft stays v1 through edits, so this now reads as
        "re-issued after having been sent", not "edited at all"."""
        return self.current_version > 1

    @property
    def is_waiting(self) -> bool:
        """True iff the first e-mail hasn't been sent yet (per 0096)."""
        return self.send_state == self.SendState.WAITING

    @property
    def is_sent(self) -> bool:
        """True iff the dodák has been e-mailed at least once (per 0096)."""
        return self.send_state == self.SendState.SENT

    @property
    def total_quantity_kg(self):
        """Sum of the kg line quantities — feeds screen 08's "hrubý objem"
        column. Per 0095, finished-product („ks") lines are unlimited and their
        piece count is not kg, so they're excluded from this mass total."""
        return sum(
            (
                line.quantity_kg
                for line in self.movement.lines.all()
                if not line.product.is_unlimited
            ),
            start=0,
        )

    def __str__(self) -> str:
        return self.cislo
