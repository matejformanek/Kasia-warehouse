"""Settings + recipient + SMTP-test forms."""

from __future__ import annotations

from django import forms

from ..models import (
    Settings,
    SettingsRecipient,
)


class SettingsForm(forms.ModelForm):
    """Operator-facing form for the Settings singleton.

    Mirrors `SettingsAdminForm`: write-only `smtp_password`, blank input
    on edit keeps the existing value. `singleton_key` excluded (system-
    managed, not part of the editable surface).
    """

    class Meta:
        model = Settings
        exclude = ("singleton_key",)
        widgets = {
            "smtp_password": forms.PasswordInput(render_value=False),
            "company_address": forms.Textarea(attrs={"rows": 2}),
            "footer_text": forms.Textarea(attrs={"rows": 2}),
            "template_initial_body": forms.Textarea(attrs={"rows": 4}),
            "template_oprava_body": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_smtp_password(self) -> str:
        new_value = self.cleaned_data.get("smtp_password", "")
        if not new_value and self.instance and self.instance.pk:
            return self.instance.smtp_password
        return new_value


# Per 0052 — operator-managed N-list of recipients replaces the fixed
# Petr+Karolína pair from 0031. Uses modelformset_factory to match the
# existing project pattern (RecipeComponentFormSet at :365,
# ThresholdOverrideFormSet at :481); the JS-clone <template> add-row UI
# lives in settings_form.html.


class SettingsRecipientForm(forms.ModelForm):
    class Meta:
        model = SettingsRecipient
        fields = (
            "email",
            "label",
            "is_active",
            "is_low_stock_recipient",
            "sort_order",
        )
        labels = {
            "email": "E-mail",
            "label": "Popisek",
            "is_active": "Aktivní",
            "is_low_stock_recipient": "Souhrn dochází zboží",
            "sort_order": "Pořadí",
        }
        widgets = {
            "sort_order": forms.NumberInput(attrs={"style": "width:5rem;"}),
        }

    def clean_email(self) -> str:
        return (self.cleaned_data.get("email") or "").strip().lower()


SettingsRecipientFormSet = forms.modelformset_factory(
    SettingsRecipient,
    form=SettingsRecipientForm,
    extra=1,
    can_delete=True,
)


class SmtpTestForm(forms.Form):
    """Tiny one-field form for the 'Otestovat odeslání' button."""

    to_email = forms.EmailField(
        label="Otestovat odeslání na adresu",
        help_text="Výchozí: vaše vlastní e-mailová adresa.",
    )


# ---------------------------------------------------------------------------
# Supplier + Customer CRUD (Pass 5, per decision 0040)
# ---------------------------------------------------------------------------


