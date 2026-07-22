"""Catalogue admin."""

from django.contrib import admin

from ..models import (
    Branch,
    Customer,
    Product,
    RecipeComponent,
    Stock,
    StockThresholdOverride,
    Supplier,
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
    fields = ("component_product", "ratio", "note")
    autocomplete_fields = ("component_product",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name_cs", "kind", "is_stock_tracked", "is_active")
    list_filter = ("kind", "is_stock_tracked", "is_active")
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
    list_display = ("mixture_product", "component_product", "ratio", "note")
    list_filter = ("mixture_product",)
    search_fields = ("mixture_product__name_cs", "component_product__name_cs")
    autocomplete_fields = ("mixture_product", "component_product")


# ---------------------------------------------------------------------------
# Movement + MovementLine + MovementAudit
# ---------------------------------------------------------------------------


@admin.register(StockThresholdOverride)
class StockThresholdOverrideAdmin(admin.ModelAdmin):
    """Full CRUD per 0043 — vlastník-only in the operator app, but admin
    is unrestricted (standard pattern, matches RecipeComponentAdmin)."""

    list_display = ("product", "branch", "threshold_kg")
    list_filter = ("branch",)
    search_fields = ("product__name_cs",)
    autocomplete_fields = ("product",)


# ---------------------------------------------------------------------------
# Feedback (per decision 0046)
# ---------------------------------------------------------------------------


