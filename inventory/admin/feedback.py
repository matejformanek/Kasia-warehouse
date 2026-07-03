"""Feedback admin."""

from django.contrib import admin

from ..models import (
    Feedback,
)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    """Read-mostly per 0046 — main UI is /podpora/. Admin is here only
    for emergency moderation (e.g. removing duplicate spam)."""

    list_display = ("id", "created_at", "created_by", "page_url", "is_open")
    list_filter = ("created_at",)
    search_fields = ("description", "page_url", "created_by__email")
    readonly_fields = (
        "created_at",
        "created_by",
        "resolved_at",
        "resolved_by",
    )

    @admin.display(boolean=True, description="otevřené")
    def is_open(self, obj: Feedback) -> bool:
        return obj.is_open
