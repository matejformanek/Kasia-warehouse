"""Ciselnik masters + product/recipe/threshold forms."""

from __future__ import annotations

from django import forms

from ..models import (
    Branch,
    Customer,
    Product,
    RecipeComponent,
    StockThresholdOverride,
    Supplier,
)
from .base import validate_active_name_unique


class SupplierForm(forms.ModelForm):
    """Operator-facing form for adding/editing dodavatele.

    Per [0040](../context/decisions/0040-operator-crud-tiering.md):
    all authenticated users can create/edit/archive. `is_internal` is
    excluded — workers don't (and shouldn't) flip the Míchárna pseudo-
    supplier from this UI.
    """

    class Meta:
        model = Supplier
        fields = ("name", "ico", "address", "is_active")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_name(self) -> str:
        # Soft uniqueness on active rows: don't let a worker create a second
        # "Koření CZ s.r.o." by accident.
        return validate_active_name_unique(
            Supplier, "name", self.cleaned_data["name"], instance=self.instance, label="dodavatel"
        )


class CustomerForm(forms.ModelForm):
    """Operator-facing form for adding/editing odběratele.

    Per [0040](../context/decisions/0040-operator-crud-tiering.md):
    all authenticated users can create/edit/archive. `is_internal`
    and `is_default_recipient` are excluded — both have semantic
    invariants (interní Míchárna pair, single Říčany default per
    0030) and changing them belongs in the admin / vlastník surface.
    """

    class Meta:
        model = Customer
        fields = ("name", "ico", "dic", "address", "email", "phone", "is_active")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_name(self) -> str:
        return validate_active_name_unique(
            Customer, "name", self.cleaned_data["name"], instance=self.instance, label="odběratel"
        )


# ---------------------------------------------------------------------------
# Product + Recipe CRUD (Pass 5b, per decision 0040)
# ---------------------------------------------------------------------------




class ProductForm(forms.ModelForm):
    """Operator-facing form for new + edit produkt (surovina / směs).

    Per [0040](../context/decisions/0040-operator-crud-tiering.md):
    all authenticated users may create + edit. Archive lives on a
    separate POST endpoint gated to vlastník.
    """

    class Meta:
        model = Product
        fields = ("name_cs", "kind", "notes", "reorder_threshold_kg")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "name_cs": "Název (česky)",
            "kind": "Typ",
            "notes": "Poznámka",
            "reorder_threshold_kg": "Objednací bod (kg) — kdy upozornit",
        }

    def __init__(
        self,
        *args,
        lock_kind: bool = False,
        can_edit_threshold: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if lock_kind:
            # Once stock or recipe references exist, flipping
            # surovina↔směs would orphan data. The view passes
            # lock_kind=True in those cases.
            self.fields["kind"].disabled = True
        if not can_edit_threshold:
            # Per 0043: editing the reorder threshold is vlastník-only.
            # Drop the field entirely so a non-vlastník POST doesn't
            # null out the value an admin set.
            self.fields.pop("reorder_threshold_kg", None)

    def clean_name_cs(self) -> str:
        return validate_active_name_unique(
            Product,
            "name_cs",
            self.cleaned_data["name_cs"],
            instance=self.instance,
            label="produkt",
        )


class RecipeComponentForm(forms.ModelForm):
    """One row of a mixture's recipe — inline-edited by vlastník
    on the mixture's product detail / edit screen."""

    class Meta:
        model = RecipeComponent
        fields = ("component_product", "ratio")

    def __init__(self, *args, mixture: Product | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Limit the dropdown to raw spices (surovina) — a mixture can
        # only contain raw-spice components in MVP. Also drop the
        # mixture itself from the queryset to avoid self-reference.
        qs = Product.objects.filter(
            kind=Product.Kind.RAW_SPICE, is_active=True
        ).order_by("name_cs")
        if mixture is not None and mixture.pk:
            qs = qs.exclude(pk=mixture.pk)
        self.fields["component_product"].queryset = qs


RecipeComponentFormSet = forms.modelformset_factory(
    RecipeComponent,
    form=RecipeComponentForm,
    extra=0,
    can_delete=True,
)


# ---------------------------------------------------------------------------
# Branch CRUD (Pass 5c, per decision 0040, vlastník-only)
# ---------------------------------------------------------------------------




class BranchForm(forms.ModelForm):
    """Operator-facing form for branches. Vlastník-only per 0040.

    `code` is locked once any dodák has been issued from that branch
    (per [0008](../context/decisions/0008-dodaci-list-numbering.md))
    — re-using/changing the code would break číslování invariants.
    """

    class Meta:
        model = Branch
        fields = ("code", "name", "address", "is_active")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "code": "Kód (3 písmena)",
            "name": "Název",
            "address": "Adresa",
        }

    def __init__(self, *args, code_locked: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if code_locked:
            self.fields["code"].disabled = True

    def clean_code(self) -> str:
        code = (self.cleaned_data["code"] or "").strip().upper()
        if len(code) != 3:
            raise forms.ValidationError(
                "Kód pobočky musí mít přesně 3 písmena (např. TYN, SEZ)."
            )
        if not code.isalpha():
            raise forms.ValidationError(
                "Kód pobočky smí obsahovat pouze písmena."
            )
        qs = Branch.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Pobočka s tímto kódem už existuje."
            )
        return code

    def clean_name(self) -> str:
        return (self.cleaned_data["name"] or "").strip()


# ---------------------------------------------------------------------------
# Manual stock adjustment (Pass 5d, per decision 0041)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Threshold override + PlannedTransfer + MixingPlan (per decisions 0043 + 0044)
# ---------------------------------------------------------------------------




class ThresholdOverrideForm(forms.ModelForm):
    """One per-branch override row on the product edit page (vlastník-only)."""

    class Meta:
        model = StockThresholdOverride
        fields = ("branch", "threshold_kg")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


ThresholdOverrideFormSet = forms.modelformset_factory(
    StockThresholdOverride,
    form=ThresholdOverrideForm,
    extra=0,
    can_delete=True,
)


