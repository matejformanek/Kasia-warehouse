from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.home, name="home"),
    path("pobocka/<str:code>/", views.branch_dashboard, name="branch_dashboard"),
    path("prijem/novy/", views.prijem_create, name="prijem_create"),
    path("vydej/novy/", views.vydej_create, name="vydej_create"),
    path(
        "_partials/line-row/",
        views.line_row_partial,
        name="line_row_partial",
    ),
    path(
        "_partials/stock-warn/",
        views.stock_warn_partial,
        name="stock_warn_partial",
    ),
    path("pohyby/", views.movement_history, name="movement_history"),
    path("pohyby/<int:pk>/", views.movement_saved, name="movement_saved"),
    path("pohyby/<int:pk>/upravit/", views.movement_edit, name="movement_edit"),
    path("katalog/", views.catalogue_index, name="catalogue_index"),
    path("katalog/novy/", views.product_create, name="product_create"),
    # XLS recipe importer (per 0048) — vlastník-only upload→review→confirm.
    path(
        "katalog/import-xls/",
        views.xls_import_upload,
        name="xls_import_upload",
    ),
    path(
        "katalog/import-xls/potvrdit/",
        views.xls_import_confirm,
        name="xls_import_confirm",
    ),
    path("katalog/<int:pk>/", views.product_detail, name="product_detail"),
    path("katalog/<int:pk>/receptura/pdf/", views.recipe_pdf, name="recipe_pdf"),
    path("katalog/<int:pk>/upravit/", views.product_edit, name="product_edit"),
    path(
        "katalog/<int:pk>/archivovat/",
        views.product_archive,
        name="product_archive",
    ),
    path(
        "katalog/<int:pk>/aktivovat/",
        views.product_reactivate,
        name="product_reactivate",
    ),
    path(
        "katalog/<int:product_id>/pobocky/<int:branch_id>/pridat/",
        views.product_branch_add,
        name="product_branch_add",
    ),
    path(
        "katalog/<int:product_id>/pobocky/<int:branch_id>/odebrat/",
        views.product_branch_remove,
        name="product_branch_remove",
    ),
    path(
        "katalog/<int:pk>/upravit-stav/",
        views.stock_adjust_edit,
        name="stock_adjust_edit",
    ),
    path(
        "katalog/inventura/<str:code>/",
        views.inventura_edit,
        name="inventura_edit",
    ),
    path("michani/", views.mixing_job_index, name="mixing_job_index"),
    path("michani/novy/", views.mixing_job_create, name="mixing_job_create"),
    path("michani/<int:pk>/", views.mixing_job_detail, name="mixing_job_detail"),
    path(
        "michani/<int:pk>/dokoncit/",
        views.mixing_job_finish,
        name="mixing_job_finish",
    ),
    path(
        "michani/<int:pk>/zrusit/",
        views.mixing_job_cancel,
        name="mixing_job_cancel",
    ),
    path(
        "_partials/mixing-preview/",
        views.mixing_preview_partial,
        name="mixing_preview_partial",
    ),
    path("dodaky/", views.dodaci_list_index, name="dodaci_list_index"),
    path("dodaky/<str:cislo>/", views.dodaci_list_detail, name="dodaci_list_detail"),
    path(
        "dodaky/<str:cislo>/pdf/",
        views.dodaci_list_pdf,
        name="dodaci_list_pdf",
    ),
    path(
        "dodaky/<str:cislo>/znovu-odeslat/",
        views.dodaci_list_resend,
        name="dodaci_list_resend",
    ),
    path("nastaveni/", views.settings_edit, name="settings_edit"),
    path(
        "nastaveni/test-smtp/",
        views.settings_test_smtp,
        name="settings_test_smtp",
    ),
    # Supplier CRUD (Pass 5, per 0040)
    path("dodavatele/", views.supplier_index, name="supplier_index"),
    path("dodavatele/novy/", views.supplier_create, name="supplier_create"),
    path(
        "dodavatele/<int:pk>/upravit/",
        views.supplier_edit,
        name="supplier_edit",
    ),
    path(
        "dodavatele/<int:pk>/archivovat/",
        views.supplier_archive,
        name="supplier_archive",
    ),
    path(
        "dodavatele/<int:pk>/aktivovat/",
        views.supplier_reactivate,
        name="supplier_reactivate",
    ),
    # Branch CRUD (Pass 5c, per 0040 — vlastník-only)
    path("pobocky/", views.branch_index, name="branch_index"),
    path("pobocky/novy/", views.branch_create, name="branch_create"),
    path(
        "pobocky/<str:code>/upravit/",
        views.branch_edit,
        name="branch_edit",
    ),
    path(
        "pobocky/<str:code>/archivovat/",
        views.branch_archive,
        name="branch_archive",
    ),
    path(
        "pobocky/<str:code>/aktivovat/",
        views.branch_reactivate,
        name="branch_reactivate",
    ),
    # PlannedTransfer (Pass 6, per 0044) — all authenticated users.
    path("prevody/", views.planned_transfer_index, name="planned_transfer_index"),
    path(
        "prevody/novy/",
        views.planned_transfer_create,
        name="planned_transfer_create",
    ),
    path(
        "prevody/<int:pk>/",
        views.planned_transfer_detail,
        name="planned_transfer_detail",
    ),
    path(
        "prevody/<int:pk>/provest/",
        views.planned_transfer_execute,
        name="planned_transfer_execute",
    ),
    path(
        "prevody/<int:pk>/zrusit/",
        views.planned_transfer_cancel,
        name="planned_transfer_cancel",
    ),
    # Plánované míchání (Pass 6, per 0044).
    path(
        "michani/planovat/",
        views.mixing_plan_create,
        name="mixing_plan_create",
    ),
    path(
        "michani/<int:pk>/spustit/",
        views.mixing_job_start,
        name="mixing_job_start",
    ),
    # Customer CRUD (Pass 5, per 0040)
    path("odberatele/", views.customer_index, name="customer_index"),
    path("odberatele/novy/", views.customer_create, name="customer_create"),
    path(
        "odberatele/<int:pk>/upravit/",
        views.customer_edit,
        name="customer_edit",
    ),
    path(
        "odberatele/<int:pk>/archivovat/",
        views.customer_archive,
        name="customer_archive",
    ),
    path(
        "odberatele/<int:pk>/aktivovat/",
        views.customer_reactivate,
        name="customer_reactivate",
    ),
    # Podpora (Pass 7, per 0046).
    path("podpora/", views.support_view, name="support"),
    path(
        "podpora/<int:pk>/vyresit/",
        views.feedback_toggle_view,
        name="feedback_toggle",
    ),
]
