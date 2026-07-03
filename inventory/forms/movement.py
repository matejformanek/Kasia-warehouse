"""Movement create/edit forms + line formsets."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django import forms

from ..models import (
    Branch,
    Customer,
    Movement,
    Product,
    Supplier,
)


class _MovementBaseForm(forms.Form):
    """Shared fields for příjem and výdej."""

    date_issued = forms.DateField(
        label="Datum vystavení",
        initial=date.today,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
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
        required=False,  # optional on a planned příjem; enforced in clean()
    )
    # Per 0059: an optional arrival date. Empty / today / past = receive
    # straight away (DONE). A future date = a planned príjem (objednávka) —
    # stock changes only after the arrival is confirmed.
    expected_on = forms.DateField(
        label="Příjezd (kdy dorazí)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text=(
            "Prázdné = přijmout hned. Budoucí datum = plánovaný příjem;"
            " sklad se změní až po potvrzení."
        ),
    )

    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        if user is not None and getattr(user, "branch_id", None):
            # Branch staff: lock to their branch.
            self.fields["branch"].initial = user.branch_id
            self.fields["branch"].disabled = True

    def clean(self):
        cleaned = super().clean()
        exp = cleaned.get("expected_on")
        is_planned = exp is not None and exp > date.today()
        if is_planned:
            # Planned príjem: supplier optional, arrival date required (it is,
            # since exp is set). Nothing else to enforce.
            pass
        elif not cleaned.get("dodavatel"):
            # Immediate (DONE) príjem still requires a supplier.
            self.add_error("dodavatel", "Příjem musí mít dodavatele.")
        return cleaned


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
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
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

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


class VydejEditForm(_MovementEditBaseForm):
    branch = forms.ModelChoiceField(label="Pobočka", queryset=None, empty_label=None)
    odberatel = forms.ModelChoiceField(
        label="Odběratel",
        queryset=Customer.objects.filter(is_active=True),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


# ---------------------------------------------------------------------------
# Settings (screen 14 — operator-facing Nastavení)
# ---------------------------------------------------------------------------


