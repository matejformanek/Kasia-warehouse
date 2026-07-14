"""Operator screen-visit log (per 0077).

One row per authenticated, full-page, successful GET under ``/sklad/`` —
who / which screen / when — written by ``inventory.middleware
.ScreenVisitMiddleware``. First-party and server-side: no client JS, no IP,
no User-Agent. Append-only and kept indefinitely (0075 retention precedent);
feeds the vlastník-gated „Aktivita" Správa page. Writes stay in
``MovementAudit``'s territory — this model records reads only.
"""

from django.conf import settings
from django.db import models


class ScreenVisit(models.Model):
    """One warehouse-screen pageview by one operator. Never edited or
    deleted — the log is append-only (per 0077)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="screen_visits",
        verbose_name="uživatel",
    )
    url_name = models.CharField("obrazovka", max_length=64)
    namespace = models.CharField(
        "jmenný prostor", max_length=32, blank=True, default=""
    )
    path = models.CharField("cesta", max_length=512)
    created_at = models.DateTimeField("navštíveno", auto_now_add=True)

    class Meta:
        verbose_name = "návštěva obrazovky"
        verbose_name_plural = "návštěvy obrazovek"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["url_name", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.url_name} · {self.created_at:%Y-%m-%d %H:%M}"
