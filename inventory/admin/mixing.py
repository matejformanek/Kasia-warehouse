"""Mixing admin."""

from django.contrib import admin

from ..models import (
    MixingJob,
    MixingJobLine,
)


@admin.register(MixingJob)
class MixingJobAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "started_at",
        "branch",
        "mixture",
        "target_qty",
        "actual_produced_qty",
        "state",
        "created_by",
    )
    list_filter = ("state", "branch", "mixture")
    search_fields = ("mixture__name_cs", "branch__code", "note")
    readonly_fields = (
        "branch",
        "mixture",
        "target_qty",
        "actual_produced_qty",
        "state",
        "started_at",
        "finished_at",
        "created_by",
        "cancel_reason",
        "note",
        "consume_movement",
        "produce_movement",
    )

    def has_add_permission(self, request) -> bool:
        # Created only via start_mixing_job / record_completed_mixing_job.
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(MixingJobLine)
class MixingJobLineAdmin(admin.ModelAdmin):
    list_display = (
        "mixing_job",
        "component_product",
        "ratio_at_start",
        "derived_qty",
        "actual_qty",
        "sarze",
    )
    list_filter = ("mixing_job__state",)
    search_fields = (
        "component_product__name_cs",
        "mixing_job__mixture__name_cs",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


# ---------------------------------------------------------------------------
# PlannedTransfer + StockThresholdOverride (per 0043 + 0044)
# ---------------------------------------------------------------------------


