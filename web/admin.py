from django.contrib import admin

from .models import ContactInquiry


@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    """Read-only review surface for public poptávky (decision 0050).

    The durable store is the source of truth; admin is for review only, with
    a 'vyřízeno' toggle. Public submissions are never created or edited here.
    """

    list_display = ("id", "created_at", "name", "email", "phone", "handled")
    list_filter = ("handled", "created_at")
    search_fields = ("name", "email", "phone", "message")
    list_editable = ("handled",)
    readonly_fields = ("name", "email", "phone", "message", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        return False
