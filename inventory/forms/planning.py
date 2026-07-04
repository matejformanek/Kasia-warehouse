"""Planned transfer + mixing-plan forms."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django import forms

from ..models import (
    Branch,
    PlannedTransfer,
    Product,
)


class PlannedTransferForm(forms.ModelForm):
    """Operator-facing form for /prevody/novy/ + /prevody/<pk>/upravit/.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    all authenticated users may create + execute + cancel. No tier gate
    beyond login.
    """

    class Meta:
        model = PlannedTransfer
        fields = (
            "source_branch",
            "target_branch",
            "product",
            "quantity_kg",
            "scheduled_for",
            "notes",
        )
        widgets = {
            "scheduled_for": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "quantity_kg": forms.NumberInput(attrs={"step": "0.1"}),
        }
        labels = {
            "source_branch": "Zdrojová pobočka",
            "target_branch": "Cílová pobočka",
            "product": "Produkt",
            "quantity_kg": "Množství (kg)",
            "scheduled_for": "Plánováno na",
            "notes": "Poznámka",
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["source_branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["target_branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        ).order_by("name_cs")
        self.fields["scheduled_for"].initial = date.today

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source_branch")
        target = cleaned.get("target_branch")
        if source and target and source == target:
            raise forms.ValidationError(
                "Cílová pobočka se musí lišit od zdrojové."
            )
        return cleaned


class MixingPlanForm(forms.Form):
    """One-shot form for /michani/planovat/ — plans a PLANNED MixingJob.

    Per [0044](../context/decisions/0044-reservations-planned-states.md):
    creates the job (with derived MixingJobLine rows) without touching
    Stock. Operator then opens the job detail and clicks "Spustit teď"
    to consume stock.
    """

    branch = forms.ModelChoiceField(
        label="Pobočka",
        queryset=None,
        empty_label=None,
    )
    mixture = forms.ModelChoiceField(
        label="Směs",
        queryset=Product.objects.filter(kind=Product.Kind.MIXTURE, is_active=True),
    )
    target_qty = forms.DecimalField(
        label="Cílové množství (kg)",
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    planned_for = forms.DateField(
        label="Plánováno na",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        required=False,
        initial=date.today,
    )
    note = forms.CharField(
        label="Poznámka",
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        if user is not None and getattr(user, "branch_id", None):
            self.fields["branch"].initial = user.branch_id
            self.fields["branch"].disabled = True


# ---------------------------------------------------------------------------
# Feedback (Pass 7, per decision 0046)
# ---------------------------------------------------------------------------


