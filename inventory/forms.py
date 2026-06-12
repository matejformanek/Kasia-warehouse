"""Forms for the příjem / výdej create screens.

The line formset uses formset_factory with an explicit Form, not
inlineformset_factory, because Movement is built fresh inside
apply_movement and the lines are constructed as unsaved
MovementLine instances handed to the service.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django import forms

from .models import Customer, Movement, Product, Settings, Supplier


class _MovementBaseForm(forms.Form):
    """Shared fields for příjem and výdej."""

    date_issued = forms.DateField(
        label="Datum vystavení",
        initial=date.today,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    note = forms.CharField(
        label="Poznámka",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class PrijemForm(_MovementBaseForm):
    branch = forms.ModelChoiceField(
        label="Pobočka",
        queryset=None,  # set in __init__
        empty_label=None,
    )
    dodavatel = forms.ModelChoiceField(
        label="Dodavatel",
        queryset=Supplier.objects.filter(is_active=True),
    )

    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from .models import Branch

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        if user is not None and getattr(user, "branch_id", None):
            # Branch staff: lock to their branch.
            self.fields["branch"].initial = user.branch_id
            self.fields["branch"].disabled = True


class VydejForm(_MovementBaseForm):
    branch = forms.ModelChoiceField(
        label="Pobočka",
        queryset=None,
        empty_label=None,
    )
    odberatel = forms.ModelChoiceField(
        label="Odběratel",
        queryset=Customer.objects.filter(is_active=True),
    )

    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from .models import Branch

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        if user is not None and getattr(user, "branch_id", None):
            self.fields["branch"].initial = user.branch_id
            self.fields["branch"].disabled = True
        default = Customer.objects.filter(is_default_recipient=True).first()
        if default is not None:
            self.fields["odberatel"].initial = default.pk


class MovementLineForm(forms.Form):
    """One product line on a příjem / výdej form. Used inside a formset."""

    product = forms.ModelChoiceField(
        label="Produkt",
        queryset=Product.objects.filter(is_active=True),
    )
    quantity_kg = forms.DecimalField(
        label="Množství (kg)",
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    sarze = forms.CharField(label="Šarže", max_length=64, required=False)
    expiry = forms.DateField(
        label="Expirace",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    note = forms.CharField(label="Poznámka", max_length=256, required=False)


MovementLineFormSet = forms.formset_factory(
    MovementLineForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


def assert_no_future_date(value: date) -> None:
    if value > date.today():
        raise forms.ValidationError("Datum vystavení nemůže být v budoucnosti.")


def kind_label(kind: str) -> str:
    return Movement.Kind(kind).label


# ---------------------------------------------------------------------------
# Edit-mode forms (screen 11)
# ---------------------------------------------------------------------------


class MovementEditLineForm(MovementLineForm):
    """Edit-mode line form. The hidden `line_id` carries the existing
    MovementLine.pk; a blank value means "new line, add it"."""

    line_id = forms.IntegerField(required=False, widget=forms.HiddenInput)


MovementEditLineFormSet = forms.formset_factory(
    MovementEditLineForm,
    extra=0,
    can_delete=True,
)


class _MovementEditBaseForm(_MovementBaseForm):
    reason = forms.CharField(
        label="Důvod úpravy",
        widget=forms.TextInput(attrs={"size": 60}),
    )


class PrijemEditForm(_MovementEditBaseForm):
    branch = forms.ModelChoiceField(label="Pobočka", queryset=None, empty_label=None)
    dodavatel = forms.ModelChoiceField(
        label="Dodavatel",
        queryset=Supplier.objects.filter(is_active=True),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from .models import Branch

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


class VydejEditForm(_MovementEditBaseForm):
    branch = forms.ModelChoiceField(label="Pobočka", queryset=None, empty_label=None)
    odberatel = forms.ModelChoiceField(
        label="Odběratel",
        queryset=Customer.objects.filter(is_active=True),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        from .models import Branch

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


# ---------------------------------------------------------------------------
# Settings (screen 14 — operator-facing Nastavení)
# ---------------------------------------------------------------------------


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

    def clean_recipient_petr(self) -> str:
        return self.cleaned_data["recipient_petr"].strip()

    def clean_recipient_karolina(self) -> str:
        return self.cleaned_data["recipient_karolina"].strip()


class SmtpTestForm(forms.Form):
    """Tiny one-field form for the 'Otestovat odeslání' button."""

    to_email = forms.EmailField(
        label="Otestovat odeslání na adresu",
        help_text="Výchozí: vaše vlastní e-mailová adresa.",
    )
