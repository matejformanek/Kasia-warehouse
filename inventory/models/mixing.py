"""Mixing jobs: MixingJob + MixingJobLine."""

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint

from .catalogue import Branch, Product
from .movement import Movement


class MixingJob(models.Model):
    """One execution of a mixture recipe at a branch.

    Per 0039: consume at start (consume_movement points at the vydej
    Movement written when the operator clicks Zahájit); produce at
    finish (produce_movement points at the prijem Movement written
    when the operator clicks Dokončit). Cancel is an audited correction
    that zeros out every line of consume_movement via edit_movement.
    Yield loss surfaces as the delta between target_qty and
    actual_produced_qty; no separate column.
    """

    class State(models.TextChoices):
        PLANNED = "planned", "naplánováno"
        RUNNING = "running", "probíhá"
        DONE = "done", "dokončeno"
        CANCELLED = "cancelled", "zrušeno"

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="mixing_jobs",
        verbose_name="pobočka",
    )
    mixture = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="mixing_jobs",
        verbose_name="směs",
    )
    target_qty = models.DecimalField(
        "cílové množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    actual_produced_qty = models.DecimalField(
        "skutečně vyrobeno (kg)",
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
    )
    state = models.CharField(
        "stav",
        max_length=16,
        choices=State.choices,
        default=State.RUNNING,
    )
    planned_for = models.DateField(
        "plánováno na",
        null=True,
        blank=True,
        help_text=(
            "Pouze pro state=PLANNED — kdy operátor předpokládá fyzické míchání."
            " Po přechodu na RUNNING už nemá smysl, pole zůstane jako historický záznam."
        ),
    )
    started_at = models.DateTimeField("zahájeno", auto_now_add=True)
    finished_at = models.DateTimeField("ukončeno", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_mixing_jobs",
        verbose_name="vytvořil",
    )
    cancel_reason = models.TextField(
        "důvod zrušení",
        blank=True,
        default="",
    )
    note = models.TextField("poznámka", blank=True, default="")
    consume_movement = models.ForeignKey(
        Movement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mixing_job_as_consume",
        verbose_name="pohyb spotřeby",
    )
    produce_movement = models.ForeignKey(
        Movement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mixing_job_as_produce",
        verbose_name="pohyb produkce",
    )

    class Meta:
        verbose_name = "míchací dávka"
        verbose_name_plural = "míchací dávky"
        ordering = ("-started_at", "-id")
        constraints = [
            CheckConstraint(
                condition=Q(target_qty__gt=0),
                name="mixing_job_target_qty_positive",
            ),
            CheckConstraint(
                condition=Q(actual_produced_qty__isnull=True)
                | Q(actual_produced_qty__gte=0),
                name="mixing_job_actual_produced_qty_non_negative",
            ),
            CheckConstraint(
                condition=~Q(state="cancelled") | ~Q(cancel_reason=""),
                name="mixing_job_cancel_reason_required",
            ),
        ]

    @property
    def is_terminal(self) -> bool:
        return self.state in (self.State.DONE, self.State.CANCELLED)

    @property
    def yield_delta(self):
        """Signed (actual - target). None if not finished. Used by
        screen 15 to surface dust loss / over-yield as a delta on the
        produced movement per 0039."""
        if self.actual_produced_qty is None:
            return None
        return self.actual_produced_qty - self.target_qty

    def __str__(self) -> str:
        return f"Míchání {self.mixture} {self.target_qty} kg @ {self.branch.code}"


class MixingJobLine(models.Model):
    """One per-component snapshot of a MixingJob's recipe.

    Per 0005: recipe is snapshotted at job start — `ratio_at_start`
    is copied from the live RecipeComponent row, and future recipe
    edits do not touch in-flight jobs. `derived_qty` is
    `target_qty * ratio_at_start` computed at start. `actual_qty`
    defaults to `derived_qty` and is editable at finish to record
    weighing tolerance.
    """

    mixing_job = models.ForeignKey(
        MixingJob,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="míchací dávka",
    )
    component_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="mixing_job_lines",
        verbose_name="surovina",
    )
    ratio_at_start = models.DecimalField(
        "podíl při zahájení",
        max_digits=7,
        decimal_places=6,
    )
    derived_qty = models.DecimalField(
        "odvozené množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    actual_qty = models.DecimalField(
        "skutečné množství (kg)",
        max_digits=10,
        decimal_places=3,
    )
    sarze = models.CharField("šarže", max_length=64, blank=True)

    class Meta:
        verbose_name = "položka míchání"
        verbose_name_plural = "položky míchání"
        ordering = ("mixing_job_id", "id")
        constraints = [
            UniqueConstraint(
                fields=["mixing_job", "component_product"],
                name="unique_mixing_job_component",
            ),
            CheckConstraint(
                condition=Q(derived_qty__gt=0),
                name="mixing_job_line_derived_positive",
            ),
            CheckConstraint(
                condition=Q(actual_qty__gt=0),
                name="mixing_job_line_actual_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.component_product} {self.actual_qty} kg"


# ---------------------------------------------------------------------------
# Planned inter-branch transfer (per decision 0044)
# ---------------------------------------------------------------------------


