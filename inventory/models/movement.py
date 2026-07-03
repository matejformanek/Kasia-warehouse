"""Movement ledger: Movement, MovementLine, MovementAudit."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q

from .catalogue import Branch, Customer, Product, Supplier


class Movement(models.Model):
    """A header row for one stock movement at one branch.

    Sign convention: lines store `quantity_kg` as positive; the parent's
    `kind` decides direction (příjem = +, výdej = −). See MovementLine.
    """

    class Kind(models.TextChoices):
        PRIJEM = "prijem", "příjem"
        VYDEJ = "vydej", "výdej"

    class Status(models.TextChoices):
        DONE = "done", "hotovo"
        PLANNED = "planned", "plánováno"

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="pobočka",
    )
    kind = models.CharField("druh pohybu", max_length=16, choices=Kind.choices)
    status = models.CharField(
        "stav pohybu",
        max_length=16,
        choices=Status.choices,
        default=Status.DONE,
        help_text=(
            "DONE = běžný pohyb (mění sklad). PLANNED = plánovaný příjem"
            " (objednávka) — sklad se nemění, dokud se příjezd nepotvrdí."
            " Per rozhodnutí 0059."
        ),
    )
    date_issued = models.DateField("datum vystavení")
    expected_on = models.DateField(
        "očekávaný příjezd",
        null=True,
        blank=True,
        help_text=(
            "Vyplněno jen u PLANNED příjmu (promise arrival date). NULL u"
            " běžných (DONE) pohybů. Per rozhodnutí 0059."
        ),
    )
    odberatel = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vydej_movements",
        verbose_name="odběratel",
    )
    dodavatel = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prijem_movements",
        verbose_name="dodavatel",
    )
    note = models.TextField("poznámka", blank=True)
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_movements",
        verbose_name="vytvořil",
    )
    transfer = models.ForeignKey(
        "PlannedTransfer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="plánovaný převod",
        help_text=(
            "Set by `execute_planned_transfer` on both paired Movements"
            " (the výdej at source + the příjem at target) so the audit"
            " trail can link executed Movements back to their originating"
            " PlannedTransfer. NULL on every other Movement."
        ),
    )

    class Meta:
        verbose_name = "pohyb"
        verbose_name_plural = "pohyby"
        ordering = ("-date_issued", "-id")
        constraints = [
            # Per 0059: a DONE příjem still requires a supplier (no
            # regression); a výdej requires a customer; a PLANNED příjem may
            # omit the supplier (it is filled at confirm time).
            CheckConstraint(
                condition=(
                    Q(kind="vydej")
                    & Q(odberatel__isnull=False)
                    & Q(dodavatel__isnull=True)
                )
                | (
                    Q(kind="prijem")
                    & Q(status="done")
                    & Q(odberatel__isnull=True)
                    & Q(dodavatel__isnull=False)
                )
                | (
                    Q(kind="prijem")
                    & Q(status="planned")
                    & Q(odberatel__isnull=True)
                ),
                name="movement_counterparty_matches_kind",
            ),
            # PLANNED status only applies to příjem (per 0059).
            CheckConstraint(
                condition=Q(status="done") | Q(kind="prijem"),
                name="movement_planned_implies_prijem",
            ),
        ]

    def clean(self) -> None:
        if self.kind == self.Kind.VYDEJ:
            if self.odberatel_id is None:
                raise ValidationError(
                    {"odberatel": "Výdej musí mít odběratele."}
                )
            if self.dodavatel_id is not None:
                raise ValidationError(
                    {"dodavatel": "Výdej nemůže mít dodavatele."}
                )
        elif self.kind == self.Kind.PRIJEM:
            # A supplier is required only once the příjem is DONE; a PLANNED
            # příjem (objednávka) may still lack one until arrival is
            # confirmed (per 0059).
            if self.dodavatel_id is None and self.status == self.Status.DONE:
                raise ValidationError(
                    {"dodavatel": "Příjem musí mít dodavatele."}
                )
            if self.odberatel_id is not None:
                raise ValidationError(
                    {"odberatel": "Příjem nemůže mít odběratele."}
                )

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.date_issued.isoformat()} @ {self.branch.code}"


class MovementLine(models.Model):
    """One product line of a Movement. `quantity_kg` is positive; signed
    quantity is derived from the parent's kind."""

    movement = models.ForeignKey(
        Movement,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="pohyb",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movement_lines",
        verbose_name="produkt",
    )
    quantity_kg = models.DecimalField(
        "množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    sarze = models.CharField("šarže", max_length=64, blank=True)
    expiry = models.DateField("expirace", null=True, blank=True)
    note = models.CharField("poznámka", max_length=256, blank=True)

    class Meta:
        verbose_name = "položka pohybu"
        verbose_name_plural = "položky pohybu"
        ordering = ("movement_id", "id")
        constraints = [
            CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name="movement_line_quantity_positive",
            ),
        ]

    @property
    def signed_quantity(self):
        """Positive for příjem, negative for výdej. Requires `movement` loaded."""
        if self.movement.kind == Movement.Kind.PRIJEM:
            return self.quantity_kg
        return -self.quantity_kg

    def __str__(self) -> str:
        return f"{self.product} {self.quantity_kg} kg"


class MovementAudit(models.Model):
    """Append-only audit row per changed field (or per line lifecycle event)
    of a Movement edit. See decisions 0021 and 0035."""

    class TargetKind(models.TextChoices):
        MOVEMENT = "movement", "pohyb"
        LINE = "line", "položka"

    class Event(models.TextChoices):
        FIELD_CHANGED = "field_changed", "změna pole"
        LINE_ADDED = "line_added", "přidaná položka"
        LINE_REMOVED = "line_removed", "odebraná položka"

    movement = models.ForeignKey(
        Movement,
        on_delete=models.CASCADE,
        related_name="audit_entries",
        verbose_name="pohyb",
    )
    edited_at = models.DateTimeField("upraveno", auto_now_add=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movement_edits",
        verbose_name="upravil",
    )
    reason = models.TextField("důvod úpravy")
    target_kind = models.CharField(
        "cíl změny",
        max_length=16,
        choices=TargetKind.choices,
    )
    line_id = models.BigIntegerField("ID položky", null=True, blank=True)
    event = models.CharField("událost", max_length=24, choices=Event.choices)
    field = models.CharField("pole", max_length=64, blank=True, default="")
    old_value = models.TextField("původní hodnota", blank=True, default="")
    new_value = models.TextField("nová hodnota", blank=True, default="")

    class Meta:
        verbose_name = "záznam auditu"
        verbose_name_plural = "záznamy auditu"
        ordering = ("movement_id", "edited_at", "id")
        constraints = [
            CheckConstraint(
                condition=~Q(reason=""),
                name="movement_audit_reason_required",
            ),
        ]

    def __str__(self) -> str:
        suffix = f" ({self.field})" if self.field else ""
        return f"{self.movement_id} {self.event}{suffix} @ {self.edited_at.isoformat()}"


# ---------------------------------------------------------------------------
# Dodací list + send trail + numbering (per 0007 / 0008 / 0031 / 0036)
# ---------------------------------------------------------------------------


