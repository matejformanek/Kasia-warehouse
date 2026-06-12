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
    path("katalog/<int:pk>/", views.product_detail, name="product_detail"),
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
]
