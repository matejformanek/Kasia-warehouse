from django import forms
from django.contrib import admin, messages

from .models import (
    Branch,
    Customer,
    DodaciList,
    DodaciListEmailLog,
    MixingJob,
    MixingJobLine,
    Movement,
    MovementAudit,
    MovementLine,
    PlannedTransfer,
    Product,
    RecipeComponent,
    Settings,
    Stock,
    StockThresholdOverride,
    Supplier,
)
from .services import (
    apply_movement,
    edit_movement,
    render_dodaci_list_pdf,
    send_dodaci_list_email,
)


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


# ---------------------------------------------------------------------------
# DodaciList + DodaciListEmailLog + Settings (per 0007 / 0031 / 0036 / 0037)
# ---------------------------------------------------------------------------


@admin.register(DodaciList)
class DodaciListAdmin(admin.ModelAdmin):
    list_display = (
        "cislo",
        "date_issued",
        "branch",
        "odberatel",
        "current_version",
        "is_edited_display",
        "created_by",
    )
    list_filter = ("branch", "year_issued")
    search_fields = ("cislo", "odberatel__name", "movement__id")
    readonly_fields = (
        "cislo",
        "branch",
        "year_issued",
        "counter",
        "current_version",
        "movement",
        "odberatel",
        "date_issued",
        "created_at",
        "created_by",
    )
    actions = ("resend_dodaci_list",)

    @admin.display(boolean=True, description="editováno")
    def is_edited_display(self, obj: DodaciList) -> bool:
        return obj.is_edited

    def has_add_permission(self, request) -> bool:
        # Dodáky are created only by apply_movement (or the management cmd).
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        # Per screens/09: a dodací list is never deleted.
        return False

    @admin.action(description="Znovu odeslat")
    def resend_dodaci_list(self, request, queryset) -> None:
        sent = 0
        failed = 0
        for dodaci_list in queryset:
            pdf_bytes = render_dodaci_list_pdf(dodaci_list)
            log = send_dodaci_list_email(
                dodaci_list=dodaci_list,
                trigger_reason="ruční opětovné odeslání",
                pdf_bytes=pdf_bytes,
            )
            if log.status == DodaciListEmailLog.Status.SENT:
                sent += 1
            else:
                failed += 1
        if sent:
            self.message_user(
                request, f"Odesláno: {sent}", level=messages.SUCCESS
            )
        if failed:
            self.message_user(
                request, f"Selhalo: {failed}", level=messages.ERROR
            )


@admin.register(DodaciListEmailLog)
class DodaciListEmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "sent_at",
        "dodaci_list",
        "version",
        "status",
        "recipients",
        "trigger_reason",
        "error_message",
    )
    list_filter = ("status", "version")
    search_fields = ("dodaci_list__cislo", "trigger_reason", "error_message")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


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
        (
            "Příjemci dodacího listu",
            {"fields": ("recipient_petr", "recipient_karolina")},
        ),
        (
            "Šablony e-mailů",
            {
                "fields": (
                    "template_initial_subject",
                    "template_initial_body",
                    "template_oprava_subject",
                    "template_oprava_body",
                )
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return not Settings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


# ---------------------------------------------------------------------------
# MixingJob + MixingJobLine (per decision 0039)
# ---------------------------------------------------------------------------


@admin.register(MixingJob)
class MixingJobAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "started_at",
        "branch",
        "mixture",
        "target_qty",
        "actual_produced_qty",
        "state",
        "created_by",
    )
    list_filter = ("state", "branch", "mixture")
    search_fields = ("mixture__name_cs", "branch__code", "note")
    readonly_fields = (
        "branch",
        "mixture",
        "target_qty",
        "actual_produced_qty",
        "state",
        "started_at",
        "finished_at",
        "created_by",
        "cancel_reason",
        "note",
        "consume_movement",
        "produce_movement",
    )

    def has_add_permission(self, request) -> bool:
        # Created only via start_mixing_job / record_completed_mixing_job.
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(MixingJobLine)
class MixingJobLineAdmin(admin.ModelAdmin):
    list_display = (
        "mixing_job",
        "component_product",
        "ratio_at_start",
        "derived_qty",
        "actual_qty",
        "sarze",
    )
    list_filter = ("mixing_job__state",)
    search_fields = (
        "component_product__name_cs",
        "mixing_job__mixture__name_cs",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


# ---------------------------------------------------------------------------
# PlannedTransfer + StockThresholdOverride (per 0043 + 0044)
# ---------------------------------------------------------------------------


@admin.register(PlannedTransfer)
class PlannedTransferAdmin(admin.ModelAdmin):
    """Read-mostly admin per 0044 — created + executed via the operator
    surface at /prevody/. Admin can view / cancel but not edit fields."""

    list_display = (
        "pk",
        "scheduled_for",
        "source_branch",
        "target_branch",
        "product",
        "quantity_kg",
        "state",
        "created_by",
    )
    list_filter = ("state", "source_branch", "target_branch")
    search_fields = ("product__name_cs", "notes")
    readonly_fields = (
        "source_branch",
        "target_branch",
        "product",
        "quantity_kg",
        "scheduled_for",
        "state",
        "notes",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(StockThresholdOverride)
class StockThresholdOverrideAdmin(admin.ModelAdmin):
    """Full CRUD per 0043 — vlastník-only in the operator app, but admin
    is unrestricted (standard pattern, matches RecipeComponentAdmin)."""

    list_display = ("product", "branch", "threshold_kg")
    list_filter = ("branch",)
    search_fields = ("product__name_cs",)
    autocomplete_fields = ("product",)
