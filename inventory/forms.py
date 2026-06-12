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
        fields = ("name_cs", "kind", "notes")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "name_cs": "Název (česky)",
            "kind": "Typ",
            "notes": "Poznámka",
        }

    def __init__(self, *args, lock_kind: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if lock_kind:
            # Once stock or recipe references exist, flipping
            # surovina↔směs would orphan data. The view passes
            # lock_kind=True in those cases.
            self.fields["kind"].disabled = True

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
