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
    path("pohyby/<int:pk>/", views.movement_saved, name="movement_saved"),
    path("pohyby/<int:pk>/upravit/", views.movement_edit, name="movement_edit"),
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
]
