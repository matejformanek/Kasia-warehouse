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

from .models import Customer, Feedback, Movement, Product, Settings, Supplier


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


# ---------------------------------------------------------------------------
# Supplier + Customer CRUD (Pass 5, per decision 0040)
# ---------------------------------------------------------------------------


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
        name = (self.cleaned_data["name"] or "").strip()
        # Soft uniqueness check on active rows: don't let a worker
        # create a second "Koření CZ s.r.o." by accident.
        qs = Supplier.objects.filter(name__iexact=name, is_active=True)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Aktivní dodavatel s tímto názvem už existuje."
            )
        return name


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
        name = (self.cleaned_data["name"] or "").strip()
        qs = Customer.objects.filter(name__iexact=name, is_active=True)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Aktivní odběratel s tímto názvem už existuje."
            )
        return name


# ---------------------------------------------------------------------------
# Product + Recipe CRUD (Pass 5b, per decision 0040)
# ---------------------------------------------------------------------------


from .models import RecipeComponent  # noqa: E402 (kept here to group concerns)


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
        name = (self.cleaned_data["name_cs"] or "").strip()
        qs = Product.objects.filter(name_cs__iexact=name, is_active=True)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Aktivní produkt s tímto názvem už existuje."
            )
        return name


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


from .models import Branch  # noqa: E402


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


class StockAdjustmentForm(forms.Form):
    """One-shot form for changing the current stock of one product at one
    branch. Writes a synthetic Movement per [0041]; never raw UPDATE.
    """

    branch = forms.ModelChoiceField(
        label="Pobočka",
        queryset=None,  # set in __init__
        empty_label=None,
    )
    new_quantity = forms.DecimalField(
        label="Nový stav (kg)",
        max_digits=10,
        decimal_places=3,
        min_value=Decimal("0.000"),
    )
    reason = forms.CharField(
        label="Důvod úpravy",
        widget=forms.TextInput(attrs={"size": 60}),
    )

    def __init__(self, *args, product: Product, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.product = product
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)


# ---------------------------------------------------------------------------
# Threshold override + PlannedTransfer + MixingPlan (per decisions 0043 + 0044)
# ---------------------------------------------------------------------------


from .models import PlannedTransfer, StockThresholdOverride  # noqa: E402


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
            "scheduled_for": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "quantity_kg": forms.NumberInput(attrs={"step": "0.001"}),
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
        widget=forms.DateInput(attrs={"type": "date"}),
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


class FeedbackForm(forms.ModelForm):
    """Operator-facing form for submitting one feedback row on /podpora/."""

    class Meta:
        model = Feedback
        fields = ("page_url", "description")
        widgets = {
            "page_url": forms.TextInput(
                attrs={
                    "placeholder": "/katalog/ — volitelné",
                    "size": 40,
                }
            ),
            "description": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "page_url": "Stránka, které se hlášení týká (volitelné)",
            "description": "Popis problému, dotazu nebo nápadu",
        }


# ---------------------------------------------------------------------------
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
        widget=forms.NumberInput(attrs={"readonly": "readonly", "step": "0.001"}),
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
