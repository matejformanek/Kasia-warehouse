"""XLS recipe import forms."""

from __future__ import annotations

from decimal import Decimal

from django import forms

# XLS recipe importer (per decision 0048)
# ---------------------------------------------------------------------------

# Files larger than this are rejected at form level. The sample recipe is
# ~33 KB — 2.5 MB is comfortably above any plausible per-recipe XLS.
_XLS_MAX_BYTES = 2_500_000


class XLSImportUploadForm(forms.Form):
    """Step 1 — upload a single .xls / .xlsx recipe."""

    xls_file = forms.FileField(
        label="XLS soubor s recepturou",
        widget=forms.ClearableFileInput(attrs={"accept": ".xls,.xlsx"}),
        help_text="Formát .xls nebo .xlsx. Maximální velikost 2,5 MB.",
    )

    def clean_xls_file(self):
        f = self.cleaned_data["xls_file"]
        name = (getattr(f, "name", "") or "").lower()
        if not (name.endswith(".xls") or name.endswith(".xlsx")):
            raise forms.ValidationError(
                "Soubor musí mít koncovku .xls nebo .xlsx."
            )
        if f.size > _XLS_MAX_BYTES:
            raise forms.ValidationError(
                "Soubor je příliš velký (max 2,5 MB)."
            )
        return f


class XLSImportReviewHeaderForm(forms.Form):
    """Step 2 — Product-level fields on the review page."""

    name_cs = forms.CharField(max_length=128, label="Název směsi")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        required=False,
        label="Poznámka (postup míchání, balení…)",
    )
    total_kg = forms.DecimalField(
        max_digits=10,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"readonly": "readonly", "step": "0.1"}),
        label="Celková hmotnost (z XLS)",
    )


class XLSImportReviewLineForm(forms.Form):
    """Step 2 — one ingredient row (editable name + qty)."""

    name_cs = forms.CharField(max_length=128, label="Surovina")
    qty_kg = forms.DecimalField(
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.001"),
        label="Množství (kg)",
    )
    existing_product_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput,
    )


XLSImportReviewLineFormSet = forms.formset_factory(
    XLSImportReviewLineForm,
    extra=0,
    can_delete=True,
)
