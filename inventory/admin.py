from django import forms
from django.contrib import admin

from .models import (
    Branch,
    Customer,
    Movement,
    MovementAudit,
    MovementLine,
    Product,
    RecipeComponent,
    Stock,
    Supplier,
)
from .services import apply_movement, edit_movement


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "ico", "is_default_recipient", "is_active")
    list_filter = ("is_default_recipient", "is_active")
    search_fields = ("name", "ico", "dic")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "ico", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "ico")


class RecipeComponentInline(admin.TabularInline):
    model = RecipeComponent
    fk_name = "mixture_product"
    extra = 1
    autocomplete_fields = ("component_product",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name_cs", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name_cs",)
    inlines = (RecipeComponentInline,)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("product", "branch", "quantity")
    list_filter = ("branch",)
    search_fields = ("product__name_cs",)
    autocomplete_fields = ("product",)


@admin.register(RecipeComponent)
class RecipeComponentAdmin(admin.ModelAdmin):
    list_display = ("mixture_product", "component_product", "ratio")
    list_filter = ("mixture_product",)
    search_fields = ("mixture_product__name_cs", "component_product__name_cs")
    autocomplete_fields = ("mixture_product", "component_product")


# ---------------------------------------------------------------------------
# Movement + MovementLine + MovementAudit
# ---------------------------------------------------------------------------

_MOVEMENT_EDITABLE_FIELDS = ("branch", "date_issued", "odberatel", "dodavatel", "note")
_LINE_EDITABLE_FIELDS = ("product", "quantity_kg", "sarze", "expiry", "note")


class MovementLineInline(admin.TabularInline):
    model = MovementLine
    extra = 1
    fields = ("product", "quantity_kg", "sarze", "expiry", "note")
    autocomplete_fields = ("product",)


class MovementChangeForm(forms.ModelForm):
    """Admin form for Movement edits — adds a mandatory `reason` field."""

    reason = forms.CharField(
        label="Důvod úpravy",
        required=True,
        widget=forms.TextInput(attrs={"size": 60}),
    )

    class Meta:
        model = Movement
        fields = ("branch", "kind", "date_issued", "odberatel", "dodavatel", "note")


class MovementAddForm(forms.ModelForm):
    class Meta:
        model = Movement
        fields = ("branch", "kind", "date_issued", "odberatel", "dodavatel", "note")


@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    list_display = ("date_issued", "kind", "branch", "odberatel", "dodavatel", "created_by")
    list_filter = ("kind", "branch", "date_issued")
    search_fields = ("note", "odberatel__name", "dodavatel__name")
    inlines = (MovementLineInline,)
    autocomplete_fields = ("odberatel", "dodavatel")
    readonly_fields = ("created_at", "created_by")

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, change=False, **kwargs):
        if change:
            kwargs["form"] = MovementChangeForm
        else:
            kwargs["form"] = MovementAddForm
        return super().get_form(request, obj, change=change, **kwargs)

    def save_model(self, request, obj, form, change):
        # Intentionally no DB write here — apply_movement / edit_movement own
        # all writes in save_related(). For change=True, capture the pre-edit
        # DB snapshot so save_related can diff against it.
        if change:
            obj._pre_edit = Movement.objects.get(pk=obj.pk)
        # No super().save_model() — defer to save_related().

    def save_related(self, request, form, formsets, change):
        # Inline formset cleaned data lives in formsets[0].cleaned_data.
        line_formset = formsets[0] if formsets else None
        cleaned_lines = list(line_formset.cleaned_data) if line_formset else []

        if not change:
            # CREATE path: build line instances from the formset, then
            # apply_movement(...) saves Movement + lines + Stock atomically.
            new_lines = []
            for line_data in cleaned_lines:
                if not line_data or line_data.get("DELETE"):
                    continue
                new_lines.append(
                    MovementLine(
                        product=line_data["product"],
                        quantity_kg=line_data["quantity_kg"],
                        sarze=line_data.get("sarze", "") or "",
                        expiry=line_data.get("expiry"),
                        note=line_data.get("note", "") or "",
                    )
                )
            apply_movement(movement=form.instance, lines=new_lines, user=request.user)
            return

        # EDIT path.
        pre = form.instance._pre_edit
        new = form.instance

        changes = {}
        for field in _MOVEMENT_EDITABLE_FIELDS:
            old_value = getattr(pre, field)
            new_value = getattr(new, field)
            if old_value != new_value:
                changes[field] = new_value

        # Restore the parent to its pre-edit values; edit_movement will
        # re-apply the changes and audit them.
        for field in _MOVEMENT_EDITABLE_FIELDS:
            setattr(new, field, getattr(pre, field))

        line_changes = []
        for line_form, line_data in zip(line_formset.forms, cleaned_lines, strict=False):
            if not line_data:
                continue
            instance = line_form.instance
            if line_data.get("DELETE"):
                if instance.pk:
                    line_changes.append({"op": "remove", "line_id": instance.pk})
                continue
            if instance.pk is None:
                line_changes.append(
                    {
                        "op": "add",
                        "fields": {
                            "product": line_data["product"],
                            "quantity_kg": line_data["quantity_kg"],
                            "sarze": line_data.get("sarze", "") or "",
                            "expiry": line_data.get("expiry"),
                            "note": line_data.get("note", "") or "",
                        },
                    }
                )
            else:
                # Existing line — diff vs DB.
                db_line = MovementLine.objects.get(pk=instance.pk)
                fields_diff = {}
                for field in _LINE_EDITABLE_FIELDS:
                    old_value = getattr(db_line, field)
                    new_value = line_data.get(field)
                    if field in ("sarze", "note") and new_value is None:
                        new_value = ""
                    if old_value != new_value:
                        fields_diff[field] = new_value
                if fields_diff:
                    line_changes.append(
                        {"op": "update", "line_id": instance.pk, "fields": fields_diff}
                    )

        reason = form.cleaned_data.get("reason", "")
        edit_movement(
            movement=new,
            changes=changes,
            line_changes=line_changes,
            reason=reason,
            user=request.user,
        )


@admin.register(MovementAudit)
class MovementAuditAdmin(admin.ModelAdmin):
    list_display = (
        "edited_at",
        "movement",
        "edited_by",
        "target_kind",
        "field",
        "event",
        "old_value",
        "new_value",
        "reason",
    )
    list_filter = ("event", "target_kind", "edited_by")
    search_fields = ("movement__id", "field", "reason")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
