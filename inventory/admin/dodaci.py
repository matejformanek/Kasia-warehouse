"""Dodaci list admin."""

from django.contrib import admin, messages

from ..models import (
    DodaciList,
    EmailLog,
)
from ..services import (
    render_dodaci_list_pdf,
    send_dodaci_list_email,
)


@admin.register(DodaciList)
class DodaciListAdmin(admin.ModelAdmin):
    list_display = (
        "cislo",
        "date_issued",
        "branch",
        "odberatel",
        "current_version",
        "is_edited_display",
        "created_by",
    )
    list_filter = ("branch", "year_issued")
    search_fields = ("cislo", "odberatel__name", "movement__id")
    readonly_fields = (
        "cislo",
        "branch",
        "year_issued",
        "counter",
        "current_version",
        "movement",
        "odberatel",
        "date_issued",
        "created_at",
        "created_by",
    )
    actions = ("resend_dodaci_list",)

    @admin.display(boolean=True, description="editováno")
    def is_edited_display(self, obj: DodaciList) -> bool:
        return obj.is_edited

    def has_add_permission(self, request) -> bool:
        # Dodáky are created only by apply_movement (or the management cmd).
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        # Per screens/09: a dodací list is never deleted.
        return False

    @admin.action(description="Znovu odeslat")
    def resend_dodaci_list(self, request, queryset) -> None:
        sent = 0
        failed = 0
        for dodaci_list in queryset:
            pdf_bytes = render_dodaci_list_pdf(dodaci_list)
            log = send_dodaci_list_email(
                dodaci_list=dodaci_list,
                trigger_reason="ruční opětovné odeslání",
                pdf_bytes=pdf_bytes,
            )
            if log.status == EmailLog.Status.SENT:
                sent += 1
            else:
                failed += 1
        if sent:
            self.message_user(
                request, f"Odesláno: {sent}", level=messages.SUCCESS
            )
        if failed:
            self.message_user(
                request, f"Selhalo: {failed}", level=messages.ERROR
            )


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "category",
        "status",
        "recipients",
        "dodaci_list",
    )
    list_filter = ("category", "status")
    search_fields = (
        "recipients",
        "subject",
        "trigger_reason",
        "error_message",
        "dodaci_list__cislo",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


