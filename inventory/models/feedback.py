"""Support feedback."""

from django.conf import settings
from django.db import models


class Feedback(models.Model):
    """One user-submitted report from the /podpora/ support page.

    Per [0046](../context/decisions/0046-support-page.md): free-form Czech
    bug / question / wish, optional page reference, visible to every
    logged-in user. Vlastník can toggle resolved state; on resolve they may
    add a ``resolution_note`` and the creator is notified by e-mail (per 0098).
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_feedback",
        verbose_name="autor",
    )
    created_at = models.DateTimeField("vytvořeno", auto_now_add=True)
    page_url = models.CharField("stránka", max_length=255, blank=True)
    description = models.TextField("popis")
    resolved_at = models.DateTimeField(
        "vyřešeno v", null=True, blank=True
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_feedback",
        verbose_name="vyřešil",
    )
    # Optional closing note the vlastník types when resolving (per 0098). Kept
    # on reopen. Included in the resolve notification e-mail to the creator.
    resolution_note = models.TextField("poznámka k vyřešení", blank=True)

    class Meta:
        verbose_name = "hlášení"
        verbose_name_plural = "hlášení"
        ordering = ("-created_at",)

    @property
    def is_open(self) -> bool:
        return self.resolved_at is None

    def __str__(self) -> str:
        marker = "otevřené" if self.is_open else "vyřešené"
        return f"Hlášení #{self.pk} ({marker})"
