"""Planning admin."""

from django.contrib import admin

from ..models import (
    PlannedOrder,
    PlannedTransfer,
)


@admin.register(PlannedTransfer)
class PlannedTransferAdmin(admin.ModelAdmin):
    """Read-mostly admin per 0044 — created + executed via the operator
    surface at /prevody/. Admin can view / cancel but not edit fields."""

    list_display = (
        "pk",
        "scheduled_for",
        "source_branch",
        "target_branch",
        "product",
        "quantity_kg",
        "state",
        "created_by",
    )
    list_filter = ("state", "source_branch", "target_branch")
    search_fields = ("product__name_cs", "notes")
    readonly_fields = (
        "source_branch",
        "target_branch",
        "product",
        "quantity_kg",
        "scheduled_for",
        "state",
        "notes",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(PlannedOrder)
class PlannedOrderAdmin(admin.ModelAdmin):
    """Read-only historical admin. Per 0059 the objednávka surface is retired;
    planned inbound is now a PLANNED Movement. Admin views historical rows
    only — no add, no edit, no delete."""

    list_display = (
        "pk",
        "expected_on",
        "product",
        "branch",
        "supplier",
        "quantity_kg",
        "received_qty",
        "state",
        "created_by",
    )
    list_filter = ("state", "branch")
    search_fields = ("product__name_cs", "notes")
    readonly_fields = (
        "state",
        "received_qty",
        "received_movement",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


