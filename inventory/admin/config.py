"""Config admin."""

from django import forms
from django.contrib import admin

from ..models import (
    Settings,
    SettingsRecipient,
)


class SettingsAdminForm(forms.ModelForm):
    """Admin form for Settings — renders smtp_password as a write-only field.

    An empty input leaves the existing password untouched (per 0037).
    """

    class Meta:
        model = Settings
        exclude = ("singleton_key",)
        widgets = {
            "smtp_password": forms.PasswordInput(render_value=False),
        }

    def clean_smtp_password(self) -> str:
        new_value = self.cleaned_data.get("smtp_password", "")
        if not new_value and self.instance and self.instance.pk:
            # Empty input on edit → keep the existing value.
            return self.instance.smtp_password
        return new_value


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    form = SettingsAdminForm
    fieldsets = (
        (
            "Společnost / hlavička dokumentu",
            {
                "fields": (
                    "company_name",
                    "company_ico",
                    "company_dic",
                    "company_address",
                    "company_phone",
                    "company_email",
                    "logo",
                    "footer_text",
                )
            },
        ),
        (
            "SMTP",
            {
                "fields": (
                    "smtp_host",
                    "smtp_port",
                    "smtp_use_tls",
                    "smtp_user",
                    "smtp_password",
                    "email_from_address",
                    "email_from_name",
                )
            },
        ),
        # Příjemci jsou v separátní tabulce SettingsRecipient per 0052;
        # spravují se v UI na /nastaveni/. Pole na Settings neexistují.
        (
            "Šablony e-mailů",
            {
                "fields": (
                    "template_initial_subject",
                    "template_initial_body",
                    "template_oprava_subject",
                    "template_oprava_body",
                    "template_low_stock_subject",
                    "template_low_stock_body",
                )
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return not Settings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(SettingsRecipient)
class SettingsRecipientAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "label",
        "is_active",
        "is_dodaci_recipient",
        "is_low_stock_recipient",
        "is_feedback_recipient",
        "dodaci_branch",
        "sort_order",
        "created_at",
    )
    list_filter = (
        "is_active",
        "is_dodaci_recipient",
        "is_low_stock_recipient",
        "is_feedback_recipient",
        "dodaci_branch",
    )
    search_fields = ("email", "label")
    ordering = ("-is_active", "sort_order", "id")


# ---------------------------------------------------------------------------
# MixingJob + MixingJobLine (per decision 0039)
# ---------------------------------------------------------------------------


